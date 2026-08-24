"""Parallel web provider — api.parallel.ai Search & Extract APIs.

Parallel (https://parallel.ai) exposes two JSON endpoints used here:
``POST /v1/search`` (objective + keyword queries → ranked results with
markdown excerpts) and ``POST /v1/extract`` (up to 20 URLs per call → per-URL
markdown content, optionally the full page).

Authentication — spec finding: the Parallel OpenAPI document declares its
security scheme as ``securitySchemes.ApiKeyAuth = {type: apiKey, in: header,
name: "x-api-key"}``. Despite what some third-party examples show, this is
NOT ``Authorization: Bearer <key>``; this provider sends the key in the
``x-api-key`` header, the lowercase literal the spec declares (HTTP header
names are case-insensitive on the wire).

Configuration:
    export PARALLEL_API_KEY="your-api-key"   # https://parallel.ai

    # in .hyperresearch/config.toml
    [web]
    provider = "parallel"

Delta vs the tavily/exa providers: a missing key does NOT fail construction.
Provider candidates are constructed eagerly by the fallback chain, so
ParallelProvider defers the key check to the first fetch()/search() call,
where it raises :class:`ParallelAuthError` (a RuntimeError) with an
actionable message.

No optional-install wrapper applies here: httpx is a core dependency of
hyperresearch, so unlike tavily/crawl4ai there is no ImportError/pip-extra
hint to raise or translate.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from hyperresearch.web._netguard import validate_url_public
from hyperresearch.web.base import WebResult

logger = logging.getLogger(__name__)

# V1ExtractRequest.urls accepts at most 20 entries per call (OpenAPI spec);
# fetch_many() chunks larger lists into batched POSTs of this size.
_EXTRACT_BATCH_LIMIT = 20

_VALID_MODES = frozenset({"turbo", "fast", "basic", "advanced"})


class ParallelAuthError(RuntimeError):
    """PARALLEL_API_KEY was missing at call time (not at construction)."""


class ParallelApiError(RuntimeError):
    """A non-200 response from the Parallel API.

    Carries the HTTP status in ``.status_code`` and, when the body followed
    the ErrorResponse envelope, the server's human-readable message.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _metadata_for(item: dict[str, Any]) -> dict[str, Any]:
    """Shared metadata mapping for search/extract rows."""
    metadata: dict[str, Any] = {"provider": "parallel"}
    publish_date = item.get("publish_date")
    if publish_date:
        metadata["published_date"] = publish_date
    return metadata


def _joined_excerpts(item: dict[str, Any]) -> str:
    excerpts = item.get("excerpts") or []
    return "\n\n".join(e for e in excerpts if e)


def _search_result_to_web_result(item: dict[str, Any]) -> WebResult:
    """Map a V1WebSearchResult into a hyperresearch WebResult."""
    return WebResult(
        url=item.get("url") or "",
        title=item.get("title") or "",  # null title -> ""
        content=_joined_excerpts(item),
        fetched_at=datetime.now(UTC),
        metadata=_metadata_for(item),
    )


def _extract_result_to_web_result(item: dict[str, Any]) -> WebResult:
    """Map a V1ExtractResult; full_content wins over joined excerpts."""
    full_content = item.get("full_content")
    content = full_content if full_content else _joined_excerpts(item)
    return WebResult(
        url=item.get("url") or "",
        title=item.get("title") or "",
        content=content,
        fetched_at=datetime.now(UTC),
        metadata=_metadata_for(item),
    )


def _error_message(resp: httpx.Response) -> str:
    """Faithful message extraction from a non-200 Parallel response.

    Parses the ErrorResponse envelope ({"type":"error","error":{"message"}})
    when present, appending the envelope's ``ref_id`` as "(ref <ref_id>)"
    when the envelope carries one; falls back to the raw body text otherwise.
    """
    try:
        body: Any = resp.json()
    except ValueError:
        body = None
    if (
        isinstance(body, dict)
        and body.get("type") == "error"
        and isinstance(body.get("error"), dict)
    ):
        server_message = body["error"].get("message")
        if server_message:
            message = str(server_message)
            ref_id = body["error"].get("ref_id")
            if ref_id:
                message = f"{message} (ref {ref_id})"
            return message
    raw_text = resp.text.strip()
    return raw_text or f"Parallel API error (HTTP {resp.status_code})"


