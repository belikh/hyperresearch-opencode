"""DeepWiki web provider — Cognition's official MCP server (mcp.deepwiki.com).

DeepWiki (https://deepwiki.com, by Cognition) hosts AI-generated wiki
documentation for public GitHub repositories. The public documentation of
any indexed ``owner/repo`` is available — free, no login, no auth — through
the official MCP server at ``https://mcp.deepwiki.com/mcp`` with three
documented tools:

* ``read_wiki_structure`` — the wiki's table of contents (page list)
* ``read_wiki_contents`` — the FULL wiki text for the repo (one large
  markdown document with ``# Page: <title>`` section separators)
* ``ask_question`` — context-grounded Q&A over the repo (accepts a list
  of up to 10 repos)

This provider speaks the MCP **Streamable HTTP** wire protocol directly
with httpx (a core dependency): one JSON-RPC ``initialize`` request, one
``notifications/initialized`` notification, then the ``tools/call``.
The endpoint is sessionless (no ``mcp-session-id`` header is issued or
required), so each public method opens one short-lived client, performs
the handshake, makes its single tool call, and closes — the same
client-per-call lifecycle as the parallel provider. Responses arrive
SSE-framed (``event: message`` / ``data: {...}``); :func:`_parse_sse`
extracts the JSON-RPC envelope, and a plain-JSON body is also accepted.

URL contract for ``fetch()``: ``https://deepwiki.com/<owner>/<repo>``
(exactly two path segments — the same URL shape as the public site).
Deeper page URLs are rejected with guidance rather than silently
returning the wrong page's content. ``search()`` is not implemented —
DeepWiki exposes no repo-search tool for public mode — and raises
``NotImplementedError`` per the WebProvider protocol; the fallback chain
treats that as a capability skip and tries the next candidate.

No optional-install wrapper applies: httpx is a core dependency. No API
key is required or accepted — the public MCP endpoint is auth-free by
design (Cognition's announcement: "completely free with no login or auth
required").
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from hyperresearch.web._netguard import validate_url_public
from hyperresearch.web.base import WebResult

logger = logging.getLogger(__name__)

# Canonical public endpoint (Cognition's announcement + docs.devin.ai).
DEFAULT_BASE_URL = "https://mcp.deepwiki.com/mcp"

# MCP protocol version we advertise in the initialize handshake. The
# server negotiated "2025-03-26" in the P5-A live probe (serverInfo
# "DeepWiki" 2.14.3), so this is the proven-compatible version.
_MCP_PROTOCOL_VERSION = "2025-03-26"

# The deepwiki.com page separator emitted by read_wiki_contents.
_PAGE_HEADER_RE = re.compile(r"^# Page: (.+)$", re.MULTILINE)

# fetch() accepts exactly this shape: https://deepwiki.com/<owner>/<repo>
_REPO_URL_RE = re.compile(
    r"^https?://(?:www\.)?deepwiki\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$"
)


class DeepwikiApiError(RuntimeError):
    """A failed exchange with the DeepWiki MCP server.

    Carries the HTTP status in ``.status_code`` (when the failure was an
    HTTP-level one) and the JSON-RPC error code in ``.rpc_code`` (when the
    server answered with a JSON-RPC error object). Mirrors
    :class:`~hyperresearch.web.parallel_provider.ParallelApiError` so the
    fallback chain's fall-through classification in
    :func:`hyperresearch.web.base._is_fall_through_error` recognises it by
    exact type + status.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        rpc_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.rpc_code = rpc_code


def _parse_sse(text: str) -> list[dict[str, Any]]:
    """Extract every JSON object carried in an SSE-framed response body.

    DeepWiki answers Streamable-HTTP requests with ``event: message`` /
    ``data: {...}`` frames. Robust to both the SSE framing and a plain
    JSON body (a single ``data:`` line or an unframed document), so a
    future server that replies application/json keeps working.
    """
    if not text:
        return []
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data: "):
            data_lines.append(line[len("data: ") :])
    if not data_lines:
        # Plain-JSON body (no SSE framing) — accept it whole.
        return [_plain_json(text)]
    out: list[dict[str, Any]] = []
    for chunk in data_lines:
        obj = _plain_json(chunk)
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _plain_json(text: str) -> Any:
    import json

    try:
        return json.loads(text)
    except ValueError:
        return None


