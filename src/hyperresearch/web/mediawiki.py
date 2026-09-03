"""MediaWiki clean-text lane — native action-API fetching for Wikimedia wikis.

Wikipedia (and the other Wikimedia wikis) are among the most-fetched
reference sources in a research vault, and also among the worst-served by
generic page rendering: the served HTML buries the article under site
chrome — "Jump to content", search/donate/login bars, 40-language
interwiki lists, "Edit links", sidebar menus, navboxes, category boxes,
and a footer. A live probe (``Immunotherapy``, en.wikipedia.org) measured
55,077 chars of that soup against 19,428 chars of actual article prose —
roughly two thirds of every wikipedia note was navigation garbage.

The fix is not better stripping: MediaWiki ships a native machine
interface, and this lane uses it. ``action=query&prop=extracts&explaintext``
returns the full article as plain text with ``== Section ==`` headings —
references, navboxes, sidebars, interwiki links, infoboxes, and site
chrome are removed SERVER-SIDE by the same TextExtract code that powers
Wikipedia's own apps. This module converts the headings to markdown
(``## Section``), drops tail sections that lost their bodies to the
extractor (``== References ==`` always comes back empty), and returns a
:class:`~hyperresearch.web.base.WebResult`.

Contract with the provider chain (:class:`hyperresearch.web.base._ChainedProvider`,
which calls this lane BEFORE any generic candidate):

* URL not on a Wikimedia wiki, not a content-page URL shape, or a
  revision-specific view (``oldid``/``diff``) → ``None``: the normal
  chain serves it exactly as before.
* Page exists but has no extractable prose (Category:, Wikidata Q-items,
  most File: pages) → ``None``: the generic render actually carries the
  useful content for those, so it takes over.
* Transient lane failure (transport error, non-2xx, undecodable JSON)
  → ``None`` with a debug log: fall through to the generic chain rather
  than failing a fetch the chain could still serve.
* Page verifiably does not exist (API ``missing``/``missingtitle``) →
  raises :class:`MediawikiPageError`: a clean, honest failure. Falling
  back here would save Wikipedia's "does not have an article with this
  exact name" interstitial as a research note.

The API request goes through :func:`hyperresearch.web._netguard.guarded_get`
(SSRF-validated start URL + redirect re-validation), matching the builtin
provider's lane. ``result.url`` stays the ORIGINAL requested URL — the
sources table and note frontmatter key on it, and redirects (via the API's
``redirects=1``) are recorded in ``metadata`` instead.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlunparse

from hyperresearch.web._netguard import guarded_get, validate_url_public
from hyperresearch.web.base import WebResult

logger = logging.getLogger(__name__)

# Serving-provider name recorded in the sources table / fetch_provider
# frontmatter when this lane serves a fetch (mirrors "browser-run").
PROVIDER_NAME = "mediawiki-api"

# Wikimedia wiki hosts, matched by exact host or dot-suffix so a lookalike
# ("en.wikipedia.org.evil.com") can never enter the lane — same hardening
# as _on_arxiv_host in crawl4ai_provider.py.
_WIKI_HOSTS: frozenset[str] = frozenset(
    {
        "wikipedia.org",
        "wiktionary.org",
        "wikibooks.org",
        "wikiquote.org",
        "wikisource.org",
        "wikinews.org",
        "wikiversity.org",
        "wikivoyage.org",
        "wikimedia.org",
        "wikidata.org",
        "mediawiki.org",
    }
)

# Namespaces that never yield extractable prose. Fetching them through the
# API is a wasted round trip — skip straight to None so the generic chain
# renders whatever those pages actually show (file descriptions, etc.).
_NON_PROSE_NAMESPACES = ("Special:", "Media:", "File:")

# == Section == (2-6 equals) → markdown heading; same level count. A wiki
# level-2 heading is an article's top section, and the note's H1 is its
# title, so == maps to ## without losing a level.
_HEADING_RE = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")
_MD_HEADING_RE = re.compile(r"^#{2,6}\s+\S")

# Query params that make a ?title= URL a NON-plain view (revision diff,
# old revision, edit form). The extract is always the CURRENT revision,
# so honouring these means the generic lane.
_REVISION_PARAMS = ("oldid", "diff", "curid", "action")

# Wikimedia's UA policy asks for a descriptive agent with a contact point.
_USER_AGENT = "hyperresearch/0.1 (research note fetcher; MediaWiki action API)"


class MediawikiPageError(RuntimeError):
    """The requested wiki page verifiably does not exist.

    Deliberately NOT a fall-through signal: falling back to the generic
    chain here would save Wikipedia's "article doesn't exist" interstitial
    (with its search-results chrome) as a research note. The CLI surfaces
    this as a normal FETCH_ERROR.
    """


def is_mediawiki_url(url: str) -> bool:
    """True when `url` is on a Wikimedia wiki host (exact/suffix host match)."""
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host in _WIKI_HOSTS:
        return True
    return any(host.endswith("." + domain) for domain in _WIKI_HOSTS)


def extract_page_title(url: str) -> str | None:
    """Pull the wiki page title out of a content-page URL, if it has one.

    Accepted shapes (everything else → None, generic chain serves):

    * ``https://en.wikipedia.org/wiki/<Title>`` (title percent-decoded;
      ``#fragment`` section anchors ignored — the extract is whole-page)
    * ``https://en.wikipedia.org/w/index.php?title=<Title>`` — but ONLY
      as a plain view: ``oldid``/``diff``/``curid``/``action`` params make
      it revision-specific, and the API extract cannot honour them.

    Non-prose namespaces (Special:/Media:/File:) short-circuit to None —
    the API would return nothing useful for them anyway.
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)

    title: str | None = None
    if path.startswith("/wiki/"):
        title = path[len("/wiki/") :]
    elif path.startswith("/w/index.php"):
        query = parse_qs(parsed.query)
        if any(p in query for p in _REVISION_PARAMS):
            return None
        titles = query.get("title")
        if titles:
            title = titles[0]
    else:
        return None

    if title is None:
        return None
    title = title.strip("/")
    if not title:
        return None
    if title.startswith(_NON_PROSE_NAMESPACES):
        return None
    return title