class ParallelProvider:
    """Web provider backed by api.parallel.ai Search & Extract.

    ``fetch()``/``fetch_many()`` use ``POST /v1/extract`` with full page
    content requested; ``search()`` uses ``POST /v1/search``. Results map
    onto :class:`WebResult` with ``metadata["provider"] == "parallel"``.

    DELIBERATE DELTA vs tavily/exa providers: missing-key errors surface at
    CALL time (:class:`ParallelAuthError`, a RuntimeError subclass) instead
    of construction time — see the module docstring for why. Non-200 API
    responses raise :class:`ParallelApiError`; transport failures propagate
    as httpx.TransportError untouched.

    HTTP client choice — client-per-call: each API call builds a short-lived
    ``httpx.Client`` inside a ``with`` block. No pooled state is shared
    across calls (nothing to leak in long sessions), the lifecycle closes
    deterministically, and request volume here is one research wave at a
    time, so connection-pool reuse would buy nothing over simplicity and
    easy transport injection.
    """

    name = "parallel"

    def __init__(
        self,
        api_key: str | None = None,
        mode: str = "advanced",
        excerpt_max_chars: int = 2000,
        full_content_max_chars: int | None = None,
        base_url: str = "https://api.parallel.ai",
        timeout: float = 60.0,
        # Test-only seam: an httpx.BaseTransport (e.g. MockTransport) used
        # when building each client so tests run with zero network.
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        if mode not in _VALID_MODES:
            valid = ", ".join(sorted(_VALID_MODES))
            raise ValueError(f"invalid mode {mode!r}: expected one of {valid}")
        self._api_key = api_key
        self._mode = mode
        self._excerpt_max_chars = excerpt_max_chars
        self._full_content_max_chars = full_content_max_chars
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = _transport
        #: Per-result ExtractErrors from the most recent fetch_many() call;
        #: partial failures never raise, they land here (and in the log).
        self.last_extract_errors: list[dict[str, Any]] = []

    def _resolve_api_key(self) -> str:
        key = self._api_key or os.environ.get("PARALLEL_API_KEY", "").strip()
        if not key:
            raise ParallelAuthError(
                "PARALLEL_API_KEY is not set. Get a key at https://parallel.ai "
                "and export it."
            )
        return key

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST one JSON request against the configured base URL."""
        # Header name is the lowercase literal declared by the OpenAPI
        # securitySchemes (ApiKeyAuth, in: header, name: "x-api-key");
        # HTTP header names are case-insensitive on the wire.
        headers = {"x-api-key": self._resolve_api_key()}
        with httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            resp = client.post(path, json=payload, headers=headers)
        if resp.status_code != 200:
            raise ParallelApiError(_error_message(resp), status_code=resp.status_code)
        try:
            data_raw: Any = resp.json()
        except ValueError as exc:
            raise ParallelApiError(
                f"Parallel API returned invalid JSON (HTTP 200): {exc}",
                status_code=200,
            ) from exc
        if not isinstance(data_raw, dict):
            raise ParallelApiError(
                "Parallel API returned a non-object 200 body "
                f"(top-level {type(data_raw).__name__})",
                status_code=200,
            )
        return data_raw

    def _advanced_extract_settings(self) -> dict[str, Any]:
        """Full-content settings shared by fetch()/fetch_many()."""
        full_content: bool | dict[str, int] = (
            {"max_chars_per_result": self._full_content_max_chars}
            if self._full_content_max_chars is not None
            else True
        )
        return {"full_content": full_content}

    def fetch(self, url: str) -> WebResult:
        """Fetch a single URL via Parallel extract and return clean content."""
        validate_url_public(url)  # SSRF guard BEFORE any request
        payload = {
            "urls": [url],
            "advanced_settings": self._advanced_extract_settings(),
        }
        data = self._post_json("/v1/extract", payload)

        results: list[dict[str, Any]] = list(data.get("results") or [])
        if results:
            return _extract_result_to_web_result(results[0])

        errors: list[dict[str, Any]] = [
            e for e in (data.get("errors") or []) if e.get("url") == url
        ]
        if errors:
            error_type = str(errors[0].get("error_type") or "unknown")
            status = errors[0].get("http_status_code")
            suffix = f" (HTTP {status})" if status else ""
            raise RuntimeError(f"Parallel could not extract {url!r}: {error_type}{suffix}")
        raise RuntimeError(f"Parallel returned no contents for {url}")

    def fetch_many(self, urls: list[str]) -> list[WebResult]:
        """Batched extract; returns successful WebResults only.

        - ALL URLs are SSRF-validated up front (all-or-nothing): one bad URL
          aborts before any request is issued.
        - Input URLs are deduplicated preserving first-seen order, so a
          repeated URL neither double-fetches nor inflates the result list.
        - URLs are chunked into <=20-URL batches (the V1ExtractRequest limit);
          each chunk is ONE batched POST and caller order is preserved.
        - Per-result ExtractErrors NEVER raise: they are recorded on
          ``self.last_extract_errors`` and logged as warnings. This mirrors
          the crawl4ai ``fetch_many`` duck-type consumed by
          cli/fetch_batch.py (successes only, whole-batch failure falls back
          to per-URL fetching).
        - Only whole-request failures propagate: transport errors
          (httpx.TransportError) and non-200 envelopes (ParallelApiError).
        """
        for url in urls:
            validate_url_public(url)
        self.last_extract_errors = []
        results: list[WebResult] = []
        advanced = self._advanced_extract_settings()
        # First-seen-order dedupe: duplicates neither double-fetch nor
        # inflate the returned results.
        unique_urls = list(dict.fromkeys(urls))
        for chunk in _chunks(unique_urls, _EXTRACT_BATCH_LIMIT):
            data = self._post_json(
                "/v1/extract",
                {"urls": chunk, "advanced_settings": advanced},
            )
            succeeded: dict[Any, dict[str, Any]] = {
                item.get("url"): item for item in (data.get("results") or [])
            }
            for url in chunk:
                item = succeeded.get(url)
                if item is not None:
                    results.append(_extract_result_to_web_result(item))
            for error in data.get("errors") or []:
                entry: dict[str, Any] = {
                    "url": error.get("url"),
                    "error_type": error.get("error_type"),
                    "http_status_code": error.get("http_status_code"),
                    "content": error.get("content"),
                }
                self.last_extract_errors.append(entry)
                status = entry["http_status_code"]
                logger.warning(
                    "Parallel extract failed for %s: %s%s",
                    entry["url"],
                    entry["error_type"],
                    f" (HTTP {status})" if status else "",
                )
        return results

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """Search the web via Parallel and return ranked results with excerpts."""
        payload = {
            "objective": query,
            "search_queries": [query],
            "mode": self._mode,
            "advanced_settings": {
                "max_results": max_results,
                "excerpt_settings": {
                    "max_chars_per_result": self._excerpt_max_chars,
                },
            },
        }
        data = self._post_json("/v1/search", payload)
        # Preserve the API's relevance order verbatim.
        return [_search_result_to_web_result(item) for item in (data.get("results") or [])]
