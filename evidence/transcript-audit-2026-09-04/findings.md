# Transcript audit: what breaks when agents run hyperresearch

**Date:** 2026-09-04 · **Corpus:** 445 hyperresearch-touching sessions in
`~/.local/share/opencode/opencode.db` (525 sessions, 92,487 parts total),
spanning 2026-08-26 → 2026-09-04 across 8 vaults (songs, jupiter-os,
ha-linux-agent, model_router, ha-strategy, lgtv-webos-homeassistant,
jupiterCare, ~/brisbane-airport). 12,641 tool calls extracted and classified
(12,495 bash + 146 skill invocations).

## Headline

The user's hypothesis is confirmed and quantified. **43% of all bash calls in
hyperresearch sessions (5,367 / 12,495) are hand-written inline Python**,
median 446 chars each, ~2.7 MiB of throwaway script text across the corpus.
The agents are not doing data science — they have written the same four
adapter scripts hundreds of times each because the CLI's output layer is not
agent-ergonomic:

| Hand-rolled pattern | Calls | What it compensates for |
|---|---|---|
| `note show … -j \| python3 -c …` | 2,121 | no agent-friendly body reader (818 char-window body slices, 667 field extractions) |
| parse `search`/`note list`/`claims`/`tags`/`escalation` JSON | ~1,100 | inconsistent `data` envelope; no `--fields`/TSV output |
| run-artefact schema probes (`print(type(d))`, `list(d.keys())`) | 92+ | undocumented JSON schemas for loci/contradiction-graph/claims files |
| report metrics (word count, headings, citation density) | 16 | `run verify` does this but skills don't mandate it |
| string-replace editing + JSON surgery on logs | ~50 | patcher/polish ergonomics |

Direct damage: **398 hard Python errors** (166 KeyError, 59 TypeError, 55
AttributeError, 35 other tracebacks, 33 JSONDecodeError, …), **181
near-identical retries** in-place, plus 617 `isinstance` defensive chains and
1,658 multi-`.get()` chains — pure uncertainty tax. 1,827 bash calls across
107 sessions stage JSON through `/tmp/opencode/` purely to work around tool
output truncation (51,200-byte cap) that full-body `-j` output trips.

## Failure catalogue (ranked by cost)

### F1. Inline Python as the CLI's missing output adapter — the big one

**F1a. Envelope instability.** Verified live against 0.10.0.post1 — sibling
commands return five different `data` shapes:

| command | `data` shape |
|---|---|
| `note show ID -j` (hit) | the note dict itself |
| `note show ID -j` (miss) | **no `data` key at all** (`{ok,error,error_code}`) |
| `note show ID1 ID2 -j` | `{notes:[], not_found:[]}` |
| `note list -j` | bare list |
| `search -j` | `{query,results,total}` |
| `escalation list -j` | `{items,stats}` |

74 transcripts hits of `KeyError: 'notes'` and 22 `KeyError: 'data'` trace
directly to agents guessing the wrong arm. Every fetcher/investigator session
opens with a schema-discovery probe before it can read anything.

**F1b. No windowed body reader.** Long notes (15 KB+ JSON each) exceed the
bash tool's 51,200-byte output cap, so agents invented the staging dance:
`note show ids -j > /tmp/opencode/batchN.json` → python to slice
`n['body'][13000:21000]` → write `.txt` → read. 818 body-slice reads; the
evidence is in every depth-investigator and draft-orchestrator session (e.g.
ses_fae841efaffez4Wx, ses_fb09520e3ffeO39v). `--raw` exists but is mentioned
nowhere in the skills and can't do character windows.

**F1c. Truncation → JSON parse failures.** When agents parse the persisted
truncated tool-output file with `json.loads(t[idx:])` it fails mid-JSON
(33 JSONDecodeErrors, e.g. ses_fb9cb7ff0ffejhlAJw).

**F1d. Undocumented artefact schemas.** `loci.json`,
`contradiction-graph.json`, `claims-*.json`, `cite-check-pairs.json`,
`polish-log.json` are read via ad-hoc python with `type()`/`keys()` probes
each time (43+43+37+35 file-read clusters).

### F2. `fetch` reports duplicates as errors
`"ok": false, "URL already fetched as note 'X'"` — 64 occurrences. Dedup is a
*success* but fetcher agents treat the ok:false as failure and burn turns
deciding whether to re-fetch. (Genuine web noise — 404s etc. — is separate
and unavoidable.)

### F3. Skills prescribe parsing without a method
7,956 CLI invocations used a JSON flag; **63 used jq** (0.8%) even though jq
is on PATH. The skills say "parse the `vault_tag` field from the response"
with no canonical recipe, so every agent invents a python one-liner. None of
the 16 skills or 15 agent docs mention `jq`, `--raw`, or `--meta`.

### F4. Synthesizer Write lock — ALREADY FIXED
`permission: {edit: deny}` collapsed edit+write+patch and killed step 11
mid-run (diagnostic sessions ses_f9b2bdb8cffev0KQ70tWAX2Dkh,
ses_faa56886cffeTPr8RU9s32EH5h show the synthesizer with no write tool,
attempting `ha_write_file` as a fallback). Fixed by commit 5548993 (F-B1);
recorded here so it isn't re-diagnosed.

