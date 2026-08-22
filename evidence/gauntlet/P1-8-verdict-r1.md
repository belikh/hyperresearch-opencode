# P1-8 gauntlet r1 — VERDICT: OURS (blind win)
Staging: /tmp/opencode/gauntlet/P1-8 (source-only; test sets asymmetric across trees due to
piece sequencing — disclosed to keep comparison fair), scrubbed, randomized+sealed.
Sidemap: B=ours, A=upstream. Trees runtime-identical in logic; ours adds strict-mypy work.
VERDICT: B (ours) — differentiator was the declared strict-mypy gate which upstream fails wholesale.
NAMED GAP -> CLOSED in closure wave: module-level Vault annotation imports moved behind
TYPE_CHECKING in runs/escalation/citecheck/claims (grep-verified zero runtime uses).
INHERITED DEFECTS FILED NOT FIXED (architectural, upstream-shared; PORTING-NOTES):
unlocked add_spend/set_step/record_event manifest races; finish_run without state-machine
precondition; escalation claim_next lacks lease/requeue; COUNT-then-INSERT enqueue race;
shared .json.tmp path; resume retry without attempt cap; mechanical auto-pass substring
numeral match (fail-open direction documented); claims raw-text FTS MATCH + 64-bit hash dedup.
