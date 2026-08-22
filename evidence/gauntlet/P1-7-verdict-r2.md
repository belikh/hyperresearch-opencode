# P1-7 gauntlet r2 — VERDICT: OURS (blind win; supersedes VOID r1)
r1 was comparison-VOID (stale staging, coordinator error; audit defects D1-D6 all fixed in
the remediation commit f553545). r2 staged fresh trees /tmp/opencode/gauntlet/P1-7-r2,
scrubbed, randomized+sealed. Sidemap disclosure: B=ours, A=upstream ("swapped").
Critic EMPIRICALLY probed both trees (config round-trips, inverted ranges, negative knobs,
unknown levers, mid-rebuild DB failure, hostile tags/titles/dates).
VERDICT: B (ours) — rejects inverted dict-ranges/negative knobs, TOML-safe save round-trip,
[models] empty-inherit alias table present, lever fail-loud, atomic-ish rebuild, escaped
interpolation. Upstream side failed every one of those probes.
RESIDUAL GAP named by critic -> CLOSED in critic-gap closure wave:
- created[:7] month key unsanitized crashed write phase after stale unlink
  -> pre-flight fullmatch validation + staged-filename invariant + regression tests
  (falsified pre-fix: FileNotFoundError post-unlink destroyed prior indexes).
Also closed: double-skip defect in test_levers/test_dissertation_profile (unconditional
pytestmark removed; single accurate self-releasing skipif remains).
Zero indexgen tests upstream noted; ours now ships tests/test_core/test_indexgen.py.
