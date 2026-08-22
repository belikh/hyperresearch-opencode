# S0-2 — Agents dir naming (`agent` vs `agents`)

Question: do both `.opencode/agent/<name>.md` and `.opencode/agents/<name>.md`
load? What are the installer implications?

Probed on opencode 1.18.21, host Linux, 2026-08-22. Prior empirical evidence:
`/tmp/opencode/spike-evidence-coordinator.md` (S0-2 section) — both dirs
listed there, with one cold-init miss observed.

## Method

Fresh scratch tree `/tmp/opencode/s02-agents` (not a git repo), two probe
files created back-to-back:

- `.opencode/agent/probe-singular.md`  (`mode: all`)
- `.opencode/agents/probe-plural.md`   (`mode: all`)

Then `opencode agent list` from that cwd **immediately** after creation (the
cold run), and again (the warm run). Name lines extracted from both runs and
diffed. Corroborating context: the same session's S0-1 runs picked up freshly
written `nester.md`/`driver.md` on their first invocations.

## Transcript

```
$ opencode agent list          # cold: cwd = /tmp/opencode/s02-agents, files just written; exit=0
build (primary)
compaction (primary)
explore (subagent)
general (subagent)
plan (primary)
summary (primary)
title (primary)
architect (subagent)
...
probe-plural (all)        ← .opencode/agents/  (plural)
probe-singular (all)      ← .opencode/agent/   (singular)
...
$ opencode agent list          # warm re-run; exit=0
$ grep -E '^[a-zA-Z0-9_-]+ \(' warm | diff - names-from-cold  → IDENTICAL
```

Both project probes appear in the very first listing, merged with built-ins
and the host's global agents (`~/.config/opencode/agents/`). Full trimmed
name list: `evidence/spikes/S0-2-agent-list-names.txt`.

Mode observation: both show `(all)` — frontmatter `mode:` was set to `all`
here, and coordinator evidence showed files with no `mode:` also render
`(all)`, i.e. default mode is primary+subagent unless restricted. Pipeline
agents in this port must set `mode: subagent` explicitly.

## Cold-init anomaly

- Coordinator probe (prior session): first `agent list` in a brand-new tree
  once failed to show newly written agents; every subsequent run listed them.
- This session: NOT reproduced — the fresh-tree cold run listed both probes
  immediately, and the S0-1 scratch agents were also picked up first try.
  Frequency so far: 1 miss across ~5 fresh trees over two sessions.
  Honest status: intermittent, unreproduced here, root cause unknown
  (cold init vs cache).

## Verdict: CONFIRMED

Both directories load; agents from `.opencode/agent/` and `.opencode/agents/`
appear together in `opencode agent list`, merged with built-ins and global
user agents.

## Installer implication / fallback

Discovery can intermittently lag or one-shot-fail on a freshly created tree.
Idempotent installs should:

1. Re-run agent discovery after writing agent files rather than trusting a
   single first-run check;
2. Treat "(agent not listed on first try)" as retryable, not fatal;
3. Verify installs by re-listing, not by trusting write success alone;
4. If the anomaly ever becomes deterministic, standardize the port on ONE
   directory (`.opencode/agents/`, the plural form used by our roster).

## Residual risk

Anomaly root cause undiagnosed and frequency unquantified (seen once across
~5 fresh trees). A deterministic miss would only affect self-installed roster
agents on first launch; mitigation above bounds the impact.
