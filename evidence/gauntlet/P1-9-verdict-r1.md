# P1-9 gauntlet r1 — VERDICT: OURS (blind win)
Staging: /tmp/opencode/gauntlet/P1-9 (source-only cli group modules, no __init__ either side),
scrubbed, randomized+sealed. Sidemap: B=ours, A=upstream. Critic verified git behaviors
against a real repo (rc checks) — our git_cmd separator/pathspec split and "??" porcelain key
proven correct where upstream's variants fail outright.
VERDICT: B (ours).
CLOSED in closure wave (were OURS-side gaps or cheap security wins):
- `index show` path escape -> containment + INVALID_PATH envelope (falsified pre-fix:
  served <vault>/secret.md outside index_dir, exit 0).
- `note mv` vault-boundary escape + silent collision overwrite -> containment + DEST_EXISTS
  envelope (three falsifying tests).
- dangling `[N]` citations silently dropped in citecheck -> recorded dangling (ship-gate effect).
STAYS FILED (inherited, core-out-of-ownership or behavioral-parity):
- link --dry-run writes wiki-links before sync gate (fix needs dry-run-aware linker; core/).
- NO_VAULT envelope inconsistency across ~half verbs (upstream-wide; uniform envelope is a
  cross-cutting delta deferred to reconciler with written reason).
- batch.py dead-code _batch_update_files / partial-mutation aborts (filed).
- repair --docs no-op honesty: core/agent_docs.py port ASSIGNED to P1-10 scope so the flag
  becomes real and help text truthful.
