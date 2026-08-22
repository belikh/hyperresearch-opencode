"""Builtin web provider — uses httpx + beautifulsoup4 if available, else bare urllib."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html.parser import HTMLParser

from hyperresearch.web._netguard import guarded_get, guarded_urlopen
from hyperresearch.web.base import WebResult


class _TextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor (no external deps)."""

    def __init__(self) -> None:  # Delta vs upstream: added `-> None` for mypy --strict
        super().__init__()
        self._pieces: list[str] = []
        self._skip = False
        self._skip_tags = {"script", "style", "nav", "footer", "header"}
        self._title = ""
        self._in_title = False

    # Delta vs upstream: override params annotated for mypy --strict (typeshed signature)
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._skip_tags:
            self._skip = True
        if tag == "title":
            self._in_title = True
        if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip_tags:
            self._skip = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title = data.strip()
        if not self._skip:
            self._pieces.append(data)

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        # Collapse whitespace
        lines = [line.strip() for line in raw.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class BuiltinProvider:
    """Minimal web fetcher using stdlib + optional httpx/bs4."""

    name = "builtin"

    def fetch(self, url: str) -> WebResult:
        html, final_url = self._download(url)
        title, content = self._extract(html)
        return WebResult(
            url=final_url,
            title=title,
            content=content,
            raw_html=html,
            fetched_at=datetime.now(UTC),
        )

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        raise NotImplementedError(
            "Builtin provider does not support web search. "
            "Use your agent's built-in search, then pipe URLs into 'hyperresearch fetch'."
        )

    def _download(self, url: str) -> tuple[str, str]:
        """Download URL, return (html, final_url). Tries httpx first, falls back to urllib.

        Both lanes are SSRF-guarded (P1-4 hardening): the start URL is
        validated before any request and every redirect hop is re-validated —
        `follow_redirects=True` / urllib's default redirect handling would
        follow a poisoned Location straight into internal infrastructure.
        """
        try:
            # guarded_get imports httpx lazily; ImportError here means "no
            # httpx installed" and selects the stdlib lane below.
            resp = guarded_get(url, timeout=30, headers={"User-Agent": "hyperresearch/0.1"})
            resp.raise_for_status()
            return resp.text, str(resp.url)
        except ImportError:
            pass

        with guarded_urlopen(url, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            return html, resp.url or url

    def _extract(self, html: str) -> tuple[str, str]:
        """Extract title and clean text from HTML. Tries bs4 first, falls back to stdlib."""
        try:
            # Delta vs upstream: ignore for --strict; bs4 is optional and
            # stub-less here (stdlib parser fallback below is the real path).
            from bs4 import BeautifulSoup  # type: ignore[import-not-found]

            soup = BeautifulSoup(html, "html.parser")
            # Remove noise
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            text = soup.get_text(separator="\n", strip=True)
            # Collapse blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)
            return title, text
        except ImportError:
            pass

        # Fallback: stdlib HTML parser
        parser = _TextExtractor()
        parser.feed(html)
        return parser._title, parser.get_text()
