"""Cloudflare Browser Run web provider — Quick Actions with the Kitesurf engine.

Cloudflare Browser Run (https://developers.cloudflare.com/browser-run/,
formerly Browser Rendering) executes headless browser tasks in Cloudflare's
isolates — nothing runs locally. **Kitesurf** is its agent-first engine: a
stateless browser built on Workers/Blitz/Stylo/Boa-WASM, reachable by adding
``browser=kitesurf`` to any Quick Action endpoint, using 3-7x less CPU and
memory than the Chromium flavour for agentic extraction. This provider
implements the **Quick Actions REST lane** (issue #2's v1 depth):

* ``fetch()`` → ``POST /browser-rendering/content?browser=kitesurf`` — fully
  rendered HTML after JS execution, then text-extracted into a WebResult.
* ``fetch()`` with ``screenshot=True`` → the ``/screenshot`` quick action
  (binary PNG) carried on ``WebResult.screenshot`` so the existing
  ``--save-assets`` pipeline persists it exactly like a crawl4ai screenshot.
* ``search()`` raises ``NotImplementedError`` (no search action exists).

Authentication (REST lane): a custom API token with **Browser Rendering -
Edit** permission, sent as ``Authorization: Bearer <token>``. The token is
read from the environment ONLY — never argv, never a config-file plaintext
(the acceptance criteria pin this) — via ``CLOUDFLARE_BROWSER_RUN_TOKEN``.
The account id comes from ``CF_ACCOUNT_ID`` (or explicit config/env override).
A missing token fails at CALL time with :class:`BrowserRunAuthError` (a
:class:`ProviderAuthError`, so the fallback chain falls through) — the
parallel-provider precedent: eager chain construction must never die on a
keyless candidate.

Response shapes (pinned from the official docs):
* text actions (``/content``, ``/markdown``): JSON ``{"success": true,
  "result": "<text>"}``; errors are the standard CF v4 envelope
  ``{"success": false, "errors": [{"code", "message"}]}``.
* ``/screenshot``: raw PNG bytes (``Content-Type: image/png``).

Escalation-drain semantics (P6-B) live in the fetch CLI path, not here: this
provider is a plain WebProvider. Wall-signature retries and the
needs_human policy are the fetcher lane's contract.

No optional-install wrapper applies: httpx is a core dependency.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from hyperresearch.web._netguard import validate_url_public
from hyperresearch.web.base import ProviderAuthError, WebResult

logger = logging.getLogger(__name__)

# Canonical REST base (the quick-actions reference spells browser-rendering;
# the Kitesurf pages spell browser-run — both resolve; the reference form is
# the default and the engine rides the ?browser= query param either way).
DEFAULT_BASE_URL = "https://api.cloudflare.com/client/v4"

# The v4 API prefix between the base and the account id.
_V4_ACCOUNTS_PREFIX = "/accounts"

_TOKEN_ENV = "CLOUDFLARE_BROWSER_RUN_TOKEN"
_ACCOUNT_ENV = "CF_ACCOUNT_ID"

_VALID_ENGINES = frozenset({"kitesurf", "chromium"})

# Tags that carry no text when stripped of the DOM chrome.
_STRIP_TAGS_RE = re.compile(
    r"<(script|style|noscript|template|svg|head)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_BLOCK_TAG_RE = re.compile(r"</?(?:p|div|br|h[1-6]|li|tr|table|section|article)[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANK_RE = re.compile(r"\n{3,}")


class BrowserRunAuthError(ProviderAuthError):
    """CLOUDFLARE_BROWSER_RUN_TOKEN missing at call time (not construction).

    Subclasses :class:`~hyperresearch.web.base.ProviderAuthError` so the
    fallback chain recognises it as an auth-config error and falls through
    to the next candidate (the parallel-provider precedent).
    """


class BrowserRunApiError(RuntimeError):
    """A failed Browser Run exchange.

    Carries the HTTP status in ``.status_code`` and Cloudflare's error code
    in ``.cf_code`` (from the v4 envelope) when present. Mirrors
    :class:`~hyperresearch.web.parallel_provider.ParallelApiError` so the
    chain's fall-through classification recognises it by exact type + status.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        cf_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.cf_code = cf_code