### F5. Friction papercuts
- `hyperresearch` typed bare → 23 `command not found` (full venv path is the
  documented convention; agents forget; no PATH shim).
- 154 `--help` invocations across 80 sessions — discoverability tax paid
  again per session.
- `run verify` invoked only 24×/7 sessions while agents hand-rolled the same
  metrics 16×/9 sessions — the ship gate exists but the step skills don't
  force it.
- One-off: `search-web` lane-disabled/builtin-provider errors surfaced as
  confusing config round-trips in fresh vaults (ses_fb9fc80e6ffeQoJ4vC).

### F6. Silent subagent deaths (environment, not hyperresearch)
Dozens of 1–2 part subagent sessions (polish "zen/spark/relay" retries,
draft retries) produced nothing — the orchestrator's own notes blame model
routing ("every session that starts with the default model produces zero
output", ses_fc3849c02ffeOPJ7Nb). Out of scope for the CLI, but the run
manifest's `blocked_on` should surface "subagent returned empty" so resume
doesn't blindly respawn.

## Recommendations — explicit scripts the agents should run instead

Ordered by (evidence volume × implementation cost). R1–R3 are the payload;
they delete ~80% of the inline Python.

### R1. Stabilise the JSON contract and add `--jq` (kills the envelope tax)
- Every command returns `data` as an **object with a named payload**:
  `{ok, data: {items: [...], count, ...}}`. `note list`, `tags`, `search`
  results, `escalation items`, `claims` all use `items`.
- Errors keep `data: null` (never omit the key) plus stable `error_code`.
- Add a global `--jq <expr>` flag evaluated server-side, so the canonical
  parse is `… -j --jq '.data.items[].id'` with zero python. Cheap: typer
  callback + one post-render hook in the output layer
  (`src/hyperresearch/cli/_output.py`).
- Document the envelope once in AGENTS.md with the five most-used jq
  recipes (vault_tag mint, note list ids, search results, escalation depth,
  run status step).

### R2. `hyperresearch note read` — the agent-first body reader (kills the staging dance)
Purpose-built for how transcripts show agents actually read:

```
hyperresearch note read ID [ID...] [options]
  --chars START:END      character window into the body (open-ended ok: 5000:)
  --lines N:M            line window
  --plain                strip <untrusted-source> fence + OA banner
  --meta-line            one header line: id | tier | words | tags
  --max-chars N          default 8000, hard cap per note; prints
                         "…[body continues: use --chars 8000:16000]"
```

Plain text out, no JSON. Batch-safe (per-note cap, so 10 notes never trip
the 51,200-byte tool limit). This replaces 818 slice reads + 1,827 /tmp
staging calls, and gives truncation a *resumable* protocol instead of a
parse failure.

### R3. `--fields` + `--format tsv` on the list-like commands
`note list --fields id,word_count,tier --format tsv`, same for `search`,
`claims list`, `escalation list`, `sources`. Field-extraction python (667
note-show + ~450 list/search calls) collapses to grep/cut pipelines the
agents already know how to drive.

### R4. Ship the two tiny verbs agents keep re-implementing
- `hyperresearch run artefact <name> --summary` — schema-stable pretty-print
  for loci.json / contradiction-graph.json / cite-check-pairs.json /
  polish-log.json (name → path resolution via the run manifest). Kills the
  schema-probe pattern and documents the schemas by construction.
- `hyperresearch escalation count [--status queued]` — integer on stdout;
  the single most-parsed number in orchestrator loops.

### R5. Make `fetch` duplicate a success
`ok: true, data: {duplicate: true, note_id, url}` with `--force` to refetch.
64 error-shaped round-trips disappear and fetchers stop second-guessing.

### R6. Skill/doc patches (no code)
- Every "parse the X field" sentence in the 16 step skills gets its jq
  recipe; teach `--raw`/`--meta` in the entry skill's conventions block.
- Steps 15/16 (and light-tier polish): replace hand-rolled metric checks
  with a mandated `run verify <tag> -j` + `--jq '.data.checks[] |
  select(.ok==false)'` line. `run verify` already checks length, headings,
  citation density, scaffold leak, quote integrity, artefacts — the agents
  just don't know.
- Fetcher agent doc: duplicate-fetch is a hit (contingent on R5).

### R7. PATH shim
`hyperresearch install` (global mode) should symlink the venv binary into
`~/.local/bin` (or print the exact command). Saves the 23 bare-invocation
failures and makes `$HPR` unnecessary in fresh sessions.

### R8. Manifest visibility for dead subagents
When a spawned step produces no parts, `run resume` should say so under
`blocked_on` (it currently reports the step as merely unfinished), so
orchestrators escalate model-routing issues instead of respawning blind.

## Suggested acceptance check
After R1–R3 land, re-run this audit's extractor over a week of fresh
sessions. Targets: inline-python share of bash calls 43% → <10%;
`KeyError: 'notes'` ≈ 0; `/tmp/opencode` staging calls ≈ 0; jq usage > 50%
of JSON-flagged calls.