def split_wiki_pages(text: str) -> list[tuple[str, str]]:
    """Split a ``read_wiki_contents`` dump into ``(title, body)`` pages.

    The dump format (verified live against langchain-ai/openwiki,
    530KB, 2026-08) is a sequence of sections, each introduced by a
    ``# Page: <title>`` heading. Text before the first such heading (the
    empty case) is discarded. Bodies keep the heading's following content
    verbatim, with the ``# Page:`` line itself reattached so every page
    remains a self-contained markdown document.

    Used by the ``hpr repo wiki`` CLI verb to write one vault note per
    wiki page (per-page summaries, per-page claim extraction, wiki-links
    between pages) instead of one monolithic note.
    """
    matches = list(_PAGE_HEADER_RE.finditer(text))
    if not matches:
        return []
    pages: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group(1).strip()
        body = text[start:end].rstrip() + "\n"
        pages.append((title, body))
    return pages


class DeepwikiProvider:
    """Web provider backed by the official DeepWiki MCP server.

    ``fetch()`` maps ``https://deepwiki.com/owner/repo`` to one
    ``read_wiki_contents`` call and returns the full wiki dump as a single
    :class:`WebResult` (these are long sources by nature — the width-sweep
    long-source delegation rule applies). ``search()`` raises
    ``NotImplementedError`` (no public repo-search tool exists).

    DELIBERATE no-auth: the public endpoint requires neither key nor
    login. ``list_available_repos`` / ``generate_wiki`` are private-mode
    tools and are deliberately NOT wrapped here.
    """

    name = "deepwiki"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,
        # Test-only seam: an httpx.BaseTransport (e.g. MockTransport) used
        # when building each client so tests run with zero network.
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = _transport

    # ------------------------------------------------------------------
    # MCP Streamable-HTTP plumbing
    # ------------------------------------------------------------------

    def _rpc_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        request_id: int = 1,
    ) -> Any:
        """One tool call through the sessionless Streamable-HTTP handshake.

        Opens a short-lived client, validates the MCP endpoint with the
        SSRF guard (the one network target this provider ever touches),
        performs initialize + initialized-notification, then issues the
        ``tools/call`` and returns the tool result's ``content`` payload.

        Raises:
            DeepwikiApiError: HTTP non-200, JSON-RPC error object, a
                malformed (non-object) response, or an ``isError`` tool
                result (the server's own error channel — e.g. pydantic
                argument validation, as observed live).
            httpx.TransportError: propagated untouched (the fallback
                chain's documented fall-through signal).
        """
        validate_url_public(self._base_url)  # SSRF guard BEFORE any request
        headers = {"Accept": "application/json, text/event-stream"}
        with httpx.Client(
            base_url="",
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            init = client.post(
                self._base_url,
                json={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": _MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {
                            "name": "hyperresearch",
                            "version": "0.10.0.post1",
                        },
                    },
                },
                headers=headers,
            )
            self._check_http(init)
            client.post(
                self._base_url,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers,
            )
            call = client.post(
                self._base_url,
                json={
                    "jsonrpc": "2.0",
                    "id": request_id + 1,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                },
                headers=headers,
            )
            self._check_http(call)
        return self._tool_result(call, tool_name)

    def _check_http(self, resp: httpx.Response) -> None:
        if resp.status_code != 200:
            raise DeepwikiApiError(
                f"DeepWiki MCP returned HTTP {resp.status_code}: "
                f"{resp.text.strip()[:300]}",
                status_code=resp.status_code,
            )

    def _tool_result(self, resp: httpx.Response, tool_name: str) -> Any:
        """Extract the JSON-RPC result -> tool result from one response."""
        # Plain JSON body first (fast path / future server mode); the SSE
        # frames are parsed only when the body isn't a bare JSON document.
        envelope: Any = None
        try:
            envelope = resp.json()
        except ValueError:
            messages = _parse_sse(resp.text)
            # A JSON-RPC ERROR response has no "result" member — pick the
            # first response envelope (result OR error), never skip one.
            envelope = next(
                (
                    m
                    for m in messages
                    if isinstance(m, dict) and ("result" in m or "error" in m)
                ),
                None,
            )
        if not isinstance(envelope, dict) or ("result" not in envelope and "error" not in envelope):
            raise DeepwikiApiError(
                f"DeepWiki MCP returned a malformed response for {tool_name} "
                f"(no JSON-RPC result): {resp.text.strip()[:300]}"
            )
        if envelope.get("error") is not None:
            err = envelope["error"]
            message = (
                err.get("message", "unknown JSON-RPC error") if isinstance(err, dict) else str(err)
            )
            code = err.get("code") if isinstance(err, dict) else None
            raise DeepwikiApiError(
                f"DeepWiki MCP JSON-RPC error calling {tool_name}: {message}",
                rpc_code=code if isinstance(code, int) else None,
            )
        result = envelope["result"]
        if not isinstance(result, dict):
            raise DeepwikiApiError(
                f"DeepWiki MCP returned a non-object result for {tool_name}",
            )
        if result.get("isError"):
            # The server's own error channel (observed live: pydantic
            # argument-validation text). Surface it — a caller bug must
            # not masquerade as content.
            texts = [
                c.get("text", "") for c in (result.get("content") or []) if isinstance(c, dict)
            ]
            raise DeepwikiApiError(
                f"DeepWiki tool {tool_name} returned isError: "
                + (" ".join(t for t in texts if t) or "unknown error")[:500]
            )
        return result

    @staticmethod
    def _text_content(result: Any, tool_name: str) -> str:
        """Concatenate the text blocks of a tools/call result."""
        if not isinstance(result, dict):
            raise DeepwikiApiError(f"DeepWiki tool {tool_name} returned no result")
        parts: list[str] = []
        for block in result.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Public provider surface
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> WebResult:
        """Fetch a repo's full DeepWiki as one WebResult.

        ``url`` must be ``https://deepwiki.com/<owner>/<repo>`` — the
        public-site URL shape. Deeper page URLs are rejected with
        guidance (read_wiki_contents returns the WHOLE wiki; silently
        serving it for a page-specific URL would mislead the caller).
        """
        m = _REPO_URL_RE.match(url.strip())
        if not m:
            raise ValueError(
                f"deepwiki provider fetches https://deepwiki.com/<owner>/<repo> "
                f"URLs only; got {url!r}. (For a local checkout use "
                "`hpr repo map`; to ask a question use `hpr repo ask`.)"
            )
        owner, repo = m.group(1), m.group(2)
        repo_name = f"{owner}/{repo}"
        result = self._rpc_call("read_wiki_contents", {"repoName": repo_name})
        content = self._text_content(result, "read_wiki_contents")
        if not content.strip():
            raise DeepwikiApiError(
                f"DeepWiki returned empty contents for {repo_name} — the repo "
                "may not be indexed. Submit it at https://deepwiki.com, or "
                "analyse a local checkout with `hpr repo map`."
            )
        return WebResult(
            url=url,
            title=f"DeepWiki: {repo_name}",
            content=content,
            fetched_at=datetime.now(UTC),
            metadata={"provider": "deepwiki", "repo": repo_name},
        )

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """Not supported — DeepWiki exposes no public repo-search tool.

        Raises NotImplementedError per the WebProvider protocol so the
        fallback chain skips this candidate for search-shaped calls and
        callers get an actionable message.
        """
        raise NotImplementedError(
            "The deepwiki provider does not search. Fetch a repo's wiki "
            "directly: https://deepwiki.com/<owner>/<repo> — or use "
            "`hpr repo ask <owner/repo> <question>` for grounded Q&A."
        )

    # ------------------------------------------------------------------
    # DeepWiki-specific surface (used by the `hpr repo` CLI group)
    # ------------------------------------------------------------------

    def read_structure(self, repo_name: str) -> str:
        """``read_wiki_structure`` — the wiki's page list as text."""
        result = self._rpc_call("read_wiki_structure", {"repoName": repo_name})
        return self._text_content(result, "read_wiki_structure")

    def read_contents(self, repo_name: str) -> str:
        """``read_wiki_contents`` — the full wiki text."""
        result = self._rpc_call("read_wiki_contents", {"repoName": repo_name})
        return self._text_content(result, "read_wiki_contents")

    def ask_question(self, repo_names: list[str], question: str) -> str:
        """``ask_question`` — grounded Q&A over up to 10 repos.

        ``repo_names`` is a list (the tool schema accepts one string or a
        list; the list form is canonical here because multi-repo
        comparison questions are the interesting case).
        """
        if not 1 <= len(repo_names) <= 10:
            raise ValueError(
                f"ask_question accepts 1-10 repos; got {len(repo_names)}"
            )
        result = self._rpc_call(
            "ask_question",
            {"repoName": repo_names[0] if len(repo_names) == 1 else repo_names,
             "question": question},
        )
        return self._text_content(result, "ask_question")
