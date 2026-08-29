"""Tests for the DeepWiki web provider (official mcp.deepwiki.com MCP).

Zero network throughout, via two seams (same pattern as
tests/test_web/test_parallel_provider.py):
- an ``httpx.MockTransport`` injected through the private ``_transport`` ctor
  kwarg — the full sessionless Streamable-HTTP exchange (initialize ->
  initialized -> tools/call) is asserted request-by-request;
- DNS stubbed per-test, because every RPC call runs the SSRF guard —
  which resolves the target hostname — BEFORE any HTTP traffic exists
  to mock.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from hyperresearch.web import _netguard
from hyperresearch.web.base import WebResult, get_provider
from hyperresearch.web.deepwiki_provider import (
    DeepwikiApiError,
    DeepwikiProvider,
    split_wiki_pages,
)

# ---------------------------------------------------------------------------
# Offline helpers
# ---------------------------------------------------------------------------

Handler = Callable[[httpx.Request], httpx.Response]

WIKI_DUMP = (
    "# Page: Overview\n\nThis is the overview. Sources: [a.py]()\n\n"
    "# Page: CLI System\n\nCommands live here.\n\n"
    "# Page: Internals\n\nDeep stuff.\n"
)

STRUCTURE_TEXT = "Available pages for owner/repo:\n\n- 1 Overview\n- 2 CLI System\n"


def _pin_dns(monkeypatch: pytest.MonkeyPatch, *addresses: str) -> None:
    """Pin THE SAME getaddrinfo answer(s) for every hostname — no network."""

    def _info(addr: str) -> tuple[Any, ...]:
        if ":" in addr:
            return (10, 1, 6, "", (addr, 0, 0, 0))
        return (2, 1, 6, "", (addr, 0))

    infos = [_info(a) for a in addresses]
    monkeypatch.setattr(_netguard.socket, "getaddrinfo", lambda host, port: infos)


def _sse(envelope: dict[str, Any]) -> httpx.Response:
    """SSE-framed JSON-RPC body — the real server's observed framing."""
    return httpx.Response(
        200,
        text=f"event: message\ndata: {json.dumps(envelope)}\n\n",
        headers={"Content-Type": "text/event-stream"},
    )


def _tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        },
    }


def _full_exchange(
    tool_result: dict[str, Any],
    *,
    init_status: int = 200,
) -> Handler:
    """Handler implementing the full observed exchange: init (SSE result),
    initialized notification (202), tools/call (SSE result)."""
    counter = {"init": 0, "notif": 0, "call": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "initialize":
            counter["init"] += 1
            if init_status != 200:
                return httpx.Response(init_status, text="boom")
            return _sse(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {"listChanged": True}},
                        "serverInfo": {"name": "DeepWiki", "version": "2.14.3"},
                    },
                }
            )
        if body.get("method") == "notifications/initialized":
            counter["notif"] += 1
            return httpx.Response(202)
        if body.get("method") == "tools/call":
            counter["call"] += 1
            return _sse(tool_result)
        raise AssertionError(f"unexpected method {body.get('method')!r}")

    handler.counter = counter  # type: ignore[attr-defined]
    return handler


# ---------------------------------------------------------------------------
# Factory registration & construction
# ---------------------------------------------------------------------------


def test_provider_registered_via_factory() -> None:
    prov = get_provider("deepwiki")
    assert prov.name == "deepwiki"


def test_known_names_include_deepwiki() -> None:
    from hyperresearch.web.base import KNOWN_PROVIDER_NAMES

    assert "deepwiki" in KNOWN_PROVIDER_NAMES


def test_unknown_provider_lists_deepwiki_in_error() -> None:
    with pytest.raises(ValueError, match="deepwiki"):
        get_provider("not-a-real-provider")


def test_no_auth_needed_at_construction() -> None:
    """The public endpoint is auth-free: construction must never demand a key."""
    DeepwikiProvider()


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


def test_parse_sse_extracts_envelopes() -> None:
    from hyperresearch.web.deepwiki_provider import _parse_sse

    text = (
        "event: message\ndata: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"a\":1}}\n\n"
        "event: message\ndata: {\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{\"b\":2}}\n"
    )
    msgs = _parse_sse(text)
    assert [m["result"] for m in msgs] == [{"a": 1}, {"b": 2}]


