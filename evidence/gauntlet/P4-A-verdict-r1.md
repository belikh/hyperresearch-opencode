# P4-A gauntlet verdict (round 1) — `parallel` named provider

Blind fresh-context judge. Materials staged under /tmp/opencode/p4-gauntlet/pa/
(candidate_a = submission; candidate_b/c = sibling exa/tavily style comparators,
one byte-identical alternate noted by judge; api_spec.json = Parallel OpenAPI).
Staged copies py_compile-gated before judging (protocol from P1-12 void).

VERDICT: **ACCEPT** (ours wins r1).

BIGGEST GAP (judge): malformed-200-body decode escaped unclassified
(cannot trigger on spec-conformant traffic; not material to acceptance).

Findings -> dispositions (fix wave landed same session, gates re-run green):
1. minor  X-API-Key vs spec-literal `x-api-key`      -> fixed (lowercase literal)
2. minor  200 non-object/invalid-JSON body unclassified -> fixed (ParallelApiError status_code=200)
3. minor  fetch_many duplicate URLs inflate results   -> fixed (first-seen dedupe post-validation)
4. nit    error envelope ref_id dropped               -> fixed ("(ref <id>)" in message)
5. nit    _pin_dns offline-safety assumption          -> accepted (numeric-IP tests already cover)
6. nit    no negative authorization-header assert     -> fixed
7. nit    metadata["provider"] surplus vs siblings    -> rejected as defect (deliberate divergence)

Fix-wave gates on final state: pytest tests/ exit 0 (25 pre-existing skips),
ruff All checks passed!, mypy --strict Success (97 source files).
Builder self-review round 2: ship (tmpfs-exhaustion false-fail incident root-caused
to unrelated /tmp debris; cleaned; re-run clean).

Live-network smoke: NOT RUN — PARALLEL_API_KEY absent from environment at close.
