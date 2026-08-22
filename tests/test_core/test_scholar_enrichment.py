"""Tests for `hpr sources score` enrichment — fully offline, HTTP stubbed."""

from __future__ import annotations

import json

import pytest

from hyperresearch.core import scholar
from hyperresearch.core.scholar import extract_doi


@pytest.fixture
def doi_vault(tmp_vault):
    """Vault with two DOI-bearing notes and one plain note."""
    from hyperresearch.core.note import write_note
    from hyperresearch.core.sync import compute_sync_plan, execute_sync

    write_note(
        tmp_vault.notes_dir, "Cited Paper", body="Highly cited work.",
        tier="institutional",
        extra_frontmatter={"doi": "10.1/cited", "source": "https://doi.org/10.1/cited"},
    )
    write_note(
        tmp_vault.notes_dir, "Retracted Paper", body="Withdrawn work.",
        tier="institutional",
        extra_frontmatter={"doi": "10.1/retracted", "source": "https://doi.org/10.1/retracted"},
    )
    write_note(tmp_vault.notes_dir, "Plain Blog", body="No DOI here.")
    plan = compute_sync_plan(tmp_vault, force=True)
    execute_sync(tmp_vault, plan)
    return tmp_vault


def _stub_openalex(monkeypatch, responses: dict[str, dict | None]):
    """Stub the raw HTTP layer with canned per-URL-substring responses."""
    calls: list[str] = []

    def fake_get(url: str):
        calls.append(url)
        for key, value in responses.items():
            if key in url:
                return value
        return None

    monkeypatch.setattr(scholar, "_http_get_json", fake_get)
    return calls


OPENALEX_CITED = {
    "cited_by_count": 512,
    "primary_location": {"source": {"display_name": "Nature"}},
    "is_retracted": False,
}
OPENALEX_RETRACTED = {
    "cited_by_count": 30,
    "primary_location": {"source": {"display_name": "BadJournal"}},
    "is_retracted": True,
}


class TestScoreSources:
    def test_enrichment_populates_db_and_frontmatter(self, doi_vault, monkeypatch):
        _stub_openalex(monkeypatch, {
            "10.1%2Fcited": OPENALEX_CITED,
            "10.1%2Fretracted": OPENALEX_RETRACTED,
        })
        result = scholar.score_sources(doi_vault)
        assert result["scored"] == 2
        assert result["retracted"] == ["retracted-paper"]

        row = doi_vault.db.execute(
            "SELECT citation_count, venue, is_retracted, authority_score, quality_score "
            "FROM notes WHERE id = 'cited-paper'"
        ).fetchone()
        assert row["citation_count"] == 512
        assert row["venue"] == "Nature"
        assert row["is_retracted"] == 0
        assert row["authority_score"] is not None
        assert row["quality_score"] is not None

        # Frontmatter mirror written
        text = next(doi_vault.notes_dir.glob("cited-paper.md")).read_text(encoding="utf-8")
        assert "citation_count: 512" in text
        assert "venue: Nature" in text

    def test_retracted_gets_quality_floor(self, doi_vault, monkeypatch):
        _stub_openalex(monkeypatch, {
            "10.1%2Fcited": OPENALEX_CITED,
            "10.1%2Fretracted": OPENALEX_RETRACTED,
        })
        scholar.score_sources(doi_vault)
        floor = doi_vault.config.ranking.retraction_floor
        row = doi_vault.db.execute(
            "SELECT quality_score FROM notes WHERE id = 'retracted-paper'"
        ).fetchone()
        assert row["quality_score"] == floor

    def test_cache_prevents_second_http_call(self, doi_vault, monkeypatch):
        calls = _stub_openalex(monkeypatch, {
            "10.1%2Fcited": OPENALEX_CITED,
            "10.1%2Fretracted": OPENALEX_RETRACTED,
        })
        scholar.score_sources(doi_vault)
        first_count = len(calls)
        assert first_count == 2
        # Re-score fresh=True → cache bypassed but api_cache row present;
        # fresh=False re-run skips already-enriched notes entirely.
        scholar.score_sources(doi_vault)
        assert len(calls) == first_count  # no new HTTP calls

    def test_api_failure_is_soft(self, doi_vault, monkeypatch):
        _stub_openalex(monkeypatch, {})  # everything misses -> None
        result = scholar.score_sources(doi_vault)
        assert result["scored"] == 0
        assert len(result["missing"]) == 2  # both DOI notes unresolved, no crash

    def test_arxiv_ids_route_to_semantic_scholar(self, tmp_vault, monkeypatch):
        from hyperresearch.core.note import write_note
        from hyperresearch.core.sync import compute_sync_plan, execute_sync

        write_note(
            tmp_vault.notes_dir, "Arxiv Preprint", body="x",
            extra_frontmatter={"doi": "arXiv:2501.01234"},
        )
        plan = compute_sync_plan(tmp_vault, force=True)
        execute_sync(tmp_vault, plan)

        calls = _stub_openalex(monkeypatch, {
            "semanticscholar": {"citationCount": 7, "venue": "arXiv"},
        })
        result = scholar.score_sources(tmp_vault)
        assert result["scored"] == 1
        assert any("semanticscholar.org" in c for c in calls)
        assert not any("openalex.org" in c for c in calls)

    def test_authority_is_vault_relative_percentile(self, doi_vault, monkeypatch):
        _stub_openalex(monkeypatch, {
            "10.1%2Fcited": OPENALEX_CITED,        # 512 citations
            "10.1%2Fretracted": OPENALEX_RETRACTED,  # 30 citations
        })
        scholar.score_sources(doi_vault)
        rows = {
            r["id"]: r["authority_score"]
            for r in doi_vault.db.execute(
                "SELECT id, authority_score FROM notes WHERE authority_score IS NOT NULL"
            )
        }
        assert rows["cited-paper"] == 1.0
        assert rows["retracted-paper"] == 0.5


