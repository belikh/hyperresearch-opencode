# P1-4 gauntlet round 1 — VERDICT: ours-won blind; 4 findings fixed as hardening deltas

Blind adversarial review of the P1-4 web layer (providers/base + fetcher +
PDF extraction + junk gates). Our port won the blind comparison; all four
findings are latent defects inherited verbatim from upstream v0.10.0
(diff-checked against `/tmp/opencode/hyperresearch-reference`). Disposition:
FIX in this port during the P1-4 hardening wave — agent-chosen URLs make the
SSRF finding critical pre-E2E, and data-integrity/security trumps verbatim
per the P1-1/P1-2 precedent. Each fix carries a regression test proven to
fail against pre-fix code (git-stash round).

## Findings

1. **HIGH SSRF-FETCHLANES** — `web/crawl4ai_provider.py::_fetch_pdf`
   (~upstream :147 / ours ~:161-168) calls
   `httpx.get(url, follow_redirects=True)` with no scheme/host/IP validation;
   same disease in `web/builtin.py` HTML lane (~:79 httpx,
   ~:94 urllib auto-follow). PoC (live): fetched
   `http://127.0.0.1:<port>/hr/salaries.pdf` straight into a vault-bound
   WebResult, and a public-shaped URL answering `302 -> http://127.0.0.1/...`
   was followed automatically into loopback — both land in vault-bound
   results. Agent-chosen URLs make this critical before any E2E wiring.
   Disposition: FIX via new `web/_netguard.py::validate_url_public` (scheme
   allowlist {http,https}; DNS resolution with EVERY returned address required
   globally routable — loopback, RFC1918+ULA, link-local incl. the
   169.254.169.254 metadata service, unspecified, documentation/benchmarking
   ranges) applied at `_fetch_pdf` BEFORE the request and on EVERY redirect
   hop via manual redirect following (`follow_redirects=False`, max 5 hops),
   plus the builtin HTML lanes (httpx manual hops; urllib validating redirect
   handler). DNS rebinding (TOCTOU between check and connect) documented
   out of scope.

2. **MEDIUM JUNKGATE-INVISIBLE-PADDING** — `web/base.py::looks_like_junk`
   counts zero-width/invisible padding (ZWSP U+200B, ZWNJ/ZWJ, BOM U+FEFF,
   soft hyphen U+00AD, word joiner U+2060, …) toward `min_content_chars`, so
   homoglyph/ZWSP-spam pages pass the near-empty gate; inserting invisibles
   inside signal phrases ("Just a moment") also splits the bot/error-page
   substring matches. Disposition: FIX — strip the invisible set before
   length accounting AND before signal matching normalization, in both
   `looks_like_junk` (near-empty, cookie-wall length, cf/error/search/pdf
   signal windows) and its twin gate `looks_like_login_wall` (same defect
   class, same file).

3. **ENV-CONDITIONAL MYPY DIRT** — `web/tavily_provider.py:45` carries an
   inline `# type: ignore[import-not-found]` that becomes WRONG-CODE (unused
   ignore → strict gate failure) whenever tavily-python IS installed;
   `web/exa_provider.py:47` carries NO ignore, so the strict gate fails with
   [import-not-found] whenever exa-py is ABSENT (dev extras install it, so
   CI never saw it). Disposition: FIX env-independently —
   `[tool.mypy.overrides] ignore_missing_imports` for `tavily.*`/`exa_py.*`,
   brittle inline ignore dropped; proven clean in BOTH presence
   configurations without touching the project venv (see §Proof).

4. **LOW ARXIV-HOST-SPOOF** — `crawl4ai_provider._is_pdf_url` (:51 upstream /
   :62 ours) lane-chooses PDF handling via `"arxiv.org" in parsed.netloc`, so
   `notarxiv.org.evil.com` routes down the arXiv lane; the abs→pdf rewrite in
   `_fetch_pdf` (`"arxiv.org/abs/" in url`) is substring-based the same way.
   Lane choice only (no fetch happens on this check alone). Disposition:
   FIX with exact-host/suffix match (`hostname == "arxiv.org"` or
   `hostname.endswith(".arxiv.org")`) in both spots while in the file.

## File-only known-inherited issues (FILED, NOT FIXED)

Recorded in PORTING-NOTES.md §P1-4 "Known inherited issues"; not remediated
in this wave by design: charset decode utf-8-replace discards cp1252 pages as
binary (needs a charset-detection dependency — deferred); login-wall/bot
heuristics false-positive on prose mentioning logins/Cloudflare (upstream
design); `fetch_many` zip(strict=False) ordering assumption + synchronous PDF
fetch inside the async lane (perf/ordering, upstream design); fetcher's
interim ModuleNotFoundError paths for core.escalation / cli.fetch._save_assets
land with P1-8/P1-10 (sequenced intentionally).

## Proof obligations accepted by the fix wave

- Redirect-to-loopback and literal-loopback/metadata URLs rejected with clear
  errors on every guarded lane; normal public URLs pass.
- ZWSP-padded spam classified junk; legit non-Latin text unaffected.
- `notarxiv.org.evil.com` no longer lane-chooses arXiv.
- `mypy src` strict clean with (a) exa present/tavily absent [project venv],
  (b) both absent [--python-executable system python], (c) stub-less tavily
  present injected via PYTHONPATH — pre-fix code demonstrated dirty in (b)/(c).