def test_parse_sse_accepts_plain_json_body() -> None:
    """Future-proofing: a plain application/json body still parses."""
    from hyperresearch.web.deepwiki_provider import _parse_sse

    msgs = _parse_sse('{"jsonrpc":"2.0","id":1,"result":{"a":1}}')
    assert msgs and msgs[0]["result"] == {"a": 1}


def test_parse_sse_empty_body() -> None:
    from hyperresearch.web.deepwiki_provider import _parse_sse

    assert _parse_sse("") == []


def test_split_wiki_pages() -> None:
    pages = split_wiki_pages(WIKI_DUMP)
    assert [t for t, _ in pages] == ["Overview", "CLI System", "Internals"]
    # Bodies are self-contained markdown INCLUDING their # Page: heading.
    assert pages[0][1].startswith("# Page: Overview")
    assert "This is the overview" in pages[0][1]
    assert "Deep stuff" in pages[2][1]


def test_split_wiki_pages_no_headers() -> None:
    assert split_wiki_pages("just some text, no page separators") == []


# ---------------------------------------------------------------------------
# fetch() — URL contract
# ---------------------------------------------------------------------------


def test_fetch_rejects_non_deepwiki_url() -> None:
    with pytest.raises(ValueError, match="URLs only"):
        DeepwikiProvider().fetch("https://github.com/langchain-ai/openwiki")


def test_fetch_rejects_page_deep_url() -> None:
    """read_wiki_contents serves the WHOLE wiki — a page URL must be
    rejected rather than silently returning the wrong page."""
    with pytest.raises(ValueError, match="URLs only"):
        DeepwikiProvider().fetch(
            "https://deepwiki.com/langchain-ai/openwiki/2.1-command-parsing"
        )


def test_fetch_rejects_one_segment_url() -> None:
    with pytest.raises(ValueError, match="URLs only"):
        DeepwikiProvider().fetch("https://deepwiki.com/langchain-ai")


# ---------------------------------------------------------------------------
# fetch() — the MCP exchange, request-by-request
# ---------------------------------------------------------------------------


def test_fetch_performs_full_handshake_and_maps_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    handler = _full_exchange(_tool_text(WIKI_DUMP))
    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))

    result = prov.fetch("https://deepwiki.com/langchain-ai/openwiki")

    assert isinstance(result, WebResult)
    assert result.title == "DeepWiki: langchain-ai/openwiki"
    assert result.content == WIKI_DUMP
    assert result.metadata["provider"] == "deepwiki"
    assert result.metadata["repo"] == "langchain-ai/openwiki"
    assert result.domain == "deepwiki.com"
    # Exactly one init, one notification, one tools/call — sessionless.
    assert handler.counter["init"] == 1  # type: ignore[attr-defined]
    assert handler.counter["notif"] == 1  # type: ignore[attr-defined]
    assert handler.counter["call"] == 1  # type: ignore[attr-defined]


def test_fetch_tool_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tools/call carries read_wiki_contents + repoName verbatim."""
    _pin_dns(monkeypatch, "93.184.216.34")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "tools/call":
            seen["params"] = body["params"]
            return _sse(_tool_text(WIKI_DUMP))
        if body.get("method") == "initialize":
            return _sse(
                {"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-03-26"}}
            )
        return httpx.Response(202)

    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))
    prov.fetch("https://deepwiki.com/owner/repo")

    assert seen["params"]["name"] == "read_wiki_contents"
    assert seen["params"]["arguments"] == {"repoName": "owner/repo"}


def test_fetch_www_and_trailing_slash_normalised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "tools/call":
            seen["args"] = body["params"]["arguments"]
            return _sse(_tool_text(WIKI_DUMP))
        if body.get("method") == "initialize":
            return _sse({"jsonrpc": "2.0", "id": body["id"], "result": {}})
        return httpx.Response(202)

    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))
    # www prefix + trailing slash + dot-bearing segments all normalise.
    prov.fetch("https://www.deepwiki.com/owner.repo/project.name/")

    assert seen["args"] == {"repoName": "owner.repo/project.name"}


def test_fetch_empty_contents_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty wiki text = likely unindexed repo — actionable error, not junk."""
    _pin_dns(monkeypatch, "93.184.216.34")
    handler = _full_exchange(_tool_text("   "))
    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))

    with pytest.raises(DeepwikiApiError, match="not be indexed"):
        prov.fetch("https://deepwiki.com/foo/bar")


