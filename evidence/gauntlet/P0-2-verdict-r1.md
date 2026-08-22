# P0-2 gauntlet round 1 — VERDICT: ours (variantB won blind)
- Disqualifiers found in upstream-config variantA on this host: <3.14 cap refuses install; crawl4ai in core deps uninstallable on 3.14 (lxml/playwright no cp314 wheels); all-extra inherits it.
- Biggest remaining gap in OURS (accepted finding F3): toolchain split-brain ruff py311 vs mypy python_version 3.14 vs classifiers 3.11-3.14. Resolution decided by coordinator: single language-level policy = 3.11 everywhere (mypy python_version="3.11"), runtime correctness proven by pytest on host 3.14. Keeps verbatim-leaning port honest about floor claim.
- Landmine noted: explicit [crawl4ai] extra remains uninstallable on 3.14 — documented opt-in tradeoff (PORTING-NOTES).
