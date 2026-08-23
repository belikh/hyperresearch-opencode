# P1-10 gauntlet r1 — VERDICT: OURS (blind win)
Staging /tmp/opencode/gauntlet/P1-10: source-only (asymmetric test sets disclosed), fresh
rsync, scrubbed, randomized+sealed. Sidemap: A=ours, B=upstream. Critic confirmed our
strict-mypy renames/guards are necessary (reverting them yields 5 mypy errors) and our
lint hooks-guard prevents a whole-CLI ImportError. VERDICT: A.
NAMED GAP (shared-inherited fail-open lint) -> CLOSED in fail-closed remediation wave:
F-1 errors>0 now exit 1 with ok:false LINT_ERRORS envelope naming failing rules; ship-gate
trace proven end-to-end (verify_run imports the lint check fns, finish_run persists
failed_checks names, run finish prints FAIL <name> and exits 1).
F-2 --rule validated against RULES (UNKNOWN_RULE exit 1); stale-indexes implemented with
minimal true semantics (index `updated:` marker vs newest note mtime; warning severity).
F-3 setup child-script injection closed (profile name via argv, not spliced into -c source;
pre-fix payload proven reaching child main() as code).
STAYS FILED (inherited): NO_VAULT envelope gaps in config_cmd; escalation ingest linear
scan + uncaught body_file read; repair bare-except swallowing; error-contract variety.
