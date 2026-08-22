# P1-1 gauntlet round 1 — VOID (coordinator staging contamination)
The coordinator's de-identification sed deleted an entire code line carrying a
"# Delta vs upstream" TRAILING comment (our vault.py `def __exit__`) and the
stripped upstream copy lacked hooks.py/agent_docs.py needed by its own
conftest/vault. Critic therefore compared two artifacts BOTH damaged by staging,
not by their authors. Verdict discarded; not attributable to either side.
Ground-truth check afterward: repo vault.py HAS __exit__ (line 108) and NO
agent_docs import — port is clean on both counts.
Residual value kept: critic noted zero tests exercise Vault context-manager
protocol — filed as coverage follow-up for next builder.
Process fix: gauntlet staging must never transform code content; see
/tmp/opencode/gauntlet/PROTOCOL.md (comment-only-line stripping only, full-tree
staging so neither side loses intra-scope deps, neutral dir names only).
