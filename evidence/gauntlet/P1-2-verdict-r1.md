# P1-2 gauntlet r1 — VERDICT: ours (treeA) wins blind
- Logic drift beyond declared deltas: NONE (19 hunks all annotations or declared fixes).
- Claim i (LSH banding guard) VERIFIED BY EXECUTION: upstream silently returns all-pairs candidates (bands=16,num_perm=8) and crashes ZeroDivision on bands=0; ours raises ValueError; regression tests present.
- Claim ii (deterministic ref_vocab) VERIFIED BY EXECUTION: upstream winner flips with insertion order; ours stable highest-id.
- Ours isolated suite: 166 passed/2 skipped; mypy strict 0 errors/28 files. No weakened/dropped tests (test_fts byte-identical).
- Open findings (inherited upstream debt, disposition -> fix in P1-5 wave unless noted):
  F1 MEDIUM bm25 f-string interpolation of unvalidated ranking weights into SQL (fts.py:119) - live statement restructuring proven.
  F2 MEDIUM before-date boundary excludes entire final day (filters.py:59-62) - live proven.
  F3 LOW-MED operator-sniffing passthrough allows FTS5 column-scoped grammar injection (fts.py:40).
  F4 LOW has_backlinks=False silently ignored (filters.py:99).
