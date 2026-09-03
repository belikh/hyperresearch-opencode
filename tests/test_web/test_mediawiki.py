"""Tests for the MediaWiki clean-text lane (native action-API fetching).

Zero network throughout, same pattern as tests/test_web/test_deepwiki_provider.py:
- an ``httpx.MockTransport`` injected through the private ``_transport`` kwarg
  of :func:`fetch_mediawiki` — the full API exchange is asserted
  request-by-request;
- DNS pinned per-test, because the SSRF guard resolves the target hostname
  BEFORE any HTTP traffic exists to mock.

Chain-integration tests monkeypatch ``hyperresearch.web.mediawiki.fetch_mediawiki``
(the provider chain resolves it lazily at call time) and drive fakes through
``resolve_web_provider(..., _factories={...})`` — the chain's DI seam — so no
provider ever touches the network either.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from hyperresearch.web import _netguard
from hyperresearch.web.base import WebResult, resolve_web_provider
from hyperresearch.web.mediawiki import (
    MediawikiPageError,
    _drop_tail_headings,
    _headings_to_markdown,
    extract_page_title,
    fetch_mediawiki,
    is_mediawiki_url,
)

# ---------------------------------------------------------------------------
# Offline helpers
# ---------------------------------------------------------------------------

Handler = Callable[[httpx.Request], httpx.Response]

WIKI_URL = "https://en.wikipedia.org/wiki/Immunotherapy"

EXTRACT = (
    "Immunotherapy is the treatment of disease by activating or suppressing "
    "the immune system.\n\n"
    "== Types ==\n"
    "Cellular therapies use T cells.\n\n"
    "=== Checkpoint inhibitors ===\n"
    "They block checkpoint proteins.\n\n"
    "== See also ==\n"
    "Checkpoint inhibitor\n\n"
    "== References ==\n"
)


def _pin_dns(monkeypatch: pytest.MonkeyPatch, *addresses: str) -> None:
    """Pin THE SAME getaddrinfo answer(s) for every hostname — no network."""

    def _info(addr: str) -> tuple[Any, ...]:
        if ":" in addr:
            return (10, 1, 6, "", (addr, 0, 0, 0))
        return (2, 1, 6, "", (addr, 0))

    infos = [_info(a) for a in addresses]
    monkeypatch.setattr(_netguard.socket, "getaddrinfo", lambda host, port: infos)


def _api_ok(
    extract: str = "Real article prose. " * 60,
    title: str = "Immunotherapy",
    **page_extra: Any,
) -> httpx.Response:
    """A successful action=query extracts+info payload for one page."""
    return httpx.Response(
        200,
        json={
            "query": {
                "pages": [
                    {
                        "pageid": 226533,
                        "ns": 0,
                        "title": title,
                        "canonicalurl": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        "touched": "2026-09-02T16:28:12Z",
                        "pagelanguage": "en",
                        "extract": extract,
                        **page_extra,
                    }
                ]
            }
        },
    )


# ---------------------------------------------------------------------------
# URL recognition
# ---------------------------------------------------------------------------


class TestIsMediawikiUrl:
    def test_wikimedia_hosts_recognised(self) -> None:
        for url in (
            "https://en.wikipedia.org/wiki/Foo",
            "https://ja.wikipedia.org/wiki/Foo",
            "https://en.m.wikipedia.org/wiki/Foo",
            "https://simple.wiktionary.org/wiki/Foo",
            "https://commons.wikimedia.org/wiki/Foo",
            "https://www.wikidata.org/wiki/Q42",
            "https://www.mediawiki.org/wiki/Foo",
            "https://de.wikibooks.org/wiki/Foo",
        ):
            assert is_mediawiki_url(url), url

    def test_lookalike_hosts_rejected(self) -> None:
        # Suffix match on the HOST, not a substring of the whole URL —
        # "en.wikipedia.org.evil.com" must never enter the lane.
        for url in (
            "https://example.com/wiki/Foo",
            "https://en.wikipedia.org.evil.com/wiki/Foo",
            "https://notwikipedia.org/wiki/Foo",
            "https://mywikipedia.org/wiki/Foo",
            "file:///etc/passwd",
        ):
            assert not is_mediawiki_url(url), url


class TestExtractPageTitle:
    def test_plain_wiki_path(self) -> None:
        assert extract_page_title(WIKI_URL) == "Immunotherapy"

    def test_percent_encoded_title(self) -> None:
        assert extract_page_title("https://en.wikipedia.org/wiki/URL%20encoding") == "URL encoding"

    def test_fragment_ignored(self) -> None:
        assert extract_page_title("https://en.wikipedia.org/wiki/Foo#History") == "Foo"

    def test_talk_namespace_allowed(self) -> None:
        # Prose namespaces go to the API; only non-prose ones pre-filter.
        assert extract_page_title("https://en.wikipedia.org/wiki/Talk:Foo") == "Talk:Foo"

    def test_index_php_title_param(self) -> None:
        assert extract_page_title("https://en.wikipedia.org/w/index.php?title=Foo") == "Foo"

    def test_non_prose_namespaces_rejected(self) -> None:
        for ns in ("Special", "Media", "File"):
            assert extract_page_title(f"https://en.wikipedia.org/wiki/{ns}:Foo") is None, ns

    def test_revision_specific_views_rejected(self) -> None:
        # The extract is always the CURRENT revision — oldid/diff/curid views
        # must be served (and honoured) by the generic chain.
        for suffix in ("oldid=123", "diff=456", "curid=789", "action=edit"):
            url = f"https://en.wikipedia.org/w/index.php?title=Foo&{suffix}"
            assert extract_page_title(url) is None, suffix

    def test_non_page_paths_rejected(self) -> None:
        for url in (
            "https://en.wikipedia.org/wiki/Special:Export/Foo",
            "https://en.wikipedia.org/w/index.php",
            "https://en.wikipedia.org/wiki/",
            "https://en.wikipedia.org/main_page",
        ):
            assert extract_page_title(url) is None, url


# ---------------------------------------------------------------------------
# Extract post-processing
# ---------------------------------------------------------------------------


class TestHeadingsToMarkdown:
    def test_levels_map_one_to_one(self) -> None:
        assert _headings_to_markdown("== A ==") == "## A"
        assert _headings_to_markdown("=== A ===") == "### A"
        assert _headings_to_markdown("== A ==\nprose\n=== B ===")
        assert "## A" in _headings_to_markdown("== A ==\nprose\n=== B ===")
        assert "### B" in _headings_to_markdown("== A ==\nprose\n=== B ===")

    def test_prose_untouched(self) -> None:
        line = "2 + 2 = 4, a = b"
        assert _headings_to_markdown(line) == line

    def test_single_equals_is_not_a_heading(self) -> None:
        assert _headings_to_markdown("= A =") == "= A ="


class TestDropTailHeadings:
    def test_trailing_empty_references_dropped(self) -> None:
        assert _drop_tail_headings("Prose.\n\n## References") == "Prose."

    def test_stack_of_empty_tail_sections_dropped(self) -> None:
        md = "Prose.\n\n## Notes\n\n## References\n\n"
        assert _drop_tail_headings(md) == "Prose."

    def test_heading_with_content_survives(self) -> None:
        md = "Prose.\n\n## See also\nCheckpoint inhibitor"
        assert _drop_tail_headings(md) == md

    def test_content_only_untouched(self) -> None:
        assert _drop_tail_headings("Just prose.") == "Just prose."


# ---------------------------------------------------------------------------
# fetch_mediawiki (mocked transport)
# ---------------------------------------------------------------------------


class TestFetchMediawiki:
    def test_happy_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["ua"] = request.headers.get("User-Agent", "")
            return _api_ok(extract=EXTRACT)

        r = fetch_mediawiki(WIKI_URL, _transport=httpx.MockTransport(handler))
        assert r is not None
        # Original URL survives — the sources table and frontmatter key on it.
        assert r.url == WIKI_URL
        assert r.title == "Immunotherapy"
        # Headings converted; empty tail References dropped; See also kept.
        assert "## Types" in r.content
        assert "### Checkpoint inhibitors" in r.content
        assert "## See also" in r.content
        assert "References" not in r.content
        # Prose survives.
        assert "immune system" in r.content
        # Metadata carried through.
        assert r.metadata["provider"] == "mediawiki-api"
        assert r.metadata["page_id"] == 226533
        assert r.metadata["language"] == "en"
        assert r.metadata["last_edited"] == "2026-09-02T16:28:12Z"
        # Request shape: same-host /w/api.php, action=query, explaintext.
        assert "/w/api.php?" in seen["url"]
        assert "action=query" in seen["url"]
        assert "explaintext=1" in seen["url"]
        assert "titles=Immunotherapy" in seen["url"]
        assert "hyperresearch" in seen["ua"]

    def test_redirect_recorded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "query": {
                        "redirects": [{"from": "USA", "to": "United States"}],
                        "pages": [
                            {
                                "pageid": 3434750,
                                "ns": 0,
                                "title": "United States",
                                "extract": "A country. " * 80,
                                "pagelanguage": "en",
                            }
                        ],
                    }
                },
            )

        r = fetch_mediawiki(
            "https://en.wikipedia.org/wiki/USA", _transport=httpx.MockTransport(handler)
        )
        assert r is not None
        assert r.url == "https://en.wikipedia.org/wiki/USA"
        assert r.title == "United States"
        assert r.metadata["redirected_from"] == "USA"

    def test_missing_page_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            return _api_ok(extract="", title="Zzz missing", missing=True)

        with pytest.raises(MediawikiPageError, match="does not exist"):
            fetch_mediawiki(
                "https://en.wikipedia.org/wiki/Zzz_missing",
                _transport=httpx.MockTransport(handler),
            )

    def test_api_missingtitle_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"error": {"code": "missingtitle", "info": "no such page"}},
            )

        with pytest.raises(MediawikiPageError):
            fetch_mediawiki(
                "https://en.wikipedia.org/wiki/Zzz_missing",
                _transport=httpx.MockTransport(handler),
            )

    def test_other_api_errors_fall_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"error": {"code": "invalidtitle", "info": "bad"}})

        assert fetch_mediawiki(WIKI_URL, _transport=httpx.MockTransport(handler)) is None

    def test_empty_extract_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Category:/Wikidata pages have no prose — the generic render is the
        # better representation, so the lane yields.
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            return _api_ok(extract="")

        assert (
            fetch_mediawiki(
                "https://en.wikipedia.org/wiki/Category:Physics",
                _transport=httpx.MockTransport(handler),
            )
            is None
        )

    def test_http_error_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="upstream overloaded")

        assert fetch_mediawiki(WIKI_URL, _transport=httpx.MockTransport(handler)) is None

    def test_transport_error_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        assert fetch_mediawiki(WIKI_URL, _transport=httpx.MockTransport(handler)) is None

    def test_non_wiki_url_short_circuits_before_any_request(self) -> None:
        # No _transport at all: a request attempt would crash the test —
        # proving the host check fires first.
        assert fetch_mediawiki("https://example.com/wiki/Foo") is None

    def test_error_type_is_runtime_error(self) -> None:
        # Not a fall-through signal: the chain must surface it, not retry.
        assert issubclass(MediawikiPageError, RuntimeError)


# ---------------------------------------------------------------------------
# Provider-chain integration (fakes through the DI seam)
# ---------------------------------------------------------------------------


def _mw_result(url: str) -> WebResult:
    return WebResult(
        url=url,
        title="Served by lane",
        content="Clean wiki prose. " * 60,
        metadata={"provider": "mediawiki-api"},
    )


class _LaneStub:
    """Offline stand-in for the mediawiki lane (patched into the module)."""

    def __init__(self, result_for: Callable[[str], WebResult | None]) -> None:
        self.result_for = result_for
        self.calls: list[str] = []

    def __call__(self, url: str, **_kwargs: Any) -> WebResult | None:
        self.calls.append(url)
        return self.result_for(url)


class TestChainFetchHook:
    def test_lane_serves_wiki_url_and_records_provenance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hyperresearch.web.mediawiki as mw_mod

        lane = _LaneStub(_mw_result)
        monkeypatch.setattr(mw_mod, "fetch_mediawiki", lane)
        prov = resolve_web_provider("builtin")

        result = prov.fetch(WIKI_URL)

        assert lane.calls == [WIKI_URL]
        assert result.title == "Served by lane"
        assert prov.name == "mediawiki-api"  # serving-provider provenance

    def test_none_falls_through_to_candidates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import hyperresearch.web.mediawiki as mw_mod

        lane = _LaneStub(lambda url: None)  # lane not applicable
        monkeypatch.setattr(mw_mod, "fetch_mediawiki", lane)

        def make_generic() -> Any:
            class P:
                name = "generic-stub"

                def fetch(self, url: str) -> WebResult:
                    return WebResult(url=url, title="Generic", content="content " * 100)

                def search(self, query: str, max_results: int = 5) -> list[WebResult]:
                    raise NotImplementedError

            return P()

        prov = resolve_web_provider("builtin", _factories={"builtin": make_generic})
        result = prov.fetch(WIKI_URL)
        assert lane.calls == [WIKI_URL]
        assert result.title == "Generic"
        # Serving name = the DECLARED candidate that served (chain semantics).
        assert prov.name == "builtin"

    def test_missing_page_error_surfaces(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import hyperresearch.web.mediawiki as mw_mod

        def raise_missing(url: str, **_kwargs: Any) -> WebResult | None:
            raise MediawikiPageError("does not exist")

        monkeypatch.setattr(mw_mod, "fetch_mediawiki", raise_missing)
        prov = resolve_web_provider("builtin")

        with pytest.raises(MediawikiPageError):
            prov.fetch(WIKI_URL)


class _BatchStub:
    """Batch-capable fake provider (records what it was asked to fetch)."""

    name = "batch-stub"

    def __init__(self) -> None:
        self.fetched: list[str] = []

    def fetch(self, url: str) -> WebResult:
        raise AssertionError("single fetch should not be called on batch stub")

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        raise NotImplementedError

    def fetch_many(self, urls: list[str]) -> list[WebResult]:
        self.fetched.extend(urls)
        return [WebResult(url=u, title="Batched", content="content " * 100) for u in urls]


class TestChainFetchManyHook:
    def test_wiki_urls_split_out_of_the_batch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import hyperresearch.web.mediawiki as mw_mod

        lane = _LaneStub(lambda url: _mw_result(url) if "wikipedia.org" in url else None)
        monkeypatch.setattr(mw_mod, "fetch_mediawiki", lane)
        stub_holder: dict[str, _BatchStub] = {}
        urls = [
            "https://example.com/a",
            WIKI_URL,
            "https://example.com/b",
        ]

        def make_stub() -> Any:
            stub_holder["stub"] = _BatchStub()
            return stub_holder["stub"]

        # "parallel" is a _FETCH_MANY_PROVIDERS name, so the chain exposes
        # fetch_many; the factory serves our offline stub instead of the
        # real ParallelProvider.
        prov = resolve_web_provider("parallel", _factories={"parallel": make_stub})
        assert hasattr(prov, "fetch_many"), "chain advertises batch lane"

        results = prov.fetch_many(urls)

        stub = stub_holder["stub"]
        # Only the non-wiki URLs reached the generic batch lane.
        assert stub.fetched == ["https://example.com/a", "https://example.com/b"]
        # All three results came back, in input order.
        assert [r.url for r in results] == urls
        titles = {r.url: r.title for r in results}
        assert titles[WIKI_URL] == "Served by lane"
        assert titles["https://example.com/a"] == "Batched"

    def test_all_wiki_wave_never_touches_the_batch_lane(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hyperresearch.web.mediawiki as mw_mod

        lane = _LaneStub(_mw_result)
        monkeypatch.setattr(mw_mod, "fetch_mediawiki", lane)

        def make_stub() -> Any:
            class ExplodingStub(_BatchStub):
                def fetch_many(self, urls: list[str]) -> list[WebResult]:
                    raise AssertionError("batch lane must not serve wiki URLs")

            return ExplodingStub()

        prov = resolve_web_provider("parallel", _factories={"parallel": make_stub})
        results = prov.fetch_many([WIKI_URL, "https://ja.wikipedia.org/wiki/光学"])
        assert [r.title for r in results] == ["Served by lane", "Served by lane"]
        assert prov.name == "mediawiki-api"

    def test_no_wiki_urls_unchanged_behaviour(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import hyperresearch.web.mediawiki as mw_mod

        lane = _LaneStub(lambda url: None)
        monkeypatch.setattr(mw_mod, "fetch_mediawiki", lane)
        stub_holder: dict[str, _BatchStub] = {}
        urls = ["https://example.com/a", "https://example.com/b"]

        def make_stub() -> Any:
            stub_holder["stub"] = _BatchStub()
            return stub_holder["stub"]

        prov = resolve_web_provider("parallel", _factories={"parallel": make_stub})
        results = prov.fetch_many(urls)

        assert stub_holder["stub"].fetched == urls
        assert [r.url for r in results] == urls