def _headings_to_markdown(text: str) -> str:
    """Convert ``== Section ==`` extract headings to ``## Section``."""
    out: list[str] = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            out.append(f"{'#' * len(m.group(1))} {m.group(2)}")
        else:
            out.append(line)
    return "\n".join(out)


def _drop_tail_headings(md: str) -> str:
    """Drop headings that lost their bodies to the extractor.

    TextExtract strips reference bodies entirely, so ``== References ==``
    (and cousins like ``== Notes ==`` / ``== Citations ==``) arrive as the
    last line with nothing after them. A heading that is the final
    non-blank line has no content to anchor — drop it, repeatedly. A
    heading with content after it is never the last line, so it always
    survives (e.g. ``== See also ==`` keeps its link list).
    """
    lines = md.rstrip().splitlines()
    while lines and _MD_HEADING_RE.match(lines[-1].strip()):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines)


def _api_url_for(url: str, title: str) -> str:
    """Full action-API request URL (endpoint + encoded params) for a page.

    guarded_get takes a complete URL (no params kwarg) so every redirect
    hop re-validates against the same fully-specified target.
    """
    parsed = urlparse(url)
    query = urlencode(_api_payload(title))
    return urlunparse((parsed.scheme, parsed.netloc, "/w/api.php", "", query, ""))


def _api_payload(title: str) -> dict[str, str | int]:
    """Query params for the clean-text extract + page metadata."""
    return {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "extracts|info",
        "explaintext": 1,
        "exlimit": 1,  # full (non-intro) extracts allow exactly one page
        "redirects": 1,
        "inprop": "url",
        "titles": title,
    }


def fetch_mediawiki(
    url: str,
    *,
    timeout: float = 30.0,
    _transport: Any | None = None,  # httpx.MockTransport test seam
) -> WebResult | None:
    """Serve a wiki page its clean native-API text.

    Returns None whenever the lane does not apply or fails transiently
    (see module docstring); the provider chain then serves the URL through
    its normal candidates. Raises :class:`MediawikiPageError` only when the
    API confirms the page does not exist.
    """
    if not is_mediawiki_url(url):
        return None
    title = extract_page_title(url)
    if title is None:
        return None

    api = _api_url_for(url, title)
    try:
        if _transport is not None:
            # Test seam — same request URL, mocked transport. (httpx's
            # top-level get() takes no transport; a one-shot Client does.)
            import httpx

            validate_url_public(api)
            with httpx.Client(transport=_transport) as client:
                resp = client.get(
                    api,
                    timeout=timeout,
                    headers={"User-Agent": _USER_AGENT},
                )
        else:
            resp = guarded_get(
                api,
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
            )
    except Exception as exc:
        logger.debug("mediawiki lane fell through (request failed): %s", exc)
        return None

    if resp.status_code < 200 or resp.status_code >= 300:
        logger.debug("mediawiki lane fell through (HTTP %s)", resp.status_code)
        return None

    try:
        data = resp.json()
    except ValueError as exc:
        logger.debug("mediawiki lane fell through (bad JSON): %s", exc)
        return None

    error = data.get("error")
    if isinstance(error, dict):
        code = error.get("code", "")
        if code == "missingtitle":
            raise MediawikiPageError(
                f"Wikipedia page does not exist: {title!r} ({urlparse(url).netloc})"
            )
        # invalidtitle (Special: pages), readapidenied, etc. — the generic
        # chain's problem, not ours.
        logger.debug("mediawiki lane fell through (API error %s)", code)
        return None

    query = data.get("query") or {}
    pages = query.get("pages") or []
    if not pages:
        logger.debug("mediawiki lane fell through (no pages in response)")
        return None
    page = pages[0]

    if page.get("missing"):
        raise MediawikiPageError(
            f"Wikipedia page does not exist: {page.get('title', title)!r} ({urlparse(url).netloc})"
        )

    extract = page.get("extract") or ""
    if not extract.strip():
        # Category:, Wikidata items, image galleries — no prose to extract.
        # The generic render is the better representation; let it serve.
        logger.debug("mediawiki lane fell through (empty extract)")
        return None

    body = _drop_tail_headings(_headings_to_markdown(extract))

    redirects = query.get("redirects") or []
    redirected_from = redirects[0].get("from") if redirects else None

    metadata: dict[str, Any] = {
        "provider": PROVIDER_NAME,
        "last_edited": page.get("touched"),
        "page_id": page.get("pageid"),
        "language": page.get("pagelanguage"),
        "canonical_url": page.get("canonicalurl"),
    }
    if redirected_from:
        metadata["redirected_from"] = redirected_from

    return WebResult(
        url=url,
        title=page.get("title") or title,
        content=body,
        fetched_at=datetime.now(UTC),
        metadata=metadata,
    )
