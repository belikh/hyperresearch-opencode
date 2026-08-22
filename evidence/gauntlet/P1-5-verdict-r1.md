# P1-5 gauntlet r1 — VERDICT: OURS (blind win)
Staging: freshly rsynced trees under /tmp/opencode/gauntlet/P1-5 (protocol amendment
post two VOID rounds); sides randomized then sealed; port-note strings scrubbed from
staged copies only. Sidemap disclosure: A=ours, B=upstream ("straight").
Critic read both fully (3 core modules + 3 test batteries), diffed lineage, ran its own probes.
VERDICT: A (ours) — superset: netguard-guarded redirect lanes + exact/suffix DOI-host match
+ strict typing + ~270 falsifiable lines of extra tests vs upstream's raw follow_redirects.
WINNER_GAP (dispositions):
- TOCTOU/DNS-rebinding window in check_oa_url + page/pdf lanes leaning on provider internals:
  FILED (DNS rebinding documented out of scope since P1-4 sweep; per-hop revalidation covers
  JSON/JATS lanes).
- Log-wording coupling in SSRF tests: accepted cosmetic; contract assertions dominate.
Shared defects noted by critic (User-Agent placeholder mailto, tautological ranking assert
tests/test_source_ranking.py:197): FILED in PORTING-NOTES known-inherited issues.
