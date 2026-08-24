# Phase 4 live smoke — Parallel provider against api.parallel.ai (2026-08-24)

Mandatory per dispatch; PARALLEL_API_KEY exported from ~/.bashrc into the
shell before each invocation (bashrc itself has an interactivity guard, so
the export is explicit per shell). Vault: throwaway at /tmp/opencode/smoke-vault
(`hpr init`, then `config set web.parallel_search_lane true`).

## Arm 1 — search-web verb (P4-C) through the parallel provider (P4-A)
Command: `hpr search-web "parallel AI text processing API" --provider parallel -n 5 -j`
Exit 0. Raw envelope: `search-web-live.json` (5 rows; url/title/content/
provider stamped "parallel"). First run WITHOUT the key env produced the
actionable call-time error (`search-web-nokey.json`) — kept as evidence for
the missing-key error-text requirement.

## Arm 2 — fetch through the parallel provider (P4-A -> /v1/extract full_content)
Command: `hpr fetch "https://en.wikipedia.org/wiki/Extract,_transform,_load" --provider parallel -j`
Exit 0. Raw envelope: `fetch-parallel-live.json` — note_id
`extract-transform-load-wikipedia`, word_count 6312, provider "parallel";
content passed the existing junk/login-wall gates unmodified and landed as a
fenced note in the vault (provenance header shown in the transcript below).

Both arms zero-mock: live HTTPS to api.parallel.ai, x-api-key auth,
response mapped by src/hyperresearch/web/parallel_provider.py.
