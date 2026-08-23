"""Claims persistence tests (WS5) — offline. Embedding half lives in test_embed.py (P1-2)."""

from __future__ import annotations

import json

import pytest

from hyperresearch.core.claims import (
    ingest_claims_dir,
    ingest_claims_file,
    list_claims,
    search_claims,
)


@pytest.fixture
def claims_vault(seeded_vault):
    """Seeded vault plus a claims JSON file for one of its notes."""
    temp = seeded_vault.root / "research" / "temp"
    temp.mkdir(parents=True, exist_ok=True)
    claims = [
        {
            "claim": "Async IO improves throughput for network-bound workloads",
            "quoted_support": "async/await syntax enables concurrent I/O",
            "numbers": ["10x"],
            "confidence": "high",
            "evidence_type": "empirical",
            "stance_target": "async-performance",
            "stance": "supports",
        },
        {
            "claim": "GIL limits CPU-bound parallelism",
            "confidence": "medium",
            "evidence_type": "opinion",
        },
    ]
    (temp / "claims-python-async-patterns.json").write_text(
        json.dumps(claims), encoding="utf-8"
    )
    return seeded_vault


class TestClaimsIngest:
    def test_ingest_and_list(self, claims_vault):
        summary = ingest_claims_dir(claims_vault, vault_tag="test-run")
        assert summary["ingested"] == 2
        assert summary["errors"] == []
        rows = list_claims(claims_vault.db, note_id="python-async-patterns")
        assert len(rows) == 2
        assert rows[0]["vault_tag"] == "test-run"
        assert json.loads(rows[0]["numbers"]) == ["10x"]

    def test_reingest_is_idempotent(self, claims_vault):
        ingest_claims_dir(claims_vault)
        second = ingest_claims_dir(claims_vault)
        assert second["ingested"] == 0
        assert second["skipped"] == 2
        assert len(list_claims(claims_vault.db)) == 2

    def test_fts_search(self, claims_vault):
        ingest_claims_dir(claims_vault)
        hits = search_claims(claims_vault.db, "throughput")
        assert len(hits) == 1
        assert hits[0]["note_id"] == "python-async-patterns"

    def test_unknown_note_errors_softly(self, claims_vault):
        temp = claims_vault.root / "research" / "temp"
        (temp / "claims-nonexistent-note.json").write_text("[]", encoding="utf-8")
        summary = ingest_claims_dir(claims_vault)
        assert any("not in vault" in e for e in summary["errors"])

    def test_wrapper_format_accepted(self, claims_vault, tmp_path):
        p = claims_vault.root / "research" / "temp" / "claims-rust-ownership.json"
        p.write_text(json.dumps({"claims": [{"claim": "Ownership prevents data races"}]}), encoding="utf-8")
        r = ingest_claims_file(claims_vault.db, p)
        claims_vault.db.commit()
        assert r["ingested"] == 1

    def test_claims_cli(self, claims_vault, monkeypatch):
        from typer.testing import CliRunner

        from hyperresearch.cli import app

        monkeypatch.chdir(claims_vault.root)
        runner = CliRunner()
        result = runner.invoke(app, ["claims", "ingest", "--tag", "cli-run", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["ingested"] == 2

        result = runner.invoke(app, ["claims", "search", "throughput", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["count"] == 1