def html_to_text(html: str) -> str:
    """Rendered-HTML -> readable plain text (best-effort, no deps).

    The /content action returns the FULL rendered DOM including head and
    scripts. Vault notes want readable text: strip script/style/head blocks,
    turn block-level closes into newlines, drop the remaining tags, and
    collapse whitespace. Deliberately simple — the junk gates downstream
    catch the pathological cases.
    """
    text = _STRIP_TAGS_RE.sub("", html)
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    # Minimal entity decode (the common five + numeric forms).
    for entity, char in (
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
        ("&#39;", "'"), ("&nbsp;", " "),
    ):
        text = text.replace(entity, char)
    text = _WS_RE.sub(" ", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip()


class BrowserRunProvider:
    """Web provider backed by Cloudflare Browser Run Quick Actions.

    ``fetch()`` maps one URL to one ``/content`` call (Kitesurf engine by
    default — agent-first, stateless, runs entirely in CF isolates) and
    extracts readable text. ``screenshot=True`` adds one ``/screenshot``
    call whose PNG bytes ride the WebResult for the existing asset pipeline.

    DELIBERATE no-SSRF-ambiguity: the FETCHED url is validated with the
    shared ``_netguard.validate_url_public`` (SSRF guard) before any
    request, and the API endpoint (api.cloudflare.com) is a fixed public
    host — the target URL travels in the JSON body, never as our request
    host.
    """

    name = "browser-run"

    def __init__(
        self,
        api_token: str | None = None,
        account_id: str | None = None,
        engine: str = "kitesurf",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        # Test-only seam: an httpx.BaseTransport (e.g. MockTransport) used
        # when building each client so tests run with zero network.
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        if engine not in _VALID_ENGINES:
            valid = ", ".join(sorted(_VALID_ENGINES))
            raise ValueError(f"invalid engine {engine!r}: expected one of {valid}")
        self._api_token = api_token
        self._account_id = account_id
        self._engine = engine
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = _transport

    # ------------------------------------------------------------------
    # Credentials (env-only, per the acceptance criteria)
    # ------------------------------------------------------------------

    def _resolve_token(self) -> str:
        token = self._api_token or os.environ.get(_TOKEN_ENV, "").strip()
        if not token:
            raise BrowserRunAuthError(
                f"{_TOKEN_ENV} is not set. Create a custom API token with "
                "'Browser Rendering - Edit' permission at "
                "https://dash.cloudflare.com/profile/api-tokens and export "
                f"it as {_TOKEN_ENV}."
            )
        return token

    def _resolve_account_id(self) -> str:
        account = self._account_id or os.environ.get(_ACCOUNT_ENV, "").strip()
        if not account:
            raise BrowserRunAuthError(
                f"{_ACCOUNT_ENV} is not set. Find the account id in the CF "
                "dashboard (Workers & Pages overview right rail) and export "
                f"it as {_ACCOUNT_ENV}."
            )
        return account

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    def _quick_action_json(self, action: str, payload: dict[str, Any]) -> str:
        """POST one text Quick Action; returns its result string.

        Raises:
            BrowserRunApiError: HTTP non-200 (auth failures carry the
                'Browser Rendering - Edit' guidance), success=false
                envelope, or an empty result.
            BrowserRunAuthError: token/account env missing at call time.
            httpx.TransportError: propagated untouched (chain fall-through).
        """
        resp = self._post_action(action, payload)
        data = _envelope_result(resp)
        if not isinstance(data, str) or not data.strip():
            raise BrowserRunApiError(
                f"Browser Run {action} returned an empty result "
                f"(HTTP 200) — the page may have rendered blank.",
                status_code=200,
            )
        return data

    def _post_action(self, action: str, payload: dict[str, Any]) -> httpx.Response:
        """POST one Quick Action and return the raw response (HTTP 200
        enforced; auth errors carry scope guidance)."""
        validate_url_public(self._base_url)
        url = (
            f"{self._base_url}{_V4_ACCOUNTS_PREFIX}/"
            f"{self._resolve_account_id()}/browser-rendering/{action}"
            f"?browser={self._engine}"
        )
        headers = {
            "Authorization": f"Bearer {self._resolve_token()}",
            "Content-Type": "application/json",
        }
        with httpx.Client(
            base_url="",
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            resp = client.post(url, json=payload, headers=headers)
        if resp.status_code in (401, 403):
            message = _cf_error_message(resp)
            raise BrowserRunApiError(
                f"Browser Run rejected the token (HTTP {resp.status_code}): "
                f"{message}. The token needs 'Browser Rendering - Edit'.",
                status_code=resp.status_code,
            )
        if resp.status_code != 200:
            raise BrowserRunApiError(
                f"Browser Run {action} failed (HTTP {resp.status_code}): "
                f"{_cf_error_message(resp) or resp.text[:200]}",
                status_code=resp.status_code,
            )
        return resp

    # ------------------------------------------------------------------
    # WebProvider surface
    # ------------------------------------------------------------------

    def fetch(self, url: str, *, screenshot: bool = False) -> WebResult:
        """Render one URL in Kitesurf and return its readable text.

        The target URL is SSRF-guarded BEFORE any request (it travels in
        the JSON body to Cloudflare, but a private target would still make
        CF fetch from inside their network — the guard keeps our contract
        uniform across providers). ``screenshot=True`` adds a PNG capture
        on ``WebResult.screenshot``.
        """
        validate_url_public(url)
        payload: dict[str, Any] = {
            "url": url,
            # JS-heavy pages are the whole point of the lane: wait for the
            # network to go quiet before capturing (docs' SPA guidance).
            "gotoOptions": {"waitUntil": "networkidle2"},
        }
        content_html = self._quick_action_json("content", payload)
        content_text = html_to_text(content_html)

        shot_bytes: bytes | None = None
        if screenshot:
            shot_resp = self._post_action("screenshot", {"url": url})
            shot_bytes = shot_resp.content

        metadata: dict[str, Any] = {"provider": "browser-run", "engine": self._engine}
        return WebResult(
            url=url,
            title=_title_from_html(content_html) or url,
            content=content_text,
            fetched_at=datetime.now(UTC),
            raw_html=content_html[:200_000] if len(content_html) > 200_000 else content_html,
            metadata=metadata,
            screenshot=shot_bytes,
        )

    def fetch_screenshot(self, url: str) -> bytes:
        """Standalone /screenshot capture (PNG bytes)."""
        validate_url_public(url)
        return self._post_action("screenshot", {"url": url}).content

    def fetch_markdown(self, url: str) -> str:
        """/markdown quick action — Cloudflare-side markdown conversion."""
        validate_url_public(url)
        return self._quick_action_json(
            "markdown",
            {"url": url, "gotoOptions": {"waitUntil": "networkidle2"}},
        )

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """Not supported — Browser Run has no search action.

        Raises NotImplementedError per the WebProvider protocol so the
        fallback chain skips this candidate for search-shaped calls.
        """
        raise NotImplementedError(
            "The browser-run provider does not search. Fetch a specific URL "
            "(it renders JS-heavy pages) or use `hpr search-web`."
        )


def _envelope_result(resp: httpx.Response) -> Any:
    """Parse the CF v4 envelope; raise on success=false / malformed body."""
    try:
        body: Any = resp.json()
    except ValueError as exc:
        raise BrowserRunApiError(
            f"Browser Run returned invalid JSON (HTTP {resp.status_code}): {exc}",
            status_code=resp.status_code,
        ) from exc
    if not isinstance(body, dict):
        raise BrowserRunApiError(
            f"Browser Run returned a non-object body (HTTP {resp.status_code})",
            status_code=resp.status_code,
        )
    if body.get("success") is False:
        raise BrowserRunApiError(
            f"Browser Run error: {_cf_errors_text(body)}",
            status_code=resp.status_code,
            cf_code=_cf_first_code(body),
        )
    return body.get("result")


def _cf_error_message(resp: httpx.Response) -> str:
    """Human message out of an error response, when the body has one."""
    try:
        body: Any = resp.json()
    except ValueError:
        return resp.text.strip()[:200]
    if isinstance(body, dict):
        return _cf_errors_text(body)
    return str(body)[:200]


def _cf_errors_text(body: dict[str, Any]) -> str:
    errors = body.get("errors") or []
    parts: list[str] = []
    for err in errors:
        if isinstance(err, dict):
            msg = str(err.get("message", "")).strip()
            code = err.get("code")
            parts.append(f"{msg} (code {code})" if msg else f"code {code}")
        elif err:
            parts.append(str(err))
    return "; ".join(p for p in parts if p) or "unknown error"


def _cf_first_code(body: dict[str, Any]) -> int | None:
    errors = body.get("errors") or []
    for err in errors:
        if isinstance(err, dict):
            code = err.get("code")
            if isinstance(code, int):
                return code
    return None


def _title_from_html(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    title = _TAG_RE.sub("", m.group(1))
    return _WS_RE.sub(" ", title).strip()[:300]
