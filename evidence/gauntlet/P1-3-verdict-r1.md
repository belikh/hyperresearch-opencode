# P1-3 gauntlet round 1 — VERDICT: critic-won (two findings, fixed as deltas)

Blind adversarial review of the P1-3 graph layer. Piece verified against its
acceptance criteria; two latent defects found in code inherited verbatim from
upstream v0.10.0. Both are fixed in this port during P1-2 (side-fix scope),
each with a regression test that fails against pre-fix code.

## Findings

1. **MEDIUM G13-LSH-BANDING** — `core/similarity.py` `lsh_candidates`
   (~line 62 upstream / :63 ours): `rows_per_band = num_perm // bands` is
   unguarded, so `bands > num_perm` yields `rows_per_band == 0`. Every band
   then hashes the empty slice `sig[0:0]`, all docs land in one bucket per
   band, and the function returns ALL-PAIRS candidates — i.e. every pair of
   unrelated documents becomes a "candidate duplicate". Empirically
   reproduced against upstream reference (bands=200, num_perm=128 → the
   unrelated pair is returned). This silently defeats LSH's purpose: the
   caller (future dedup CLI) would O(n²)-compare or false-positive on every
   vault. Disposition: FIX — explicit guard raising `ValueError` rather than
   clamping: clamping would silently change recall semantics of the banding
   scheme (LSH probability guarantees only hold while bands×rows ≤ num_perm),
   and a dedup tool must fail loudly, not quietly degrade into either
   all-pairs scanning or silent misses. Guard condition covers the whole
   invalid domain: `not 0 < bands <= num_perm` (also rejects `bands < 1`,
   which previously ZeroDivisionError'd at 0 and returned an empty set for
   negatives).

2. **LOW G13-REFVOCAB-ORDER** — `core/linker.py` ref_vocab population
   (:29-40): `SELECT id, title FROM notes ...` (and the aliases query) have
   no ORDER BY, so with duplicate titles the dict's last-wins assignment
   picks whichever row SQLite happens to return last — plan-dependent,
   nondeterministic across environments/vacuum/schema changes. A third note
   mentioning that title could be linked to either duplicate.
   Disposition: FIX — make resolution deterministic by ordering both
   population queries by stable unique keys (`ORDER BY id` for notes;
   `ORDER BY alias, note_id` for aliases), keeping the existing last-wins
   assignment: the winner is now well-defined (highest note id wins for
   duplicate titles; highest note_id wins for duplicate alias texts).
   Regression test uses duplicate-title fixtures and asserts the exact
   deterministic target.

Both fixes are documented as deliberate deltas in `PORTING-NOTES.md §P1-2`.
Everything else in P1-3 passed review unchanged (byte-faithful modulo the
declared strict-mypy annotation deltas recorded there).
