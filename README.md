# hyperresearch-opencode

A port of [jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch) ("the most powerful deep research harness") from Claude Code to [opencode](https://opencode.ai).

Same deep-research machine, rebuilt on opencode primitives:

- Tier-adaptive 16-step research pipeline (light / full / dissertation)
- Parallel critic/subagent roster with model-map profiles
- Patch-only draft modification enforced via opencode agent tool locks + plugins
- Persistent vault: markdown notes as truth, SQLite index as cache (search, lint, graph, PageRank)
- Resumable budgeted runs with ship-gate lint battery
- Academic-APIs-first fetch lane with Unpaywall/Europe PMC open-access recovery and untrusted-source fencing
- MCP server and local web UI

Public contract preserved: `hyperresearch <cmd>` / `hpr <cmd>` CLI and `/hyperresearch <prompt>` inside opencode.

## Status

Planned / scaffolding. Execution follows an OpenUltraCode gauntlet loop: each piece is built by an implementer and judged blind against the upstream source by a separate adversarial critic until ours wins. Progress: `HYPERRESEARCH-OPENCODE-PROGRESS.md` (added during Phase 0).

## Attribution

Upstream: [jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch) by Jordan Gibbs, MIT licensed. This port adapts that code under the same license.
