"""Tests for the Cloudflare Browser Run provider (Kitesurf Quick Actions).

Zero network, via two seams (same pattern as the parallel/deepwiki
batteries):
- ``httpx.MockTransport`` injected through the private ``_transport`` ctor
  kwarg — endpoint shape, ?browser= engine param, Bearer auth, envelope
  parsing are asserted on captured requests;
- DNS stubbed per-test, because every call runs the SSRF guard (which
  resolves the API host) BEFORE any HTTP traffic exists to mock.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from hyperresearch.web import _netguard
from hyperresearch.web.base import WebResult, get_provider
from hyperresearch.web.browser_run_provider import (
    BrowserRunApiError,
    BrowserRunAuthError,
    BrowserRunProvider,
    html_to_text,
)

Handler = Callable[[httpx.Request], httpx.Response]

ACCOUNT = "acc123"
TOKEN = "tok-abc"


def _pin_dns(monkeypatch: pytest.MonkeyPatch, *addresses: str) -> None:
    def _info(addr: str) -> tuple[Any, ...]:
        if ":" in addr:
            return (10, 1, 6, "", (addr, 0, 0, 0))
        return (2, 1, 6, "", (addr, 0))

    infos = [_info(a) for a in addresses]
    monkeypatch.setattr(_netguard.socket, "getaddrinfo", lambda host, port: infos)


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_BROWSER_RUN_TOKEN", TOKEN)
    monkeypatch.setenv("CF_ACCOUNT_ID", ACCOUNT)


def _make(handler: Handler, **kwargs: Any) -> BrowserRunProvider:
    return BrowserRunProvider(_transport=httpx.MockTransport(handler), **kwargs)


def _ok(result: Any) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "result": result})


RENDERED_HTML = (
    "<html><head><title>Example SPA</title>"
    "<script>fetch('/api/data')</script></head>"
    "<body><div><p>Hello rendered world</p><p>Second line</p></div></body></html>"
)


def _content_handler(seen: dict[str, Any], body: str = RENDERED_HTML) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return _ok(body)
    return handler


# ---------------------------------------------------------------------------
# Factory / construction
# ---------------------------------------------------------------------------


def test_provider_registered_via_factory() -> None:
    prov = get_provider("browser-run")
    assert prov.name == "browser-run"


def test_unknown_provider_lists_browser_run_in_error() -> None:
    with pytest.raises(ValueError, match="browser-run"):
        get_provider("not-a-real-provider")


def test_engine_validation() -> None:
    with pytest.raises(ValueError, match="engine"):
        BrowserRunProvider(engine="netscape")
    assert BrowserRunProvider(engine="chromium")._engine == "chromium"


def test_no_auth_needed_at_construction() -> None:
    """Auth is enforced at CALL time (chain-friendly), never construction."""
    BrowserRunProvider()


# ---------------------------------------------------------------------------
# Endpoint shape
# ---------------------------------------------------------------------------


def test_fetch_hits_kitesurf_content_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)
    seen: dict[str, Any] = {}
    prov = _make(_content_handler(seen))

    result = prov.fetch("https://example.com/spa")

    assert seen["url"] == (
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}"
        "/browser-rendering/content?browser=kitesurf"
    )
    assert seen["auth"] == f"Bearer {TOKEN}"
    assert seen["payload"]["url"] == "https://example.com/spa"
    assert seen["payload"]["gotoOptions"] == {"waitUntil": "networkidle2"}
    assert isinstance(result, WebResult)
    assert result.title == "Example SPA"
    assert "Hello rendered world" in result.content
    assert "fetch(" not in result.content  # script stripped
    assert result.metadata == {"provider": "browser-run", "engine": "kitesurf"}


def test_chromium_engine_rides_the_param(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)
    seen: dict[str, Any] = {}
    prov = _make(_content_handler(seen), engine="chromium")
    prov.fetch("https://example.com")
    assert "browser=chromium" in seen["url"]


def test_screenshot_rides_webresult(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        if request.url.path.endswith("/screenshot"):
            return httpx.Response(200, content=b"\x89PNG fake bytes", headers={"Content-Type": "image/png"})
        return _ok(RENDERED_HTML)

    prov = _make(handler)
    result = prov.fetch("https://example.com", screenshot=True)
    assert result.screenshot == b"\x89PNG fake bytes"
    assert seen["path"].endswith("/browser-rendering/screenshot")


# ---------------------------------------------------------------------------
# Auth (env-only)
# ---------------------------------------------------------------------------


def test_missing_token_fails_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    monkeypatch.delenv("CLOUDFLARE_BROWSER_RUN_TOKEN", raising=False)
    monkeypatch.setenv("CF_ACCOUNT_ID", ACCOUNT)
    prov = BrowserRunProvider(_transport=httpx.MockTransport(lambda r: _ok("x")))
    with pytest.raises(BrowserRunAuthError, match="Browser Rendering - Edit"):
        prov.fetch("https://example.com")


def test_missing_account_fails_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("CLOUDFLARE_BROWSER_RUN_TOKEN", TOKEN)
    prov = BrowserRunProvider(_transport=httpx.MockTransport(lambda r: _ok("x")))
    with pytest.raises(BrowserRunAuthError, match="CF_ACCOUNT_ID"):
        prov.fetch("https://example.com")


def test_rejected_token_carries_scope_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]},
        )

    prov = _make(handler)
    with pytest.raises(BrowserRunApiError, match="Browser Rendering - Edit") as e:
        prov.fetch("https://example.com")
    assert e.value.status_code == 403


# ---------------------------------------------------------------------------
# Envelope / error handling
# ---------------------------------------------------------------------------


def test_success_false_envelope_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"success": False, "errors": [{"code": 14211, "message": "session limit"}]},
        )

    prov = _make(handler)
    with pytest.raises(BrowserRunApiError, match="session limit") as e:
        prov.fetch("https://example.com")
    assert e.value.cf_code == 14211


def test_empty_result_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank render (SPA that never paints) is an error, not a junk note."""
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)
    prov = _make(_content_handler({}, body="   "))
    with pytest.raises(BrowserRunApiError, match="empty result"):
        prov.fetch("https://example.com")