class TestBackfillDois:
    def test_backfill_from_source_url(self, tmp_vault):
        from hyperresearch.core.note import write_note
        from hyperresearch.core.sync import compute_sync_plan, execute_sync

        write_note(
            tmp_vault.notes_dir, "Old Fetch", body="fetched before doi capture existed",
            source="https://arxiv.org/abs/2401.00001",
        )
        plan = compute_sync_plan(tmp_vault, force=True)
        execute_sync(tmp_vault, plan)

        gained = scholar.backfill_dois(tmp_vault)
        assert gained == 1
        row = tmp_vault.db.execute("SELECT doi FROM notes WHERE id = 'old-fetch'").fetchone()
        assert row["doi"] == "arXiv:2401.00001"
        text = next(tmp_vault.notes_dir.glob("old-fetch.md")).read_text(encoding="utf-8")
        assert "arXiv:2401.00001" in text


class TestApiCache:
    def test_cache_roundtrip(self, tmp_vault, monkeypatch):
        calls = []

        def fake_get(url):
            calls.append(url)
            return {"hello": "world"}

        monkeypatch.setattr(scholar, "_http_get_json", fake_get)
        conn = tmp_vault.db
        r1 = scholar._fetch_json(conn, "https://api.openalex.org/works/x", ttl_days=30)
        r2 = scholar._fetch_json(conn, "https://api.openalex.org/works/x", ttl_days=30)
        assert r1 == r2 == {"hello": "world"}
        assert len(calls) == 1  # second hit served from cache

    def test_fresh_bypasses_cache(self, tmp_vault, monkeypatch):
        calls = []

        def fake_get(url):
            calls.append(url)
            return {"n": len(calls)}

        monkeypatch.setattr(scholar, "_http_get_json", fake_get)
        conn = tmp_vault.db
        scholar._fetch_json(conn, "https://api.openalex.org/works/y", ttl_days=30)
        r2 = scholar._fetch_json(conn, "https://api.openalex.org/works/y", ttl_days=30, fresh=True)
        assert len(calls) == 2
        assert r2 == {"n": 2}

    def test_cache_body_is_json(self, tmp_vault, monkeypatch):
        monkeypatch.setattr(scholar, "_http_get_json", lambda url: {"a": 1})
        conn = tmp_vault.db
        scholar._fetch_json(conn, "https://api.openalex.org/works/z", ttl_days=30)
        row = conn.execute(
            "SELECT body FROM api_cache WHERE url = 'https://api.openalex.org/works/z'"
        ).fetchone()
        assert json.loads(row["body"]) == {"a": 1}


