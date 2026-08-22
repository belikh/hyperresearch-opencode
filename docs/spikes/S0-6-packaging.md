# S0-6 — Packaging on Python 3.14 (pymupdf wheel, extras, Crawl4AI)

Question: does the dependency story hold on the host's Python 3.14.5 —
pymupdf as a working wheel, `[all]` resolving without crawl4ai, and what
REALLY happens when Crawl4AI is requested?

Probed 2026-08-22 in the existing project venv
(`/home/io/Projects/hyperresearch-opencode/.venv`, pip 26.1.1).

## Method

Four checks, escalating:

1. Import + version in the venv;
2. Exercise the wheel: render a minimal PDF with text, save, reopen, extract,
   assert round-trip (`/tmp/opencode/s06_pymupdf_smoke.py`);
3. `.venv/bin/pip install ".[all]" --dry-run` — must resolve without crawl4ai;
4. `pip install "Crawl4AI==0.7.3" --dry-run`, then (because of what the dry-run
   showed) a REAL install into a throwaway venv `/tmp/opencode/s06-c4-venv`.

Round 2 (post-countersign F-CS3): a REAL install of this repo with `[all]`
into a CLEAN venv `/tmp/opencode/s06-clean` (`python3 -m venv`, no shared
site-packages, pip cache bypassed via `--no-cache-dir`), upgrading row 2 of
the verdict table from dry-run-only to real-install proof:

```
$ python3 -m venv /tmp/opencode/s06-clean
$ /tmp/opencode/s06-clean/bin/pip install --no-cache-dir \
    "/home/io/Projects/hyperresearch-opencode[all]"        # exit=0
...
Building wheel for hyperresearch (pyproject.toml): finished with status 'done'
Successfully built hyperresearch
Successfully installed ... hyperresearch-0.10.0.post1 ... pymupdf-1.28.2 ...
# note: NO crawl4ai anywhere in the installed set

## Sanity check on the same clean venv
Python 3.14.7
pymupdf 1.28.2 | hyperresearch import OK
hpr CLI: OK (exit=0)
WARNING: Package(s) not found: crawl4ai
```

Raw file: `evidence/spikes/S0-6-clean-venv-install.txt`.

## Transcript

```
$ .venv/bin/python -c "import pymupdf; print(pymupdf.__version__)"
pymupdf 1.28.2

$ .venv/bin/python /tmp/opencode/s06_pymupdf_smoke.py          # exit=0
python pymupdf wheel check: version=1.28.2
rendered: /tmp/s06-6sqv5amy/smoke.pdf (1053 bytes)
extracted text ---
HYPERRESEARCH S0-6 WHEEL SMOKE
pdf -> text round trip on cp314
round-trip OK: True

$ .venv/bin/pip install ".[all]" --dry-run                     # exit=0
...
Would install hyperresearch-0.10.0.post1 regex-2026.7.19 tavily-python-0.7.27 tiktoken-0.14.0
# note: NO crawl4ai anywhere in the resolved set

$ .venv/bin/pip install "Crawl4AI==0.7.3" --dry-run            # exit=0 (!)
Collecting lxml~=5.3 (from Crawl4AI==0.7.3)
  Using cached lxml-5.4.0.tar.gz (3.7 MB)                      ← sdist, not a wheel
...
Would install Crawl4AI-0.7.3 ... lxml-5.4.0 ...

$ python3 -m venv /tmp/opencode/s06-c4-venv && /tmp/opencode/s06-c4-venv/bin/pip install "Crawl4AI==0.7.3"
                                                               # exit=1
× Failed to build installable wheels for some pyproject.toml based projects
╰─> lxml
    error: subprocess-exited-with-error
    × Building wheel for lxml (pyproject.toml) did not run successfully.
```

Raw files: `evidence/spikes/S0-6-pymupdf-import-version.txt`,
`S0-6-pymupdf-smoke.txt`, `S0-6-all-extra-dryrun-resolves.txt`,
`S0-6-crawl4ai-dryrun-metadata-only.txt`,
`S0-6-crawl4ai-real-install-fails.txt`.

### Finding F-METADATA (honest trap avoided)

The Crawl4AI **dry-run exits 0** — metadata resolution alone succeeds because
lxml 5.4.0's *sdist* satisfies `lxml~=5.3`. A dry-run-only verdict would have
been a false pass. The real install fails: pip must build lxml from that
sdist and the build dies on cpython-3.14. Upstream's stated blocker
(lxml~=5.3 unbuildable on 3.14) therefore still holds in practice.

## Verdict: CONFIRMED (tiered)

| Claim | Tier | Evidence |
|---|---|---|
| pymupdf installs as cp314 wheel AND works (render→text round trip) | CONFIRMED | import 1.28.2 + smoke exit=0 |
| `[all]` extra resolves on 3.14 without crawl4ai | CONFIRMED (real install) | CLEAN venv `/tmp/opencode/s06-clean` real install exit=0; crawl4ai absent from installed set (`pip show crawl4ai` → not found); `hpr` CLI + `import hyperresearch` OK on the same venv |
| Crawl4AI 0.7.3 installable on host 3.14 | REFUTED | real-install exit=1 at lxml wheel build |
| Demoting crawl4ai to opt-in extra was correct policy | CONFIRMED | rows above combined |

Row 2 was upgraded from dry-run-only to real-install proof after countersign
finding F-CS3, which correctly noted that F-METADATA below makes a dry-run
insufficient for any installability claim.

## Fallback if refuted

Not applicable to pymupdf/[all] (both confirmed). For crawl4ai the fallback
IS the current design: browser-fetch lane stays opt-in via
`hyperresearch[crawl4ai]` for users on ≤3.13, and opencode replaces it on the
supported host. If a future lxml release ships cp314 wheels satisfying the
pin, re-run this spike before reconsidering.

## Residual risk

- ~~Dry-run green ≠ installable~~: recorded as finding F-METADATA; the `[all]`
  claim now carries real-install proof in a clean venv (round 2), and future
  packaging spikes must do real installs for any claim stronger than
  "metadata resolves". Remaining caveat: the clean-venv proof is one host, one
  Python (3.14.7); a fresh `pip install` can still drift with new upstream
  releases of core deps.
- Crawl4AI status can change upstream (new lxml or Crawl4AI releases); the
  extra keeps it available to ≤3.13 users regardless. The clean-venv install
  deliberately did NOT request the `crawl4ai` extra — that lane remains
  refuted on 3.14 per row 3.