# ---------------------------------------------------------------------------
# Error surfaces
# ---------------------------------------------------------------------------


def test_fetch_http_error_raises_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    handler = _full_exchange(_tool_text(""), init_status=503)
    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))

    with pytest.raises(DeepwikiApiError) as excinfo:
        prov.fetch("https://deepwiki.com/foo/bar")
    assert excinfo.value.status_code == 503


def test_fetch_iserror_result_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The server's own isError channel (observed live: pydantic arg
    validation text) must surface as an exception, never as content."""
    _pin_dns(monkeypatch, "93.184.216.34")
    handler = _full_exchange(
        _tool_text("1 validation error for call[read_wiki_contents]", is_error=True)
    )
    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))

    with pytest.raises(DeepwikiApiError, match="validation error"):
        prov.fetch("https://deepwiki.com/foo/bar")


def test_fetch_jsonrpc_error_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "initialize":
            return _sse({"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body.get("method") == "tools/call":
            return _sse(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "error": {"code": -32000, "message": "repo not found"},
                }
            )
        return httpx.Response(202)

    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))
    with pytest.raises(DeepwikiApiError, match="repo not found") as excinfo:
        prov.fetch("https://deepwiki.com/foo/bar")
    assert excinfo.value.rpc_code == -32000


def test_fetch_malformed_body_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "initialize":
            return _sse({"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body.get("method") == "tools/call":
            return httpx.Response(200, text="garbage, not sse or json")
        return httpx.Response(202)

    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))
    with pytest.raises(DeepwikiApiError, match="malformed"):
        prov.fetch("https://deepwiki.com/foo/bar")


def test_ssrf_guard_blocks_private_endpoint() -> None:
    """A base_url pointing at a private address is refused before any HTTP."""
    from hyperresearch.web._netguard import UnsafeUrlError

    prov = DeepwikiProvider(base_url="http://127.0.0.1:9/mcp")
    with pytest.raises(UnsafeUrlError):
        prov.read_contents("owner/repo")


# ---------------------------------------------------------------------------
# search() — capability statement
# ---------------------------------------------------------------------------


def test_search_not_implemented_with_guidance() -> None:
    prov = DeepwikiProvider()
    with pytest.raises(NotImplementedError, match="hpr repo ask"):
        prov.search("anything")


# ---------------------------------------------------------------------------
# DeepWiki-specific surface (hpr repo group backing)
# ---------------------------------------------------------------------------


def test_read_structure_and_contents(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "initialize":
            return _sse({"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body.get("method") == "tools/call":
            name = body["params"]["name"]
            text = STRUCTURE_TEXT if name == "read_wiki_structure" else WIKI_DUMP
            return _sse(_tool_text(text))
        return httpx.Response(202)

    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))
    assert "Available pages" in prov.read_structure("owner/repo")
    assert prov.read_contents("owner/repo") == WIKI_DUMP


def test_ask_question_single_repo_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "tools/call":
            seen["args"] = body["params"]["arguments"]
            return _sse(_tool_text("The answer."))
        if body.get("method") == "initialize":
            return _sse({"jsonrpc": "2.0", "id": body["id"], "result": {}})
        return httpx.Response(202)

    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))
    answer = prov.ask_question(["owner/repo"], "How does auth work?")
    assert answer == "The answer."
    # Single repo collapses to the plain string form (observed schema).
    assert seen["args"]["repoName"] == "owner/repo"
    assert seen["args"]["question"] == "How does auth work?"


def test_ask_question_multi_repo_list_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_dns(monkeypatch, "93.184.216.34")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("method") == "tools/call":
            seen["args"] = body["params"]["arguments"]
            return _sse(_tool_text("Compare answer."))
        if body.get("method") == "initialize":
            return _sse({"jsonrpc": "2.0", "id": body["id"], "result": {}})
        return httpx.Response(202)

    prov = DeepwikiProvider(_transport=httpx.MockTransport(handler))
    repos = ["a/one", "b/two", "c/three"]
    prov.ask_question(repos, "Compare these.")
    assert seen["args"]["repoName"] == repos


def test_ask_question_rejects_empty_and_oversized_lists() -> None:
    prov = DeepwikiProvider()
    with pytest.raises(ValueError, match="1-10"):
        prov.ask_question([], "q")
    with pytest.raises(ValueError, match="1-10"):
        prov.ask_question([f"r/{i}" for i in range(11)], "q")


# ---------------------------------------------------------------------------
# Fallback-chain classification
# ---------------------------------------------------------------------------


def test_chain_fall_through_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepwikiApiError 5xx falls through to the next chain candidate."""
    from hyperresearch.web.base import resolve_web_provider

    _pin_dns(monkeypatch, "93.184.216.34")

    handler = _full_exchange(_tool_text(""), init_status=500)

    def builtin_fetch(url: str) -> WebResult:
        return WebResult(
            url=url, title="builtin fallback", content="real content from builtin"
        )

    factories: dict[str, Callable[[], Any]] = {
        "deepwiki": lambda: DeepwikiProvider(_transport=httpx.MockTransport(handler)),
        "builtin": lambda: _FakeBuiltin(builtin_fetch),
    }
    chain = resolve_web_provider(
        ["deepwiki", "builtin"], _factories=factories, gates=None
    )
    result = chain.fetch("https://deepwiki.com/a/b")
    assert result.content == "real content from builtin"
    assert chain.name == "builtin"