# ---------------------------------------------------------------------------
# P1-5 hardening — twin-site SSRF closure (scholar._http_get_json lane)
#
# Pre-fix, this lane called httpx.get(follow_redirects=True): the OpenAlex /
# Semantic Scholar / Unpaywall hosts are fixed, but a compromised or poisoned
# response could redirect into internal infrastructure unchecked. Mirrors
# tests/test_web/test_ssrf_guard.py patterns; fully offline.
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, url: str, status_code: int = 200, headers: dict | None = None,
                 payload: dict | None = None):
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload

    def json(self) -> dict | None:
        return self._payload


def _info(addr: str):
    if ":" in addr:
        return (10, 1, 6, "", (addr, 0, 0, 0))
    return (2, 1, 6, "", (addr, 0))


@pytest.fixture
def guarded_httpx(monkeypatch):
    """Script httpx.get responses for _netguard.guarded_get; records calls."""
    calls: list[str] = []
    script: list[_Resp] = []

    def fake_get(url, **kwargs):
        calls.append(str(url))
        assert kwargs.get("follow_redirects") is False, "redirects must be manual"
        if not script:
            pytest.fail(f"unexpected httpx request to {url}")
        return script.pop(0)

    monkeypatch.setattr("httpx.get", fake_get)

    class _Stub:
        @property
        def calls(self) -> list[str]:
            return calls

        def enqueue(self, *responses: _Resp) -> None:
            script.extend(responses)

    return _Stub()


class TestHttpGetJsonSsrfGuard:
    def test_loopback_start_never_requested(self, monkeypatch, guarded_httpx, caplog):
        from hyperresearch.web import _netguard

        monkeypatch.setattr(
            _netguard.socket, "getaddrinfo", lambda host, port: [_info("127.0.0.1")]
        )

        import logging

        with caplog.at_level(logging.WARNING):
            assert scholar._http_get_json("http://127.0.0.1:8000/api/works") is None

        assert "blocked by SSRF guard" in caplog.text
        assert guarded_httpx.calls == []

    def test_public_shaped_redirect_into_private_host_blocked(
        self, monkeypatch, guarded_httpx, caplog
    ):
        from hyperresearch.web import _netguard

        table = {"intranet.internal": "10.0.0.9"}  # keyed by hostname

        def fake(host, port):
            return [_info(table.get(host, "93.184.216.34"))]

        monkeypatch.setattr(_netguard.socket, "getaddrinfo", fake)
        guarded_httpx.enqueue(
            _Resp(
                "https://api.openalex.org/works/doi:10.1/x",
                status_code=302,
                headers={"location": "http://intranet.internal/vault"},
            ),
        )

        import logging

        with caplog.at_level(logging.WARNING):
            assert (
                scholar._http_get_json("https://api.openalex.org/works/doi:10.1/x")
                is None
            )

        assert "blocked by SSRF guard" in caplog.text
        assert guarded_httpx.calls == ["https://api.openalex.org/works/doi:10.1/x"], (
            "the redirect target must be rejected BEFORE its request is issued"
        )

    def test_success_path_still_returns_payload(self, monkeypatch, guarded_httpx):
        from hyperresearch.web import _netguard

        monkeypatch.setattr(
            _netguard.socket, "getaddrinfo",
            lambda host, port: [_info("93.184.216.34")],
        )
        guarded_httpx.enqueue(_Resp("https://api.openalex.org/x", payload={"ok": True}))
        assert scholar._http_get_json("https://api.openalex.org/x") == {"ok": True}


class TestDoiHostExactMatch:
    """P1-5 hardening: `\"doi.org\" in netloc` substring classification let
    notdoi.org.evil.com (or doi.org.evil.com) route its PATH through the
    DOI extractor. Exact/suffix match now, mirroring _on_arxiv_host."""

    def test_spoofed_suffix_host_does_not_classify(self):
        assert extract_doi("https://notdoi.org.evil.com/10.1038/nature") is None

    def test_spoofed_prefix_host_does_not_classify(self):
        assert extract_doi("https://doi.org.evil.com/10.1038/nature") is None

    def test_real_doi_org_still_classifies(self):
        assert (
            extract_doi("https://doi.org/10.1038/s41586-024-0001-2")
            == "10.1038/s41586-024-0001-2"
        )

    def test_www_subdomain_still_classifies(self):
        assert extract_doi("https://www.doi.org/10.1038/nature") == "10.1038/nature"

    def test_port_suffix_does_not_break_classification(self):
        assert extract_doi("https://doi.org:443/10.1038/nature") == "10.1038/nature"
