"""Base protocol and data types for web providers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar, runtime_checkable

from hyperresearch.core.config import FetchSettings, JunkGates

_T = TypeVar("_T")

# Whitespace that is legitimate in extracted text.
_TEXT_WHITESPACE = "\t\n\r\f\v"

# Invisible formatting characters used to pad junk past length gates or to
# split signal phrases ("Just a moment") so they stop matching (P1-4
# hardening finding 2): ZWSP, ZWNJ, ZWJ, word joiner + invisible operators,
# BOM/ZWNBSP, soft hyphen, Mongolian vowel separator, Arabic letter mark.
# Deliberately an explicit set: a blanket unicodedata category-Cf filter has
# no evidence behind it and these are the characters observed in scraped spam.
_INVISIBLE_CHARS = frozenset(
    "\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064\ufeff\u00ad\u180e\u061c"
)


def strip_invisible(text: str) -> str:
    """Remove zero-width/invisible formatting characters from `text`.

    The junk gates measure and match on this normalization, so invisible
    padding can neither fake substance nor camouflage a signal phrase.
    """
    if not any(c in text for c in _INVISIBLE_CHARS):
        return text  # fast path: nothing to strip on ordinary text
    return "".join(c for c in text if c not in _INVISIBLE_CHARS)


# Default thresholds — used when no vault config is in play (e.g. direct
# provider usage in tests/scripts). Matches VaultConfig defaults.
DEFAULT_GATES = JunkGates()


def is_binary_garbage_char(c: str) -> bool:
    """True if `c` indicates binary or mis-decoded content rather than real text.

    Deliberately NOT `ord(c) > 127`. Treating all non-ASCII as binary rejects
    valid CJK, Arabic, Cyrillic, Greek, Hebrew, Thai, and accented Latin text —
    i.e. most of the non-English web. Only genuine markers of binary data or a
    failed decode count here.
    """
    o = ord(c)
    if o < 0x20 and c not in _TEXT_WHITESPACE:
        return True  # C0 control characters
    if c == "�":
        return True  # replacement character — decoding already failed
    return 0x80 <= o <= 0x9F  # C1 control characters


def binary_garbage_ratio(text: str) -> float:
    """Fraction of `text` that looks like binary or mis-decoded content."""
    if not text:
        return 0.0
    return sum(1 for c in text if is_binary_garbage_char(c)) / len(text)


def is_binary_garbage(sample: str, gates: JunkGates | None = None) -> bool:
    """Shared threshold check for binary/mis-decoded content.

    Single implementation for both fetch gates (WebResult.looks_like_junk and
    the crawl4ai post-fetch PDF re-check) so the threshold can't drift apart
    between them again.
    """
    gates = gates or DEFAULT_GATES
    return binary_garbage_ratio(sample) > gates.binary_garbage_ratio


@dataclass
class WebResult:
    """A single web fetch or search result."""

    url: str
    title: str
    content: str  # clean markdown or plain text
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_html: str | None = None
    # Delta vs upstream: `dict`/`list[dict]` parameterized for mypy --strict
    metadata: dict[str, Any] = field(default_factory=dict)  # author, date, domain, etc.
    media: list[dict[str, Any]] = field(default_factory=list)  # images: {src, alt, score, ...}
    links: list[dict[str, Any]] = field(default_factory=list)  # {href, text, type}
    screenshot: bytes | None = None  # PNG screenshot of the rendered page
    raw_bytes: bytes | None = None  # Raw file bytes (PDF, etc.)
    raw_content_type: str | None = None  # MIME type of raw file (application/pdf, etc.)

    @property
    def domain(self) -> str:
        from urllib.parse import urlparse

        return urlparse(self.url).netloc

    def looks_like_login_wall(self, original_url: str, gates: JunkGates | None = None) -> bool:
        """Check if the result appears to be a login/signup redirect rather than real content."""
        gates = gates or DEFAULT_GATES
        login_signals = (
            "sign in",
            "sign up",
            "log in",
            "login",
            "create account",
            "auth",
            "register",
            "sso",
            "verify your identity",
            *gates.extra_login_signals,
        )
        # Same invisible-padding normalization as looks_like_junk: padding
        # must not fake length, and signals split by zero-width characters
        # must still match.
        title_lower = strip_invisible(self.title or "").lower()
        content = strip_invisible(self.content or "")
        content_lower = content[: gates.login_sample_chars].lower()

        # Title contains login language
        title_match = any(s in title_lower for s in login_signals)

        # Content is mostly login form (very short with login keywords)
        content_match = len(content) < gates.login_wall_max_chars and any(
            s in content_lower for s in login_signals
        )

        # URL changed to a login/auth path
        from urllib.parse import urlparse

        result_path = urlparse(self.url).path.lower()
        auth_paths = ("/login", "/signin", "/signup", "/auth", "/sso", "/register")
        url_redirected = any(p in result_path for p in auth_paths)

        return title_match or content_match or url_redirected

    def looks_like_junk(self, gates: JunkGates | None = None) -> str | None:
        """Check if the result is junk that shouldn't be saved.

        Returns a reason string if junk, None if OK.
        """
        gates = gates or DEFAULT_GATES
        content = strip_invisible(self.content or "")
        title_lower = strip_invisible(self.title or "").lower()
        content_lower = content[: gates.sample_window].lower()

        # Empty or near-empty content — measured on visible characters only,
        # so zero-width padding cannot fake substance
        if len(content.strip()) < gates.min_content_chars:
            return "Empty or near-empty content"

        # Cloudflare / bot detection pages. NOTE (P6 hardening, found live
        # via the Kitesurf lane): the bare company name "cloudflare" is
        # DELIBERATELY ABSENT — it matched any page merely *about*
        # Cloudflare (their docs, blog, community threads) and junk-gated
        # legitimate content. Real challenge pages are caught by the strong
        # interstitial phrases ("just a moment", "checking your browser",
        # "ray id", ...) which every actual CF wall emits.
        cf_signals = (
            "just a moment",
            "checking your browser",
            "ray id",
            "please wait while we verify",
            "unusual activity",
            "captcha",
            "recaptcha",
            "verify you are human",
            "verify you are not a robot",
            "please complete the security check",
            "access denied",
            "enable javascript and cookies",
            "browser check",
            "ddos protection",
            "attention required",
        )
        if any(
            s in title_lower or s in content_lower
            for s in cf_signals + tuple(gates.extra_junk_signals)
        ):
            return f"Bot detection page: {self.title}"

        # Error pages
        error_signals = (
            "404 not found",
            "page not found",
            "403 forbidden",
            "500 internal server error",
            "502 bad gateway",
            "an error occurred",
            "this page isn't available",
            "the page you requested",
            "sorry, we couldn't find",
        )
        if any(s in title_lower or s in content_lower for s in error_signals):
            return f"Error page: {self.title}"

        # Search result / index pages (not actual content)
        search_signals = ("search results for", "results for query")
        if any(s in title_lower for s in search_signals):
            return f"Search results page: {self.title}"

        # Binary garbage from PDFs that weren't properly extracted
        pdf_binary_signals = ("endstream", "endobj", "/FlateDecode", "%PDF-")
        sample = content[: gates.sample_window]
        if any(m in sample for m in pdf_binary_signals):
            return "Binary PDF garbage in content"

        if is_binary_garbage(sample, gates):
            return "High ratio of binary/non-printable content"

        # Cookie consent / boilerplate pages (short with mostly nav/cookie text)
        if len(content.strip()) < gates.cookie_wall_max_chars:
            cookie_signals = (
                "we use cookies",
                "cookie policy",
                "accept cookies",
                "cookie consent",
                "there appears to be a technical issue",
                "please enable javascript",
            )
            if any(s in content_lower for s in cookie_signals):
                return "Cookie/boilerplate page"

        return None


@runtime_checkable
class WebProvider(Protocol):
    """Protocol for web content providers.

    Implementations must support at least fetch(). search() is optional —
    providers that don't support search raise NotImplementedError.
    """

    name: str

    def fetch(self, url: str) -> WebResult:
        """Fetch a single URL and return clean content."""
        ...

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """Search the web and return results with content."""
        ...


# Registry of valid web-provider names, in canonical order. Shared by
# get_provider()'s unknown-name error and resolve_web_provider()'s up-front
# spec validation so the advertised set cannot drift between the two.
KNOWN_PROVIDER_NAMES: tuple[str, ...] = (
    "builtin",
    "browser-run",
    "crawl4ai",
    "deepwiki",
    "exa",
    "parallel",
    "tavily",
)

# Names whose provider class implements a batched fetch_many (P4-B review
# F2). Static ON PURPOSE: _ChainedProvider exposes fetch_many only when a
# declared candidate name is in this set, so cli/fetch_batch.py's
# hasattr(prov, "fetch_many") duck-type keeps meaning "this chain can serve a
# batched wave" — a capability-less chain must take the per-URL branch, not
# discover at call time that the batch lane is missing. tests/test_web/
# test_provider_chain.py pins this set against reality; rot fails loudly.
_FETCH_MANY_PROVIDERS: frozenset[str] = frozenset({"parallel", "crawl4ai"})


def get_provider(
    name: str | None = None,
    profile: str | None = None,
    magic: bool = False,
    headless: bool = True,
    settings: FetchSettings | None = None,
    gates: JunkGates | None = None,
) -> WebProvider:
    """Load a web provider by name. Falls back to builtin if none specified.

    Single-name factory. For the ``[web] provider`` config setting — which
    may be a name OR an ordered fallback chain like
    ``["parallel", "builtin"]`` — use :func:`resolve_web_provider`, which
    wraps this factory (P4-B).
    """
    if name is None or name == "builtin":
        from hyperresearch.web.builtin import BuiltinProvider

        return BuiltinProvider()

    if name == "crawl4ai":
        try:
            from hyperresearch.web.crawl4ai_provider import Crawl4AIProvider

            return Crawl4AIProvider(
                profile=profile or None,
                magic=magic,
                headless=headless,
                settings=settings,
                gates=gates,
            )
        except ImportError:
            raise ImportError("crawl4ai provider requires: pip install hyperresearch[crawl4ai]")

    if name == "exa":
        from hyperresearch.web.exa_provider import ExaProvider

        return ExaProvider()

    if name == "parallel":
        # httpx is a core dependency, so unlike the crawl4ai/tavily lanes
        # there is no optional-install ImportError to translate into a
        # pip-extra hint here. Auth is enforced at call time, so no env key
        # is needed merely to construct the provider.
        from hyperresearch.web.parallel_provider import ParallelProvider

        return ParallelProvider()

    if name == "deepwiki":
        # P5-A: Cognition's official DeepWiki MCP server — no optional
        # install (httpx is core), no auth (public endpoint). sessionless
        # Streamable-HTTP JSON-RPC; see deepwiki_provider.py.
        from hyperresearch.web.deepwiki_provider import DeepwikiProvider

        return DeepwikiProvider()

    if name == "browser-run":
        # P6-A: Cloudflare Browser Run Quick Actions (Kitesurf engine by
        # default) — no optional install (httpx is core); auth is read from
        # the environment at CALL time (sops-exported on jupiterOS), so no
        # key is needed merely to construct the provider.
        from hyperresearch.web.browser_run_provider import BrowserRunProvider

        return BrowserRunProvider()

    if name == "tavily":
        try:
            from hyperresearch.web.tavily_provider import TavilyProvider

            return TavilyProvider()
        except ImportError:
            raise ImportError('tavily provider requires: pip install "hyperresearch[tavily]"')

    raise ValueError(
        f"Unknown web provider: {name!r}. Available: {', '.join(KNOWN_PROVIDER_NAMES)}"
    )


class ProviderAuthError(RuntimeError):
    """A provider's credentials are missing or unusable (auth-config error).

    Typed fall-through signal for the provider chain (P4-B review F1): a
    candidate that cannot authenticate cannot serve at all, which is exactly
    what the next candidate is for. Raised at call time (e.g.
    :class:`~hyperresearch.web.parallel_provider.ParallelAuthError`) or
    construction time. Plain RuntimeErrors still SURFACE — only this typed
    signal (and transport/5xx/429) falls through; 4xx schema errors surface.
    """


def _is_fall_through_error(exc: BaseException) -> bool:
    """Classify a CALL-time exception for chain fall-through (P4-B).

    Fall through ONLY on exact typed signals:

    * ``httpx.TransportError`` (connect/DNS/read failures, incl. timeouts);
    * :class:`ProviderAuthError` (call-time auth-config errors — e.g.
      ``ParallelAuthError`` when PARALLEL_API_KEY is missing);
    * :class:`~hyperresearch.web.parallel_provider.ParallelApiError` carrying
      status 429 or >= 500.

    Everything else surfaces untouched — plain RuntimeErrors, 4xx schema
    errors, and unknown exception types are bugs to show the user, not walls
    to route around. Construction-time failures are handled separately in
    ``_ChainedProvider._serve`` (they ALWAYS fall through: a missing optional
    SDK or a construct-time auth/config error means this candidate cannot
    serve at all, which is exactly what the next candidate is for).

    Documented limitation: tavily/exa wrap their SDKs, whose internal
    server/transport errors raise SDK-specific types that are deliberately
    NOT guessed-classified here — they surface rather than fall through.
    Chain fall-through is exact for the builtin+parallel pair; honest, no
    masking.
    """
    import httpx

    if isinstance(exc, httpx.TransportError):
        return True

    if isinstance(exc, ProviderAuthError):
        return True

    from hyperresearch.web.parallel_provider import ParallelApiError

    if isinstance(exc, ParallelApiError):
        status = exc.status_code
        return status is not None and (status == 429 or status >= 500)

    # P5-A: DeepWiki server-side failures (HTTP 429/5xx) fall through to
    # the next chain candidate, exactly like ParallelApiError above. 4xx
    # and tool-level (isError) failures surface — they are caller bugs.
    from hyperresearch.web.deepwiki_provider import DeepwikiApiError

    if isinstance(exc, DeepwikiApiError):
        status = exc.status_code
        return status is not None and (status == 429 or status >= 500)

    # P6-A: Browser Run server-side failures (HTTP 429/5xx) fall through;
    # 4xx (auth scope, bad request) surface. BrowserRunAuthError arrives via
    # the ProviderAuthError branch above.
    from hyperresearch.web.browser_run_provider import BrowserRunApiError

    if isinstance(exc, BrowserRunApiError):
        status = exc.status_code
        return status is not None and (status == 429 or status >= 500)

    return False


def _result_is_junk(result: WebResult, gates: JunkGates | None) -> bool:
    """Result-quality gate for chain fall-through (P4-B).

    A result counts as junk/empty when its content strips to "" OR
    ``WebResult.looks_like_junk`` returns a reason. A merely login-wall-looking
    result is NOT junk here unless the junk gates also fire — login walls
    belong to the escalation lane, not to the chain.
    """
    if not (result.content or "").strip():
        return True
    return result.looks_like_junk(gates or DEFAULT_GATES) is not None


def _results_are_junk(results: list[WebResult], gates: JunkGates | None) -> bool:
    """List-quality gate for search()/fetch_many() chain fall-through.

    Empty output, or output where EVERY result fails the junk gate, triggers
    fall-through. A mixed batch (any real content) is accepted as-is.
    """
    if not results:
        return True
    return all(_result_is_junk(r, gates) for r in results)


@runtime_checkable
class _BatchCapableProvider(Protocol):
    """Structural view of the duck-typed ``fetch_many`` extension.

    ``fetch_many`` deliberately extends (rather than joins) the public
    WebProvider Protocol — cli/fetch_batch.py consumes it via hasattr.
    This runtime-checkable protocol turns that duck-type into a real
    isinstance guard so chain delegation needs neither getattr nor casts.
    """

    def fetch_many(self, urls: list[str]) -> list[WebResult]: ...


class _ChainedProvider:
    """Ordered provider fallback chain behind the WebProvider protocol (P4-B).

    Not public API — build chains through :func:`resolve_web_provider`.

    Semantics:

    * Candidates are constructed LAZILY, one per turn, so a missing optional
      SDK in slot 2 never breaks slot 1. ANY construction failure falls
      through to the next candidate; if every construction fails, the LAST
      construction error is raised so the message matches what single-provider
      mode raises today.
    * Call-time exceptions fall through only when
      :func:`_is_fall_through_error` says so; anything else surfaces.
    * After every successful call ``self.name`` becomes the SERVING provider's
      name — the value recorded in the sources table / ``fetch_provider``
      frontmatter. The initial name is the first candidate's.
    * Each call starts again from the FIRST candidate (stateless), so a
      recovered upstream is retried on the next call.
    * Junk/empty outcomes try the next candidate. When every candidate yielded
      junk/empty, the LAST junk outcome is RETURNED as-is (never wrapped in a
      synthetic error), so caller-side junk gates produce their normal
      actionable error + escalation path. When every candidate RAISED, the
      last exception is re-raised.

    Provenance stability (P4-B review F3): a synchronous re-entrancy guard —
    nested calls made on this SAME instance while a top-level call is still
    in flight (e.g. an OA-rescue lane re-using the provider mid-processing)
    do NOT update the serving-name. Only a completed top-level call publishes
    its server. CONSEQUENTLY: consumers must read ``prov.name`` promptly
    after the call whose provenance they care about (all current call sites
    already do), and sequential later calls legitimately update it again.
    """

    def __init__(
        self,
        entries: list[tuple[str, Callable[[], WebProvider]]],
        gates: JunkGates | None,
    ) -> None:
        self._entries = entries
        self._gates = gates
        self.name = entries[0][0]
        #: Re-entrancy flag for serving-name bookkeeping (F3). While True,
        #: any _serve frame that did not OPEN the top-level window (i.e. a
        #: nested call on this same instance) is bookkeeping-suppressed.
        self._in_top_level = False
        # Duck-type preservation (P4-B review F2): expose fetch_many on the
        # INSTANCE only when some declared candidate can batch, so
        # cli/fetch_batch.py's hasattr(prov, "fetch_many") keeps routing
        # capability-less chains to per-URL fetching instead of discovering
        # at call time that the batch lane is missing. Never defined
        # unconditionally on the class.
        if any(name in _FETCH_MANY_PROVIDERS for name, _ in entries):
            self.fetch_many = self._fetch_many_batchable

    def _top_level(
        self,
        call: Callable[[WebProvider], _T],
        is_junk: Callable[[_T], bool],
        supports: Callable[[WebProvider], bool] | None = None,
    ) -> _T:
        """Run one chain operation inside a top-level window (F3).

        The frame that OPENS the window owns the serving-name bookkeeping;
        nested frames opened while the window is up do not touch ``name``.
        """
        owns_frame = not self._in_top_level
        outer = self._in_top_level
        self._in_top_level = True
        try:
            return self._serve(call, is_junk, supports=supports, record=owns_frame)
        finally:
            self._in_top_level = outer

    def _serve(
        self,
        call: Callable[[WebProvider], _T],
        is_junk: Callable[[_T], bool],
        supports: Callable[[WebProvider], bool] | None = None,
        record: bool = True,
    ) -> _T:
        """Run `call` against candidates in order with the chain semantics.

        `record` gates serving-name bookkeeping (success and junk paths use
        the SAME mechanism): True only for the frame that owns the top-level
        window, so nested/re-entrant calls cannot clobber the provenance of
        the in-flight outer call.
        """
        last_junk: tuple[str, _T] | None = None
        last_error: Exception | None = None
        for cand_name, factory in self._entries:
            try:
                provider = factory()
            except Exception as exc:
                # Construction failure == auth-config/import error for this
                # candidate; the next one takes the turn.
                last_error = exc
                continue
            if supports is not None and not supports(provider):
                # Capability mismatch (e.g. no fetch_many): this candidate
                # cannot serve THIS call shape at all. Not an error against
                # its other capabilities — skip without recording anything.
                continue
            try:
                outcome = call(provider)
            except Exception as exc:
                if _is_fall_through_error(exc):
                    last_error = exc
                    continue
                raise
            if is_junk(outcome):
                # Unified bookkeeping: junk records the candidate name too,
                # because its outcome is what the caller-side gates will see.
                last_junk = (cand_name, outcome)
                continue
            if record:
                self.name = cand_name
            return outcome
        if last_junk is not None:
            junk_name, junk_outcome = last_junk
            if record:
                self.name = junk_name
            return junk_outcome
        if last_error is None:
            # Only reachable when every candidate was capability-skipped.
            raise NotImplementedError(
                "no provider in the chain supports this operation: "
                + ", ".join(name for name, _ in self._entries)
            )
        raise last_error

    def fetch(self, url: str) -> WebResult:
        # MediaWiki lane FIRST: wiki URLs are served their clean native-API
        # text before any generic candidate renders the chrome-heavy page
        # (55k of nav soup vs 19k of prose on the Immunotherapy probe — see
        # hyperresearch/web/mediawiki.py). None = lane not applicable, and
        # the normal candidate chain serves exactly as before.
        from hyperresearch.web.mediawiki import fetch_mediawiki

        # Manual top-level window (mirrors _top_level): the lane is not a
        # chain candidate, so only the frame that OWNS the window records
        # the serving name (F3 re-entrancy discipline).
        owns_frame = not self._in_top_level
        outer = self._in_top_level
        self._in_top_level = True
        try:
            mw = fetch_mediawiki(url)
            if mw is not None:
                if owns_frame:
                    self.name = mw.metadata.get("provider", "mediawiki-api")
                return mw
            return self._serve(
                lambda p: p.fetch(url),
                lambda r: _result_is_junk(r, self._gates),
                record=owns_frame,
            )
        finally:
            self._in_top_level = outer

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        return self._top_level(
            lambda p: p.search(query, max_results=max_results),
            lambda rs: _results_are_junk(rs, self._gates),
        )

    def _fetch_many_batchable(self, urls: list[str]) -> list[WebResult]:
        """Batched fetch delegated to the first capable candidate.

        Attached to instances by __init__ ONLY when a declared candidate
        name is in _FETCH_MANY_PROVIDERS — see the F2 note there.

        MediaWiki pre-pass: wiki URLs are pulled out of the batch and
        served their clean native-API text by the lane; only the rest
        reach the generic batch lane (cli/fetch_batch.py fetches whole
        waves through here, so without the pre-pass most wikipedia
        fetches would miss the lane entirely). A MediawikiPageError from
        the pre-pass aborts the batch call — fetch_batch's fallback
        retries per-URL, where the raise lands on the one bad URL.
        """

        from hyperresearch.web.mediawiki import fetch_mediawiki

        served: dict[str, WebResult] = {}
        rest: list[str] = []
        for u in urls:
            mw = fetch_mediawiki(u)
            if mw is not None:
                served[u] = mw
            else:
                rest.append(u)

        if not rest:
            # Every URL went through the lane — no candidate serves, so
            # record the lane as the serving provider (same re-entrancy
            # suppression as fetch(): a nested call must not clobber the
            # in-flight outer call's provenance).
            if served and not self._in_top_level:
                first = next(iter(served.values()))
                self.name = first.metadata.get("provider", "mediawiki-api")
            return [served[u] for u in urls]

        def call(provider: WebProvider) -> list[WebResult]:
            # supports= below guarantees the isinstance holds; this guard is
            # defense-in-depth for direct callers of _serve.
            if not isinstance(provider, _BatchCapableProvider):  # pragma: no cover
                raise NotImplementedError(
                    f"provider {provider.name!r} does not implement fetch_many"
                )
            return provider.fetch_many(rest)

        batched = self._top_level(
            call,
            lambda rs: _results_are_junk(rs, self._gates),
            supports=lambda p: isinstance(p, _BatchCapableProvider),
        )

        if not served:
            return batched

        # Mixed wave: merge by original input order; batched results that
        # changed URL mid-fetch (redirects) keep their slot by appending.
        by_url = {r.url: r for r in batched}
        out: list[WebResult] = []
        seen: set[str] = set()
        for u in urls:
            if u in served:
                out.append(served[u])
                seen.add(u)
            elif u in by_url:
                out.append(by_url[u])
                seen.add(u)
        out.extend(r for r in batched if r.url not in seen)
        return out


def _default_provider_factory(
    name: str,
    *,
    profile: str | None,
    magic: bool,
    headless: bool,
    settings: FetchSettings | None,
    gates: JunkGates | None,
) -> Callable[[], WebProvider]:
    """Zero-arg factory resolving `name` through get_provider.

    get_provider is looked up via module globals at CALL time, so tests that
    monkeypatch ``hyperresearch.web.base.get_provider`` keep working unchanged
    through the chain.
    """

    def make() -> WebProvider:
        return get_provider(
            name,
            profile=profile,
            magic=magic,
            headless=headless,
            settings=settings,
            gates=gates,
        )

    return make


def resolve_web_provider(
    spec: str | list[str],
    *,
    profile: str | None = None,
    magic: bool = False,
    headless: bool = True,
    settings: FetchSettings | None = None,
    gates: JunkGates | None = None,
    _factories: Mapping[str, Callable[[], WebProvider]] | None = None,
) -> WebProvider:
    """Resolve the ``[web] provider`` config setting into ONE usable provider.

    Accepts EITHER the classic single name (``"parallel"``) OR an ordered
    fallback chain (``["parallel", "builtin"]``). A plain string behaves
    identically to :func:`get_provider` — it becomes a single-candidate
    chain. This is THE shared entry point for every call site that resolves
    a provider from config, so chain behavior cannot drift between them.

    Chain semantics live on :class:`_ChainedProvider`: lazy candidate
    construction, fall-through on transport errors / HTTP 5xx+429 /
    auth-config errors / junk-or-empty results, everything else surfaces.
    Whichever candidate serves a call becomes ``prov.name`` AFTER the call —
    that is the value recorded in the sources table and ``fetch_provider``
    frontmatter.

    Raises:
        ValueError: empty spec, a non-string entry, or an unknown provider
            name (the error names the offending position and lists the
            available names). Unknown names fail up front — before any
            network activity — rather than silently falling through.

    Test seam: ``_factories`` replaces the built-in name→factory registry so
    tests can inject fake providers with zero network and zero monkeypatching.
    """
    names = [spec] if isinstance(spec, str) else list(spec)
    if not names:
        raise ValueError(
            "[web] provider resolved to an empty candidate list. Name at least "
            'one provider, e.g. provider = ["parallel", "builtin"]. '
            f"Available: {', '.join(KNOWN_PROVIDER_NAMES)}"
        )
    known = set(_factories) if _factories is not None else set(KNOWN_PROVIDER_NAMES)
    available = ", ".join(sorted(known))
    for pos, entry in enumerate(names):
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(
                f"[web] provider entry at position {pos} must be a non-empty string; got {entry!r}"
            )
        if entry not in known:
            raise ValueError(
                f"Unknown web provider {entry!r} at position {pos} of the "
                f"[web] provider chain. Available: {available}"
            )

    entries: list[tuple[str, Callable[[], WebProvider]]] = []
    for name in names:
        if _factories is not None:
            entries.append((name, _factories[name]))
        else:
            entries.append(
                (
                    name,
                    _default_provider_factory(
                        name,
                        profile=profile,
                        magic=magic,
                        headless=headless,
                        settings=settings,
                        gates=gates,
                    ),
                )
            )
    return _ChainedProvider(entries, gates=gates)
