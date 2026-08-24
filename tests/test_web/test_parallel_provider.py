"""Tests for the Parallel web provider (api.parallel.ai Search & Extract).

Zero network throughout, via two seams:
- an ``httpx.MockTransport`` injected through the private ``_transport`` ctor
  kwarg — request method/URL/path/headers/body are asserted on the captured
  ``httpx.Request``;
- DNS stubbed per-test (same pattern as tests/test_web/test_ssrf_guard.py),
  because fetch()/fetch_many() run the SSRF guard — which resolves the target
  hostname — BEFORE any HTTP traffic exists to mock.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx
import pytest

from hyperresearch.web import _netguard
from hyperresearch.web._netguard import UnsafeUrlError
from hyperresearch.web.base import WebResult, get_provider
from hyperresearch.web.parallel_provider import (
    ParallelApiError,
    ParallelAuthError,
    ParallelProvider,
)

# ---------------------------------------------------------------------------
# Offline helpers
# ---------------------------------------------------------------------------

Handler = Callable[[httpx.Request], httpx.Response]


def _pin_dns(monkeypatch: pytest.MonkeyPatch, *addresses: str) -> None:
    """Pin THE SAME getaddrinfo answer(s) for every hostname — no network."""

    def _info(addr: str) -> tuple[Any, ...]:
        if ":" in addr:
            return (10, 1, 6, "", (addr, 0, 0, 0))
        return (2, 1, 6, "", (addr, 0))

    infos = [_info(a) for a in addresses]
    monkeypatch.setattr(_netguard.socket, "getaddrinfo", lambda host, port: infos)


def _make_provider(
    handler: Handler,
    *,
    api_key: str | None = "test-key",
    **kwargs: Any,
) -> ParallelProvider:
    return ParallelProvider(api_key=api_key, _transport=httpx.MockTransport(handler), **kwargs)


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "url": "https://example.com/a",
        "title": "Example",
        "publish_date": None,
        "excerpts": ["Excerpt one.", "Excerpt two."],
        "full_content": None,
    }
    row.update(overrides)
    return row


def _extract_response(
    results: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "extract_id": "extract_test",
            "results": results or [],
            "errors": errors or [],
            "session_id": "session_test",
        },
    )


def _search_response(results: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "search_id": "search_test",
            "results": results,
            "session_id": "session_test",
        },
    )


# ---------------------------------------------------------------------------
# Factory registration & construction
# ---------------------------------------------------------------------------


def test_provider_registered_via_factory() -> None:
    """No env key needed at all: auth is enforced at call time, not construction."""
    prov = get_provider("parallel")
    assert prov.name == "parallel"


def test_unknown_provider_lists_parallel_in_error() -> None:
    """The unknown-provider error should advertise 'parallel' as available."""
    with pytest.raises(ValueError, match="parallel"):
        get_provider("not-a-real-provider")


def test_mode_validation_rejects_bogus_mode() -> None:
    with pytest.raises(ValueError, match="mode"):
        ParallelProvider(mode="hyper")


@pytest.mark.parametrize("mode", ["turbo", "fast", "basic", "advanced"])
def test_mode_validation_accepts_spec_modes(mode: str) -> None:
    ParallelProvider(mode=mode)  # must not raise


# ---------------------------------------------------------------------------
# fetch() — single-URL extract
# ---------------------------------------------------------------------------


class TestFetch:
    def test_full_content_mapped_with_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        prov = _make_provider(
            lambda request: _extract_response(
                results=[_row(title=None, full_content="# Page\n\nBody.")]
            ),
        )

        result = prov.fetch("https://example.com/a")

        assert isinstance(result, WebResult)
        assert result.url == "https://example.com/a"
        assert result.title == ""  # null title maps to ""
        assert result.content == "# Page\n\nBody."
        assert result.metadata["provider"] == "parallel"
        assert isinstance(result.fetched_at, datetime)

    def test_publish_date_lands_in_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        prov = _make_provider(
            lambda request: _extract_response(results=[_row(publish_date="2026-05-01")]),
        )

        result = prov.fetch("https://example.com/a")

        assert result.metadata["published_date"] == "2026-05-01"

    def test_excerpts_fallback_when_no_full_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        prov = _make_provider(
            lambda request: _extract_response(results=[_row(full_content=None)]),
        )

        result = prov.fetch("https://example.com/a")

        assert result.content == "Excerpt one.\n\nExcerpt two."
        assert result.title == "Example"
        assert result.metadata["provider"] == "parallel"
        assert "published_date" not in result.metadata

    def test_request_shape_and_auth_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POST {base}/v1/extract, urls==[url], full_content truthy, spec auth header."""
        _pin_dns(monkeypatch, "93.184.216.34")
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return _extract_response(results=[_row(full_content="F")])

        _make_provider(handler).fetch("https://example.com/a")

        request = seen[0]
        assert request.method == "POST"
        assert str(request.url) == "https://api.parallel.ai/v1/extract"
        # Auth per the OpenAPI securitySchemes: apiKey in the x-api-key header,
        # NOT Authorization: Bearer.
        assert request.headers["x-api-key"] == "test-key"
        assert "authorization" not in request.headers
        body = json.loads(request.content)
        assert body["urls"] == ["https://example.com/a"]
        assert body["advanced_settings"]["full_content"] is True

    def test_full_content_max_chars_uses_settings_object(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return _extract_response(results=[_row(full_content="F")])

        _make_provider(handler, full_content_max_chars=5000).fetch("https://example.com/a")

        body = json.loads(seen[0].content)
        assert body["advanced_settings"]["full_content"] == {"max_chars_per_result": 5000}

    def test_extract_error_for_single_url_raises_runtimeerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        error_row = {
            "url": "https://dead.example/page",
            "error_type": "target_unreachable",
            "http_status_code": 503,
            "content": None,
        }
        prov = _make_provider(lambda request: _extract_response(errors=[error_row]))

        with pytest.raises(RuntimeError, match=r"target_unreachable.*503"):
            prov.fetch("https://dead.example/page")


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestSearch:
    def test_maps_results_ordering_metadata_and_request_shape(self) -> None:
        rows = [
            {"url": "https://b.test/x", "title": None, "publish_date": None,
             "excerpts": ["B1", "B2"]},
            {"url": "https://a.test/y", "title": "A title", "publish_date": "2026-01-02",
             "excerpts": ["A1"]},
        ]
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return _search_response(rows)

        results = _make_provider(handler).search("solid state batteries", max_results=7)

        assert len(results) == 2
        assert all(isinstance(r, WebResult) for r in results)
        # API relevance order preserved verbatim (b before a).
        assert [r.url for r in results] == ["https://b.test/x", "https://a.test/y"]
        assert results[0].title == ""  # null title maps to ""
        assert results[0].content == "B1\n\nB2"
        assert results[1].title == "A title"
        assert results[1].metadata["published_date"] == "2026-01-02"
        assert all(r.metadata["provider"] == "parallel" for r in results)

        assert str(seen[0].url) == "https://api.parallel.ai/v1/search"
        body = json.loads(seen[0].content)
        assert body["objective"] == "solid state batteries"
        assert body["search_queries"] == ["solid state batteries"]
        assert body["mode"] == "advanced"
        assert body["advanced_settings"]["max_results"] == 7
        assert body["advanced_settings"]["excerpt_settings"]["max_chars_per_result"] == 2000

    def test_sends_configured_mode_and_excerpt_cap(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return _search_response([])

        _make_provider(handler, mode="turbo", excerpt_max_chars=777).search("q")

        body = json.loads(seen[0].content)
        assert body["mode"] == "turbo"
        assert body["advanced_settings"]["excerpt_settings"]["max_chars_per_result"] == 777


# ---------------------------------------------------------------------------
# fetch_many() — batched extract with partial-failure tolerance
# ---------------------------------------------------------------------------


class TestFetchMany:
    def test_partial_failure_returns_successes_and_records_errors(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        good_row = {
            "url": "https://good.test/a", "title": "Good",
            "publish_date": None, "excerpts": ["G"],
        }
        bad_error = {
            "url": "https://bad.test/b", "error_type": "fetch_failed",
            "http_status_code": 403, "content": None,
        }

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["urls"] == ["https://good.test/a", "https://bad.test/b"]
            return _extract_response(results=[good_row], errors=[bad_error])

        prov = _make_provider(handler)
        with caplog.at_level(logging.WARNING, logger="hyperresearch.web.parallel_provider"):
            results = prov.fetch_many(["https://good.test/a", "https://bad.test/b"])

        assert len(results) == 1
        assert results[0].url == "https://good.test/a"
        assert prov.last_extract_errors == [bad_error]
        assert "https://bad.test/b" in caplog.text
        assert "fetch_failed" in caplog.text

    def test_chunks_requests_over_the_twenty_url_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        urls = [f"https://u{i}.test/page" for i in range(25)]
        chunk_sizes: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            chunk_urls = json.loads(request.content)["urls"]
            chunk_sizes.append(len(chunk_urls))
            return _extract_response(
                results=[
                    {"url": u, "title": None, "publish_date": None, "excerpts": ["c"]}
                    for u in chunk_urls
                ]
            )

        prov = _make_provider(handler)
        results = prov.fetch_many(urls)

        assert chunk_sizes == [20, 5]
        assert len(results) == 25
        assert results[0].url == urls[0]
        assert results[-1].url == urls[-1]
        assert prov.last_extract_errors == []

    def test_duplicate_urls_dedupe_preserving_first_seen_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        seen_chunks: list[list[str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            chunk_urls = json.loads(request.content)["urls"]
            seen_chunks.append(chunk_urls)
            return _extract_response(
                results=[
                    {"url": u, "title": None, "publish_date": None, "excerpts": ["c"]}
                    for u in chunk_urls
                ]
            )

        prov = _make_provider(handler)
        results = prov.fetch_many([
            "https://a.test/1",
            "https://b.test/2",
            "https://a.test/1",  # duplicate of the first URL
        ])

        # One request per unique URL in the chunk body, first-seen order kept.
        assert seen_chunks == [["https://a.test/1", "https://b.test/2"]]
        assert [r.url for r in results] == ["https://a.test/1", "https://b.test/2"]
        assert prov.last_extract_errors == []


# ---------------------------------------------------------------------------
# Error envelopes
# ---------------------------------------------------------------------------


class TestErrorEnvelope:
    @pytest.mark.parametrize(
        ("status", "server_message"),
        [(401, "Invalid API key"), (500, "Internal search failure")],
    )
    def test_envelope_raises_parallel_api_error(
        self,
        status: int,
        server_message: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status,
                json={"type": "error", "error": {"ref_id": "ref_1", "message": server_message}},
            )

        prov = _make_provider(handler)
        with pytest.raises(ParallelApiError) as excinfo:
            prov.fetch("https://example.com/a")

        assert excinfo.value.status_code == status
        assert server_message in str(excinfo.value)
        # Disposition 4: the envelope's ref_id rides along in the message.
        assert "(ref ref_1)" in str(excinfo.value)
        assert isinstance(excinfo.value, RuntimeError)

    def test_non_envelope_body_falls_back_to_raw_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pin_dns(monkeypatch, "93.184.216.34")
        prov = _make_provider(lambda request: httpx.Response(502, text="<html>Bad Gateway</html>"))

        with pytest.raises(ParallelApiError) as excinfo:
            prov.fetch("https://example.com/a")

        assert excinfo.value.status_code == 502
        assert "Bad Gateway" in str(excinfo.value)

    def test_transport_errors_propagate_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Connection/DNS failures are NOT wrapped in ParallelApiError."""
        _pin_dns(monkeypatch, "93.184.216.34")

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        prov = _make_provider(handler)
        with pytest.raises(httpx.TransportError):
            prov.fetch("https://example.com/a")

    @pytest.mark.parametrize(
        ("make_response", "expected_fragment"),
        [
            (lambda: httpx.Response(200, text="<html>not json</html>"), "invalid JSON"),
            (lambda: httpx.Response(200, json=[1, 2]), "non-object"),
        ],
    )
    def test_malformed_200_body_raises_parallel_api_error_with_status_200(
        self,
        make_response: Callable[[], httpx.Response],
        expected_fragment: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Disposition 1: a 200 body that is invalid JSON or a non-object
        surfaces as ParallelApiError(status_code=200), not a raw decode error."""
        _pin_dns(monkeypatch, "93.184.216.34")
        prov = _make_provider(lambda request: make_response())

        with pytest.raises(ParallelApiError) as excinfo:
            prov.fetch("https://example.com/a")

        assert excinfo.value.status_code == 200
        assert expected_fragment in str(excinfo.value)


# ---------------------------------------------------------------------------
# Call-time auth (deliberate delta vs tavily/exa construction-time checks)
# ---------------------------------------------------------------------------


class TestCallTimeAuth:
    def test_construction_succeeds_without_key_but_calls_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
        prov = ParallelProvider(
            _transport=httpx.MockTransport(
                lambda request: pytest.fail("no request may be issued without a key")
            )
        )

        _pin_dns(monkeypatch, "93.184.216.34")
        with pytest.raises(ParallelAuthError, match="PARALLEL_API_KEY"):
            prov.fetch("https://example.com/a")
        with pytest.raises(ParallelAuthError, match="PARALLEL_API_KEY"):
            prov.search("anything")

    def test_parallel_auth_error_is_a_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
        prov = ParallelProvider()

        with pytest.raises(ParallelAuthError) as excinfo:
            prov.search("q")

        assert isinstance(excinfo.value, RuntimeError)


# ---------------------------------------------------------------------------
# SSRF guard integration
# ---------------------------------------------------------------------------


class TestSsrfGuard:
    def test_loopback_fetch_blocked_before_any_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pin_dns(monkeypatch, "127.0.0.1")
        issued: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            issued.append(request)
            return _extract_response()

        prov = _make_provider(handler)
        with pytest.raises(UnsafeUrlError, match="loopback"):
            prov.fetch("http://127.0.0.1/x")

        assert issued == []

    def test_fetch_many_validates_all_urls_before_any_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Numeric-IP hosts only: no DNS stub, so the guard's real address
        # checks decide (1.1.1.1 global, 10.0.0.5 RFC1918) with zero network.
        issued: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            issued.append(request)
            return _extract_response()

        prov = _make_provider(handler)
        with pytest.raises(UnsafeUrlError):
            prov.fetch_many(["https://1.1.1.1/a", "http://10.0.0.5/private"])

        assert issued == []  # all-or-nothing: nothing was requested at all