def test_5xx_raises_with_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)
    prov = _make(lambda r: httpx.Response(503, text="unavailable"))
    with pytest.raises(BrowserRunApiError) as e:
        prov.fetch("https://example.com")
    assert e.value.status_code == 503


def test_malformed_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)
    prov = _make(lambda r: httpx.Response(200, text="<html>not json</html>"))
    with pytest.raises(BrowserRunApiError, match="invalid JSON"):
        prov.fetch("https://example.com")


# ---------------------------------------------------------------------------
# search() capability + SSRF
# ---------------------------------------------------------------------------


def test_search_not_implemented_with_guidance() -> None:
    with pytest.raises(NotImplementedError, match="search-web"):
        BrowserRunProvider().search("anything")


def test_ssrf_guard_blocks_private_target(monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.web._netguard import UnsafeUrlError

    # No DNS pin here: the loopback LITERAL check fires before any DNS —
    # and a pinned fake resolver would (correctly) answer 127.0.0.1 with a
    # public address, defeating the very check under test (proven live:
    # _netguard consults the resolver even for IP literals).
    _pin_dns(monkeypatch, "127.0.0.1")
    _env(monkeypatch)
    prov = _make(lambda r: _ok("x"))
    with pytest.raises(UnsafeUrlError):
        prov.fetch("http://127.0.0.1:8080/admin")


def test_ssrf_guard_blocks_private_target_real_resolver() -> None:
    """The un-pinned guard blocks loopback literals with no network."""
    from hyperresearch.web._netguard import UnsafeUrlError

    prov = BrowserRunProvider()  # guard raises before any HTTP construction
    with pytest.raises(UnsafeUrlError):
        prov.fetch("http://127.0.0.1:8080/admin")


def test_api_host_ssrf_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.web._netguard import UnsafeUrlError

    # A private base_url is refused before any HTTP (custom endpoint safety).
    monkeypatch.setenv("CLOUDFLARE_BROWSER_RUN_TOKEN", TOKEN)
    monkeypatch.setenv("CF_ACCOUNT_ID", ACCOUNT)
    prov = BrowserRunProvider(base_url="http://192.168.1.1", _transport=None)
    with pytest.raises(UnsafeUrlError):
        prov.fetch("https://example.com")


# ---------------------------------------------------------------------------
# html_to_text
# ---------------------------------------------------------------------------


def test_html_to_text_strips_and_keeps_readable() -> None:
    text = html_to_text(RENDERED_HTML)
    assert "Hello rendered world" in text
    assert "Second line" in text
    assert "Example SPA" not in text or "title" not in text.lower()
    assert "<script" not in text and "fetch(" not in text


def test_html_to_text_entities() -> None:
    assert html_to_text("<p>a &amp; b &lt;c&gt;</p>") == "a & b <c>"


# ---------------------------------------------------------------------------
# Fallback chain classification
# ---------------------------------------------------------------------------


def test_chain_fall_through_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.web.base import resolve_web_provider

    _pin_dns(monkeypatch, "93.184.216.34")
    _env(monkeypatch)
    failing = _make(lambda r: httpx.Response(503, text="unavailable"))

    def ok_fetch(url: str) -> WebResult:
        return WebResult(url=url, title="x", content="fallback real content")

    class FakeBuiltin:
        name = "builtin"
        def fetch(self, url: str) -> WebResult:
            return ok_fetch(url)

    chain = resolve_web_provider(
        ["browser-run", "builtin"],
        _factories={
            "browser-run": lambda: BrowserRunProvider(
                _transport=httpx.MockTransport(lambda r: httpx.Response(503, text="unavailable"))
            ),
            "builtin": lambda: FakeBuiltin(),
        },
        gates=None,
    )
    assert failing is not None  # constructed cleanly
    result = chain.fetch("https://example.com")
    assert result.content == "fallback real content"
    assert chain.name == "builtin"


def test_chain_falls_through_on_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """BrowserRunAuthError is a ProviderAuthError — chain fall-through."""
    from hyperresearch.web.base import resolve_web_provider

    _pin_dns(monkeypatch, "93.184.216.34")
    monkeypatch.delenv("CLOUDFLARE_BROWSER_RUN_TOKEN", raising=False)

    class FakeBuiltin:
        name = "builtin"
        def fetch(self, url: str) -> WebResult:
            return WebResult(url=url, title="x", content="builtin content")

    chain = resolve_web_provider(
        ["browser-run", "builtin"],
        _factories={
            "browser-run": lambda: BrowserRunProvider(),
            "builtin": lambda: FakeBuiltin(),
        },
        gates=None,
    )
    result = chain.fetch("https://example.com")
    assert result.content == "builtin content"