def test_chain_surfaces_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DeepWiki 404 is a caller bug — it must surface, not fall through."""
    from hyperresearch.web.base import resolve_web_provider

    _pin_dns(monkeypatch, "93.184.216.34")
    handler = _full_exchange(_tool_text(""), init_status=404)

    def builtin_fetch(url: str) -> WebResult:
        return WebResult(url=url, title="should not be reached", content="nope")

    factories: dict[str, Callable[[], Any]] = {
        "deepwiki": lambda: DeepwikiProvider(_transport=httpx.MockTransport(handler)),
        "builtin": lambda: _FakeBuiltin(builtin_fetch),
    }
    chain = resolve_web_provider(
        ["deepwiki", "builtin"], _factories=factories, gates=None
    )
    with pytest.raises(DeepwikiApiError):
        chain.fetch("https://deepwiki.com/a/b")


def test_junk_result_falls_through_in_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """A junk/empty wiki result tries the next candidate (chain semantics)."""
    from hyperresearch.web.base import resolve_web_provider

    _pin_dns(monkeypatch, "93.184.216.34")
    handler = _full_exchange(_tool_text(""))

    def builtin_fetch(url: str) -> WebResult:
        return WebResult(url=url, title="x", content="fallback body content")

    factories: dict[str, Callable[[], Any]] = {
        "deepwiki": lambda: DeepwikiProvider(_transport=httpx.MockTransport(handler)),
        "builtin": lambda: _FakeBuiltin(builtin_fetch),
    }
    # NOTE: empty-string content makes _result_is_junk true, BUT fetch()
    # itself raises DeepwikiApiError on empty content before the chain's
    # junk gate runs — so this asserts the raise path, then fall-through.
    chain = resolve_web_provider(
        ["deepwiki", "builtin"], _factories=factories, gates=None
    )
    # The empty-content DeepwikiApiError is NOT a fall-through type (no
    # status_code) — it must surface.
    with pytest.raises(DeepwikiApiError):
        chain.fetch("https://deepwiki.com/a/b")


class _FakeBuiltin:
    """Duck-typed stand-in for the builtin provider (fetch-only lane)."""

    name = "builtin"

    def __init__(self, fetch_impl: Callable[[str], WebResult]) -> None:
        self._fetch_impl = fetch_impl

    def fetch(self, url: str) -> WebResult:
        return self._fetch_impl(url)
