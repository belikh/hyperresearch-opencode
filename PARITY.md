# PARITY.md — hyperresearch → opencode port inventory

## Method

Every row below was surveyed directly against the upstream reference clone at
`/tmp/opencode/hyperresearch-reference`, pinned at commit
`15010c5142244b88265f7abadf7b7aa1a8237fde` (output of
`git -C /tmp/opencode/hyperresearch-reference rev-parse HEAD`; HEAD is
v0.10.0 `8619d6e` plus one post-release fix, `Fix length-in-range verify
check for CJK reports (#64)`). Survey date: 2026-08-22. Upstream tree:
94 Python files under `src/hyperresearch/` (38 in `cli/`, 30 in `core/`),
plus 19 skill markdowns under `src/hyperresearch/skills/`, tests under
`tests/` (incl. `tests/fixtures/golden_prompts/`), and `assets/`.
Citations use paths relative to the clone root. Every cited file:line was
opened and read during this survey.

## Legend

| Decision | Meaning |
|---|---|
| PORT-VERBATIM | Logic ports as-is (Python module mirrored into the port repo's `src/hyperresearch/**`). |
| PORT-ADAPT | Content/logic preserved, integration surface changes: Claude Code specifics (`.claude/skills/**`, `.claude/agents/*.md`, `CLAUDE.md`, PreToolUse hook, Task-tool spawn contract) become opencode equivalents (`.opencode/skill/*/SKILL.md`, `.opencode/agent/*.md`, `AGENTS.md` marker injection, opencode plugin, opencode subagent spawn contract). |
| DEFER | Non-goal for this port. Justification required per row. |

Proposed opencode-port target roots (final names owned by scaffolding):
`src/hyperresearch/**` (engine), `.opencode/skill/**` (skills),
`.opencode/agent/**` (subagents), `AGENTS.md` (ops doc injection),
opencode config `mcp` (stdio MCP registration), opencode plugin
(replaces the Claude Code PreToolUse hook).

---

## 1. Data models

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Note enums + metadata model | `src/hyperresearch/models/note.py:13-150` | NoteStatus/NoteType/Tier/ContentType StrEnums (:13,:22,:31,:40), slugify (:56), NoteMeta (:84), Note (:142). | PORT-VERBATIM | `src/hyperresearch/models/note.py` |
| Graph entries | `src/hyperresearch/models/graph.py:8-21` | LinkEntry + BacklinkEntry pydantic models for backlink/outlink reports. | PORT-VERBATIM | `src/hyperresearch/models/graph.py` |
| JSON envelope | `src/hyperresearch/models/output.py:11-28` | Envelope + success()/error() wrappers behind every `--json` flag. | PORT-VERBATIM | `src/hyperresearch/models/output.py` |
| Search result models | `src/hyperresearch/models/search.py:8-24` | SearchResult/SearchResponse shapes for FTS responses. | PORT-VERBATIM | `src/hyperresearch/models/search.py` |

## 2. Core store, sync, configuration

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Frontmatter codec | `src/hyperresearch/core/frontmatter.py:11-55` | Regex-delimited YAML frontmatter parse/serialize/render_note. | PORT-VERBATIM | `src/hyperresearch/core/frontmatter.py` |
| Note IO | `src/hyperresearch/core/note.py:20-148` | read_note (:20), write_note with collision-safe IDs (:72), strip_markdown (:135). | PORT-VERBATIM | `src/hyperresearch/core/note.py` |
| Vault root | `src/hyperresearch/core/vault.py:11-182` | `.hyperresearch/` layout consts (:11-13), Vault class (:20), init (:112), discover (:160), auto_sync (:174). | PORT-VERBATIM | `src/hyperresearch/core/vault.py` |
| SQLite schema | `src/hyperresearch/core/db.py:8-256` | SCHEMA_VERSION=12 (:8), SCHEMA_SQL (:10-201), FTS5 virtual table (:202-221), conn factory + init_schema (:230-256). | PORT-VERBATIM | `src/hyperresearch/core/db.py` |
| Schema migrations | `src/hyperresearch/core/migrations.py:14-353` | Versioned upgrades v6→v12 (tier/content-type, interim + source-analysis types, source ranking, oa recovery + kind), migrate() driver (:331). | PORT-VERBATIM | `src/hyperresearch/core/migrations.py` (these are DB-schema migrations, not the deferred pre-3.0 archive-migration non-goal) |
| Sync engine | `src/hyperresearch/core/sync.py:22-400` | mtime/hash SyncPlan/SyncResult (:22-39), compute_sync_plan (:71), execute_sync (:135), upsert/delete + incremental link resolution (:221-400). | PORT-VERBATIM | `src/hyperresearch/core/sync.py` |
| Config | `src/hyperresearch/core/config.py:10-408` | Frozen dataclass sections (FetchSettings :11, JunkGates :35, AssetSettings :50, DedupSettings :58, ChromeSettings :69, RankingSettings :89, EmbeddingSettings :123, LintSettings :138, ScholarSettings :147), VaultConfig TOML load/save (:194). | PORT-VERBATIM | `src/hyperresearch/core/config.py` |
| Profiles ("scale gears") | `src/hyperresearch/core/profiles.py:36-433` | ModelMap (:36), Profile with all pipeline scale numbers (:74), user `[profile.*]` overlays (:375), list/resolve_profile (:392,:399). Feeds render context. | PORT-VERBATIM | `src/hyperresearch/core/profiles.py` |
| Prompt renderer | `src/hyperresearch/core/render.py:47-104` | Strict Jinja env with `<< >>` / `<% %>` / `<# #>` delimiters (:47-61), dash/hyphen filters, profile render context (:64), provenance header (:81), insert-after-frontmatter (:93). Unknown var = hard fail. | PORT-VERBATIM | `src/hyperresearch/core/render.py` |
| Note templates | `src/hyperresearch/core/templates.py:7-209` | Six built-in note templates (note/concept/reference/guide/comparison/moc, :7-171), custom-dir override (:174), variable substitution (:197). | PORT-VERBATIM | `src/hyperresearch/core/templates.py` |

## 3. Pipeline parameterization + indexes + patterns

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Levers | `src/hyperresearch/core/levers.py:27-330` | Register/inference-depth/role lever vocab (:27-29), DEFAULT_LEVERS (:31), validation (:198), compose_shims → domain/register/inference shim texts (:235), persisted per run via decomposition.json (:265-330). | PORT-VERBATIM | `src/hyperresearch/core/levers.py` |
| Index generator | `src/hyperresearch/indexgen/generator.py:8-256` | IndexGenerator builds auto index/MOC pages grouped by tag/parent/type. | PORT-VERBATIM | `src/hyperresearch/indexgen/generator.py` |
| Markdown patterns | `src/hyperresearch/core/patterns.py:8-94` | Wiki-link/code-fence/citation-footnote regexes (:8-52), is_valid_wiki_link_target (:58). Shared parser vocabulary. | PORT-VERBATIM | `src/hyperresearch/core/patterns.py` |

## 4. Search

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| FTS search | `src/hyperresearch/search/fts.py:11-186` | Query preprocessing/splitting (:19-63), search_fts over FTS5 with weighted ranking + status/tag/parent filters (:66). | PORT-VERBATIM | `src/hyperresearch/search/fts.py` |
| Search filters | `src/hyperresearch/search/filters.py:8-105` | SearchFilters dataclass (tags/status/parent/date/type). | PORT-VERBATIM | `src/hyperresearch/search/filters.py` |
| Embeddings | `src/hyperresearch/core/embed.py:22-191` | Provider/model registry (:22), cosine (:41), HTTP embedding (:52), embed_sync bulk indexer (:105), semantic_search (:163), reciprocal-rank fusion (:182). | PORT-VERBATIM | `src/hyperresearch/core/embed.py` |
| Near-duplicate detection | `src/hyperresearch/core/similarity.py:9-81` | Shingling (:12), Jaccard (:20), MinHash signatures (:29), LSH banding candidates (:49). Powers dedup. | PORT-VERBATIM | `src/hyperresearch/core/similarity.py` |

## 5. Graph

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Graph package | `src/hyperresearch/graph/__init__.py:1` | Package marker/docstring only — real graph logic lives in the four core modules below; queries execute via SQL in CLI layer. | PORT-VERBATIM | `src/hyperresearch/graph/__init__.py` (trivial) |
| Auto-linker | `src/hyperresearch/core/linker.py:9-138` | Title-based wiki-link insertion across notes (MIN_TITLE_LEN :9, auto_link :12, per-note rewrite skipping code fences :66,:133). | PORT-VERBATIM | `src/hyperresearch/core/linker.py` |
| PageRank centrality | `src/hyperresearch/core/graphrank.py:16-82` | Damping/iteration consts (:16-18), pagerank (:21), compute_centrality writing scores back to notes table (:61). | PORT-VERBATIM | `src/hyperresearch/core/graphrank.py` |
| Source quality scoring | `src/hyperresearch/core/quality.py:22-75` | UTILITY_MAX cap (:22), per-row utility formula (:25), batch recompute (:56). | PORT-VERBATIM | `src/hyperresearch/core/quality.py` |
| Source independence | `src/hyperresearch/core/independence.py:26-151` | Wire-service markers (:26), tracking-param stripping canonical_url (:32,:36), wire signature near-dup detection (:47), compute_independence (:61). | PORT-VERBATIM | `src/hyperresearch/core/independence.py` |

## 6. Web fetching

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Provider contract | `src/hyperresearch/web/base.py:19-226` | Binary-garbage gates (:19-53), WebResult dataclass (:54), WebProvider Protocol (:167), get_provider registry/override resolution (:185). | PORT-VERBATIM | `src/hyperresearch/web/base.py` |
| Built-in provider | `src/hyperresearch/web/builtin.py:12-111` | Stdlib HTMLParser text extraction, zero deps. | PORT-VERBATIM | `src/hyperresearch/web/builtin.py` |
| Tavily provider | `src/hyperresearch/web/tavily_provider.py:26-104` | Tavily extract API client → WebResult mapping. | PORT-VERBATIM | `src/hyperresearch/web/tavily_provider.py` |
| Exa provider | `src/hyperresearch/web/exa_provider.py:27-135` | Exa contents API client → WebResult mapping. | PORT-VERBATIM | `src/hyperresearch/web/exa_provider.py` |
| Crawl4AI provider | `src/hyperresearch/web/crawl4ai_provider.py:38-491` | PDF URL detection (:38) + pymupdf extraction lane (:101-219), smart-wait JS (:70), Crawl4AI async crawler incl. profiles/magic config (:220-491). Headless lane ports; headful login-profile lane is a documented non-goal (see §17 DEFER rows). | PORT-VERBATIM (headless lane) | `src/hyperresearch/web/crawl4ai_provider.py` |
| Fetch-and-save pipeline | `src/hyperresearch/core/fetcher.py:9-190` | Provider call → junk gates → dedup → untrusted wrap → note write → sources row. Sole production caller is MCP `fetch_url` (`mcp/server.py:291`). `cli/fetch.py` does NOT import it — the `fetch` command runs its own inline pipeline in the command body (`cli/fetch.py:303-394`: gates :305, OA rescue via `core/oa` + nested `_rescue` :315-342, login-wall → escalation enqueue :357, junk/bot-wall → escalation :377-394). **Port BOTH paths — they drift independently upstream.** | PORT-VERBATIM | `src/hyperresearch/core/fetcher.py` |

## 7. Open-access recovery + enrichment + scholarly metadata

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| OA recovery | `src/hyperresearch/core/oa.py:55-690` | Unpaywall/Europe PMC clients (:55-56), OALocation (:82), paywall sniffing needs_oa_recovery (:168), candidate iteration (:196), resolve_oa (:227), JATS→markdown (:380), recovery_notice banner prose (:474), oa_frontmatter block (:524). Version/kind semantics documented in the blurb (see §13). | PORT-VERBATIM | `src/hyperresearch/core/oa.py` |
| Enrichment | `src/hyperresearch/core/enrich.py:10-110` | auto_tag from existing vocab (:10), auto_summary first-paragraph extraction (:44), enrich_note_file on write (:75). | PORT-VERBATIM | `src/hyperresearch/core/enrich.py` |
| Scholar metadata | `src/hyperresearch/core/scholar.py:30-344` | DOI/arXiv regexes (:30-37), per-host politeness delays (:40), extract_doi (:55), cached lookup_metadata (Crossref/SS/S2) (:151), backfill_dois (:214), authority scores (:250), score_sources incl. retractions (:272). | PORT-VERBATIM | `src/hyperresearch/core/scholar.py` |

## 8. Security

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Untrusted-source fencing | `src/hyperresearch/core/untrusted.py:21-62` | Trusted-type allowlist (:21), case/whitespace-tolerant fence-forging neutralization `_FENCE_TAG_RE` (:26), is_untrusted policy (:29), wrap_body with hardened DATA-not-instructions preamble + HTML-escaped attacker-influenced url attr (:42-62). | PORT-VERBATIM | `src/hyperresearch/core/untrusted.py` — security-critical, byte-for-byte |

## 9. Runs / pipeline state

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Run manifests | `src/hyperresearch/core/runs.py:29-555` | run.json manifest v1 (:29-30), events.jsonl telemetry (:46,:136), step/chapter/spend mutation (:148,:174,:183), resume_position (:243), stall detection (:266,:53), report data (:300), verify_run ship gate (headings/length/citation density/cite-resolution) (:347-525), finish_run (:526). | PORT-VERBATIM | `src/hyperresearch/core/runs.py` |
| Escalation queue | `src/hyperresearch/core/escalation.py:22-179` | Blocked-fetch queue (login_wall/bot_block/captcha/fetch_failed/interactive_needed/scholar_search :22; statuses queued/in_progress/fetched/needs_human/abandoned :23), enqueue (:34), auto-enqueue from fetch failures (:60), claim_next (:93), resolve (:123), list_items (:147), stats (:168). **Queue IS ported**; only its browser-drain consumer is deferred (§17). | PORT-VERBATIM | `src/hyperresearch/core/escalation.py` |
| Cite-check binding | `src/hyperresearch/core/citecheck.py:30-214` | Sentence splitting incl. CJK ranges (:30), numbered-cite/source-list parsers (:31-32), extract_pairs (:78), mechanical numeric triage (:114), LLM sampling (:176), pairs-file writer (:196). | PORT-VERBATIM | `src/hyperresearch/core/citecheck.py` |
| Claims store | `src/hyperresearch/core/claims.py:21-263` | Dedup-hashed claim ingestion from fetcher extractions (:44,:102), search_claims (:119), literature matrix (:156,:196), multi-source target grouping (:214). | PORT-VERBATIM | `src/hyperresearch/core/claims.py` |

## 10. Serve UI

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Local web server | `src/hyperresearch/serve/server.py:13-603` | Stdlib http.server UI: CSS (:13), drag/graph JS (:145,:164), HyperresearchHandler routes (:341), run_server (:575). No framework deps. | PORT-VERBATIM | `src/hyperresearch/serve/server.py` |
| Markdown renderer | `src/hyperresearch/serve/renderer.py:12-161` | Scheme-allowlisted safe URLs (:12-17), regex markdown→HTML (:46-146), table rendering (:147). XSS-hardened for serving fetched content. | PORT-VERBATIM | `src/hyperresearch/serve/renderer.py` |

## 11. MCP server

Registered as `FastMCP("hyperresearch", instructions=…)`. The 13 tools,
exactly as registered (each `@server.tool()`):

| # | Tool | Registered at | Port decision |
|---|---|---|---|
| 1 | search_notes | `src/hyperresearch/mcp/server.py:32` | PORT-ADAPT |
| 2 | read_note | `src/hyperresearch/mcp/server.py:68` | PORT-ADAPT |
| 3 | read_many | `src/hyperresearch/mcp/server.py:94` | PORT-ADAPT |
| 4 | list_notes | `src/hyperresearch/mcp/server.py:119` | PORT-ADAPT |
| 5 | get_backlinks | `src/hyperresearch/mcp/server.py:157` | PORT-ADAPT |
| 6 | get_hubs | `src/hyperresearch/mcp/server.py:176` | PORT-ADAPT |
| 7 | vault_status | `src/hyperresearch/mcp/server.py:194` | PORT-ADAPT |
| 8 | lint_vault | `src/hyperresearch/mcp/server.py:214` | PORT-ADAPT |
| 9 | check_source | `src/hyperresearch/mcp/server.py:241` | PORT-ADAPT |
| 10 | list_sources | `src/hyperresearch/mcp/server.py:258` | PORT-ADAPT |
| 11 | fetch_url | `src/hyperresearch/mcp/server.py:282` | PORT-ADAPT |
| 12 | create_note | `src/hyperresearch/mcp/server.py:309` | PORT-ADAPT |
| 13 | update_note | `src/hyperresearch/mcp/server.py:357` | PORT-ADAPT |

Port decision rationale: tool bodies call the same verbatim core functions;
only the transport wiring changes (launch via `hpr mcp`,
`src/hyperresearch/cli/mcp_cmd.py:8-19`, and register the stdio server in
opencode config `mcp`). Read-only-by-design note in module docstring
(`server.py:1-5`) is stale — it says "8 tools" but 13 are registered.

## 12. Skills pipeline (the 16-step procedure chain)

Where the step procedures actually live in the reference source:
**`src/hyperresearch/skills/*.md`** — 19 markdowns shipped in the wheel
(entry router + 16 numbered steps + 2 half-steps). They are NOT in
`templates.py` (which holds only the six note templates,
`core/templates.py:7-171`) nor in `render.py` (which only renders them,
`core/render.py:47-104`). Installer: `_install_hyperresearch_step_skills`
renders each with the active profile and writes
`.claude/skills/hyperresearch-N-<name>/SKILL.md`
(`core/hooks.py:4119-4178`); the entry router installs at
`.claude/skills/hyperresearch/SKILL.md` (`core/hooks.py:4076-4116`).
Golden-prompt regression fixtures: `tests/fixtures/golden_prompts/skills/`
(8 representative files) asserted byte-for-byte-ish by
`tests/test_core/test_prompt_golden.py`.

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Entry router skill | `src/hyperresearch/skills/hyperresearch.md:1-287` | Thin ROUTER: bootstrap query/vault_tag/scaffold, tier classification (light/full/dissertation), then invoke each step skill via the Skill tool; never does step work itself. | PORT-ADAPT | `.opencode/skill/hyperresearch/SKILL.md`; Skill-tool invocations map to opencode skill invocation |
| 16 steps + 2 half-steps | `src/hyperresearch/skills/hyperresearch-1-decompose.md` … `hyperresearch-16-readability-audit.md`, plus half-steps `hyperresearch-1-5-chapter-partition.md` and `hyperresearch-14-5-cite-check.md` (18 files, 2,619 lines total; the 2,906 figure sometimes quoted for the directory includes the 287-line entry router) | Per-step procedures: decompose, width-sweep, contradiction-graph, loci-analysis, depth-investigation, cross-locus-reconcile, source-tensions, corpus-critic, evidence-digest, triple-draft, synthesize, critics, gap-fetch, patcher, cite-check (14.5), polish, readability-audit, chapter partition (1.5). Profile-rendered via `<< >>` placeholders. | PORT-ADAPT | `.opencode/skill/hyperresearch-N-*/SKILL.md` — bodies preserved verbatim modulo tool-name/spawn-contract substitutions rendered by the same strict renderer |
| Skill golden fixtures | `tests/fixtures/golden_prompts/skills/` (8 files) + `tests/test_core/test_prompt_golden.py` | Regression pins for rendered skill output (subset: entry, 2, 4, 5, 9, 10, 13, 16). | PORT-VERBATIM | Same fixtures, retargeted expectations |

## 13. Agents (subagents spawned by the pipeline)

Where agent definitions live: **prompt-body string constants inside
`src/hyperresearch/core/hooks.py:90-3504`**, installed as
`.claude/agents/hyperresearch-*.md` by the `_install_*_agent` helpers
(`core/hooks.py:3760-3944`) driven by `install_hooks`
(`core/hooks.py:3548-3595`) and `install_global_hooks`
(`core/hooks.py:3598-3657`). Roster also summarized at
`core/hooks.py:3558-3563` and `core/agent_docs.py:53`. Golden fixtures:
`tests/fixtures/golden_prompts/agents/` (10 files, incl. the deferred
browser-fetcher). Upstream carries 16 agent prompt constants — 15 port +
browser-fetcher deferred.

| Agent | Reference citation (constant) | Role (1 line) | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| researcher | `src/hyperresearch/core/hooks.py:2908-3172` | Legacy/general research worker retained in roster. | PORT-ADAPT | `.opencode/agent/hyperresearch-researcher.md` |
| loci-analyst | `src/hyperresearch/core/hooks.py:90-293` | Layer 2: reads width corpus, returns 1–8 depth loci (spawn ×2 parallel, dedupe, clamp 6). | PORT-ADAPT | `.opencode/agent/hyperresearch-loci-analyst.md` |
| depth-investigator | `src/hyperresearch/core/hooks.py:294-584` | Layer 3: per-locus deep investigation with budgeted fetches. | PORT-ADAPT | `.opencode/agent/hyperresearch-depth-investigator.md` |
| source-analyst | `src/hyperresearch/core/hooks.py:2709-2907` | On-demand deep-read of a single high-value source (long-context lane). | PORT-ADAPT | `.opencode/agent/hyperresearch-source-analyst.md` |
| dialectic-critic | `src/hyperresearch/core/hooks.py:585-718` | Layer 5 critic: thesis/antithesis tension audit of drafts. | PORT-ADAPT | `.opencode/agent/hyperresearch-dialectic-critic.md` |
| instruction-critic | `src/hyperresearch/core/hooks.py:994-1319` | Layer 5 critic: compliance vs. scaffold/user requirements. | PORT-ADAPT | `.opencode/agent/hyperresearch-instruction-critic.md` |
| depth-critic | `src/hyperresearch/core/hooks.py:719-837` | Layer 5 critic: evidential depth vs. claim weight. | PORT-ADAPT | `.opencode/agent/hyperresearch-depth-critic.md` |
| width-critic | `src/hyperresearch/core/hooks.py:838-993` | Layer 5 critic: corpus breadth/source diversity. | PORT-ADAPT | `.opencode/agent/hyperresearch-width-critic.md` |
| patcher | `src/hyperresearch/core/hooks.py:1320-1495` | Layer 6: applies critic findings; TOOL-LOCKED to Read+Edit (no Write). | PORT-ADAPT | `.opencode/agent/hyperresearch-patcher.md`; preserve tool-lock invariant via opencode agent permissions |
| polish-auditor | `src/hyperresearch/core/hooks.py:1496-1857` | Layer 7: prose/consistency pass; also Read+Edit tool-locked. | PORT-ADAPT | `.opencode/agent/hyperresearch-polish-auditor.md` |
| readability-reformatter | `src/hyperresearch/core/hooks.py:2494-2708` | Post-audit readability restructuring recommendations/applier. | PORT-ADAPT | `.opencode/agent/hyperresearch-readability-reformatter.md` |
| corpus-critic | `src/hyperresearch/core/hooks.py:3173-3292` | Layer 3.7: corpus-level gap analysis feeding step 13 gap-fetch. | PORT-ADAPT | `.opencode/agent/hyperresearch-corpus-critic.md` |
| draft-orchestrator | `src/hyperresearch/core/hooks.py:1858-2058` | Layer 4: one of 3× parallel section drafters assembling triple-draft. | PORT-ADAPT | `.opencode/agent/hyperresearch-draft-orchestrator.md` |
| synthesizer | `src/hyperresearch/core/hooks.py:2059-2493` | Step 11: merges triple draft into single synthesized report. | PORT-ADAPT | `.opencode/agent/hyperresearch-synthesizer.md` |
| cite-checker | `src/hyperresearch/core/hooks.py:3419-3504` | Step 14.5: verifies sampled citation-sentence bindings against note claims; findings feed second patcher pass. | PORT-ADAPT | `.opencode/agent/hyperresearch-cite-checker.md` |
| browser-fetcher | `src/hyperresearch/core/hooks.py:3293-3418` + installer `core/hooks.py:3911-3921` | Drains escalation queue through the user's real Chrome (patchright); CAPTCHA/login/2FA always handed to human. | **DEFER** | Non-goal: depends on Claude-Code-side browser automation stack + local Chrome control; escalation queue itself IS ported (§9) and queues safely for a human or future lane. Fixture kept for reference at `tests/fixtures/golden_prompts/agents/browser_fetcher_agent.md`. |
| Agent golden fixtures | `tests/fixtures/golden_prompts/agents/` (10 files) | Rendered-output regression pins for agent prompts. | PORT-VERBATIM | Same fixtures, retargeted expectations |

## 14. Harness installer infrastructure (`core/hooks.py`, non-agent parts)

`core/hooks.py` is 4,178 lines: agent prompt constants (§13), plus the
Claude Code install machinery below.

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Render-state plumbing | `src/hyperresearch/core/hooks.py:22-50` | Process-global profile render context set before installers run; `_render_installed` stamps provenance header (:42). | PORT-VERBATIM | `src/hyperresearch/core/hooks.py` (mechanism unchanged; only install destinations differ) |
| Scaffold-only header canon | `src/hyperresearch/core/hooks.py:65-83` | `SCAFFOLD_ONLY_SECTION_HEADERS` — single source of truth shared by critics, polish-auditor, and lint wrapper-report rule; prefix-tolerant matching notes :52-64. | PORT-VERBATIM | same file |
| PreToolUse hook + hook.js | `src/hyperresearch/core/hooks.py:3505-3546` (template), `:3692-3745` (`_write_hook_script`, `_install_claude_hook`) | Writes `.hyperresearch/hook.js` and registers a Claude Code PreToolUse hook on Glob/Grep/WebSearch/WebFetch reminding the agent to check the research base first. | PORT-ADAPT | Re-express as an opencode plugin that nudges tool calls toward `hpr search/fetch`; hook JS body preserved where applicable |
| Per-agent/skill installers | `src/hyperresearch/core/hooks.py:3760-3944` (16 `_install_*_agent` helpers), `:4059-4075` (`_read_skill_source`), `:4076-4116` (entry skill), `:4119-4178` (step skills) | Render each prompt/skill with active profile, write under `.claude/agents/` + `.claude/skills/`, skip-if-unchanged. | PORT-ADAPT | Write `.opencode/agent/*.md` + `.opencode/skill/*/SKILL.md` instead |
| Retired-asset pruning | `src/hyperresearch/core/hooks.py:3946-4057` | `_RETIRED_AGENT_FILES`, `_RETIRED_SKILL_DIRS`, `_RETIRED_HYPERRESEARCH_FILES`; `_is_our_skill_dir` content-marker guard so user-owned dirs are never deleted (#73 regression); `_prune_retired_agents`, `_prune_global_step_skills`. | PORT-ADAPT | Same pruning logic retargeted at `.opencode/**`; keep the ownership-marker guard verbatim |

## 15. CLAUDE.md blurb injection → AGENTS.md

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Agent-docs injector | `src/hyperresearch/core/agent_docs.py:15-268` | Marker pair `<!-- hyperresearch:start -->`/`:end` (:15-16), full ops blurb (workflow, run mgmt, academic-APIs-first, PDF handling, OA semantics, untrusted-content policy, curation loop) (:18-184), executable-path resolution (:188-215), idempotent inject/replace (:218-268). Upstream writes CLAUDE.md only and deliberately leaves AGENTS.md/GEMINI.md alone (:1-8). | PORT-ADAPT | Inject the same blurb (reworded Claude-specific bits: `/hyperresearch` skill mechanics, `Skill` tool) into **AGENTS.md** between the same markers; `config agent-docs` verb (§16) regenerates it |

## 16. CLI — `src/hyperresearch/cli/` (38 files)

Registration surface: root commands bound at `cli/__init__.py:78-102`;
sub-apps added at `cli/__init__.py:104-150` (first block :117-127, second
block :140-150). Entry points `hyperresearch`/`hpr` →
`hyperresearch.cli:app` (`pyproject.toml:58-60`); Python guard
`>=3.11,<3.14` warning shim at `cli/__init__.py:6-31`.

Root-level commands:

| File | Command(s) (def site) | Purpose (1 line) | Port decision | Target |
|---|---|---|---|---|
| `cli/__init__.py` | app assembly (:44-150) | Typer app, version callback, all registrations. | PORT-VERBATIM | mirror |
| `cli/main.py` | init (:16), status (:41), sync (:112) | Vault init; health/stats; DB↔markdown sync. | PORT-VERBATIM | mirror |
| `cli/install.py` | install (:13; opts :13-45) | Init vault + inject agent docs + install skills/agents/hooks; `--global`, `--steps-only`, `--profile`. | PORT-ADAPT | Installs `.opencode/skill|agent` assets + AGENTS.md instead of `.claude/*` + CLAUDE.md |
| `cli/setup.py` | setup (:18; helpers :189-330) | Interactive crawl4ai/browser profile + dependency setup; `_ensure_browser` (:286). | PORT-VERBATIM | mirror; doubles as the documented path for headful login profiles (non-ported lane, §17) |
| `cli/search.py` | search (:11) | FTS with filters/body/ranking flags. | PORT-VERBATIM | mirror |
| `cli/fetch.py` | fetch (:201; helpers :82,:136,:641,:662,:726) | URL fetch→note; tier/content-type detect; asset saving; blocked-fetch escalation enqueue (:641). Runs its own inline pipeline (:303-394) — no `core/fetcher` import (§6). | PORT-VERBATIM | mirror (enqueue side of escalations stays; drain consumer deferred) |
| `cli/fetch_batch.py` | fetch-batch (:15) | Batch URL fetch from file/stdin with concurrency. | PORT-VERBATIM | mirror |
| `cli/research.py` | research (:16; helpers :231,:299) | One-shot non-agent research: search→fetch→linked notes→synthesis. | PORT-VERBATIM | mirror |
| `cli/note.py` | app + show (:159) | Hidden root `show` alias for note read. | PORT-VERBATIM | mirror |
| `cli/tag.py` | tags root (:16) | Root `tags` listing. | PORT-VERBATIM | mirror |
| `cli/vault_tag.py` | vault-tag (:81) | Derive/set per-run vault_tag namespace. | PORT-VERBATIM | mirror |
| `cli/dedup.py` | dedup (:17; brute/LSH :102,:114) | Near-dupe scan via MinHash/LSH. | PORT-VERBATIM | mirror |
| `cli/import_cmd.py` | import (:14) | Import external markdown folder into vault. | PORT-VERBATIM | mirror |
| `cli/repair.py` | repair (:13) | Auto-fix broken links; rebuild indexes. | PORT-VERBATIM | mirror |
| `cli/archive.py` | archive-run (:96; artifact lists :29-49) | Move prior run artifacts aside so next `/hyperresearch` run starts clean. Purely run-artifact archival — **contains no pre-3.0 legacy migration paths** (checked; see §17). | PORT-VERBATIM | mirror |
| `cli/watch.py` | watch (:12; quick lint :97) | watchdog Observer live-rebuild/lint on file change (:18-19,:83). | PORT-VERBATIM | mirror |
| `cli/serve.py` | serve (:10) | Launch serve UI (§10). | PORT-VERBATIM | mirror |
| `cli/mcp_cmd.py` | mcp (:8) | Run the MCP stdio server (§11). | PORT-ADAPT | Same binary; document registration in opencode config `mcp` |
| `cli/_output.py` | console/output/print_vault_status | Shared rich console + JSON envelope printing. | PORT-VERBATIM | mirror |

Sub-app groups (verbs enumerated from each file's typer decorators):

| File | Group: verbs (def sites) | Purpose | Port decision | Target |
|---|---|---|---|---|
| `cli/note.py` | note: new(:15), show(:159), list(:291), edit(:401), update(:424), mv(:535), rm(:572) | Note CRUD; show applies `<untrusted-source>` fencing per §8. | PORT-VERBATIM | mirror |
| `cli/graph.py` | graph: backlinks(:14), outlinks(:64), orphans(:114), broken(:146), stub(:188), hubs(:251), rank(:291) | Link analysis + centrality recompute. | PORT-VERBATIM | mirror |
| `cli/index.py` | index: build(:13), list(:35), show(:56) | Generated index pages. | PORT-VERBATIM | mirror |
| `cli/lint.py` | lint: single command via callback invoke_without_command (:235-236); checks quote-integrity(:110), numeric-consistency(:150), retracted-citations(:200), wrapper-report/prompt rules (:618,:1551) | Vault health + report integrity rules (1835 lines). | PORT-VERBATIM | mirror |
| `cli/export.py` | export: json(:16), vault(:60) | Export notes/vault archives. | PORT-VERBATIM | mirror |
| `cli/config_cmd.py` | config: show(:13), set(:44), get(:88), agent-docs(:124) | Config CRUD + regenerate injected ops doc. | PORT-ADAPT | `agent-docs` writes AGENTS.md (§15); rest verbatim |
| `cli/topic.py` | topic: tree(:13), list(:88), show(:119) | Topic hierarchy views. | PORT-VERBATIM | mirror |
| `cli/batch.py` | batch: tag-add(:100), tag-remove(:138), set-status(:178), deprecate(:226), set-parent(:266) | Bulk note operations. | PORT-VERBATIM | mirror |
| `cli/template.py` | template: list(:13), show(:40) | Show/list templates (§2 templates.py). | PORT-VERBATIM | mirror |
| `cli/git_cmd.py` | git: log(:27), blame(:89), changed(:124) | Git-history views over research dir. | PORT-VERBATIM | mirror |
| `cli/tag.py` (sub-app) | tag: list(:15), alias(:44), suggest(:67) | Tag management + aliases. | PORT-VERBATIM | mirror |
| `cli/profile_cmd.py` | profile: list(:46), use(:107), show(:180), validate(:208) | Switch/inspect scale gears; renders skills on switch. | PORT-VERBATIM | mirror |
| `cli/claims_cmd.py` | claims: ingest(:28), list(:62), search(:83), matrix(:107), targets(:135) | Claim store ingest/query/matrix (§9). | PORT-VERBATIM | mirror |
| `cli/embed_cmd.py` | embed: sync(:13), status(:54) | Embedding index maintenance. | PORT-VERBATIM | mirror |
| `cli/run_cmd.py` | run: init(:43), status(:77), list(:133), resume(:158), abort(:202), step(:225), spend(:251), event(:283), block(:318), report(:342), verify(:410), finish(:445) | Per-run workspace + manifest control (§9). | PORT-VERBATIM | mirror |
| `cli/escalation_cmd.py` | escalation: list(:38), add(:61), claim(:94), ingest(:115), human(:208), retry(:232), abandon(:255) | Browser-lane queue control (§9). | PORT-VERBATIM | mirror |
| `cli/escalation_cmd.py` — abandon verb | `escalation abandon` registered at `cli/escalation_cmd.py:255-256` (`@app.command("abandon")`, `def escalation_abandon`) | Mark a queued escalation dead (final lifecycle state `abandoned`, `core/escalation.py:23`). | PORT-VERBATIM | mirror — r1 gap-fix: verb was missing from this inventory's first pass |
| `cli/citecheck_cmd.py` | citecheck: extract(:15) | Build cite-check pairs file. | PORT-VERBATIM | mirror |
| `cli/levers_cmd.py` | levers: render(:34), set(:66) | Inspect/set run levers; emit shims (§3). | PORT-VERBATIM | mirror |
| `cli/sources.py` | sources: list(:13), check(:64), score(:100), backfill-doi(:139), retractions(:166), independence(:203) | Fetched-source management + scholarly enrichment (§7). | PORT-VERBATIM | mirror |
| `cli/assets.py` | assets: list(:13), path(:74) | Locate saved images/screenshots per note. | PORT-VERBATIM | mirror |
| `cli/link.py` | link: default command via callback invoke_without_command (:13) | Auto-discover + insert wiki-links (§5 linker). | PORT-VERBATIM | mirror |

## 17. Deferred (non-goals)

| Area | Reference citation | What it is | Decision | Justification |
|---|---|---|---|---|
| Browser-fetcher lane | `src/hyperresearch/core/hooks.py:3293-3418` (prompt), `core/hooks.py:3911-3921` (installer), escalation drain refs `core/hooks.py:3353` | Subagent that drains the escalation queue via the user's real Chrome (patchright), handing CAPTCHAs/logins/2FA to the human. | DEFER | Requires local-Chrome automation and Claude-Code-specific spawn plumbing; the escalation QUEUE and its CLI remain fully ported (§9, §16) so blocked fetches degrade gracefully (human drains via `escalation list/claim/ingest`). Revisit as an optional lane post-parity. |
| Banner/benchmark asset generators | `assets/_generate_banner.py`, `assets/_generate_benchmark.py` (plus generated PNGs `banner.png`, `banner_social.png`, `_banner_src.png`, `benchmark.png`) | README marketing banner + benchmark image generation scripts. | DEFER | Cosmetic/repo-marketing tooling with zero runtime or pipeline relevance. |
| Pre-3.0 archive migration internals | `src/hyperresearch/cli/archive.py:1-182` (surveyed in full, both halves) | Checklist hypothesized legacy pre-3.0 vault migration paths here. **None exist in v0.10.0**: the module only archives prior-run artifacts (`_ROOT_ARTIFACTS` :29-49, `_SUBDIRS` :51) into `research/runs/archive-<tag>-<ts>/` (:148-165), recreates empty `research/temp/` (:163-165); DB migrations live in `core/migrations.py` (v6-v12) and ARE ported (§2). | DEFER (vacuous) | Nothing to defer; recorded so the adversary sees the hypothesis was checked against the real file rather than assumed. `archive-run` itself ports verbatim (§16). |
| Crawl4AI headful login-profile lane | `src/hyperresearch/core/config.py:69-87` (ChromeSettings), `web/crawl4ai_provider.py:220-491` (profile/magic usage), `cli/setup.py:218-285` (interactive profile creation) | Visible-browser crawling of LinkedIn/Twitter/paywalled sites using saved login profiles. | DEFER (documented, not ported) | Fragile, machine-local session state. Instead, `hpr setup` (ported verbatim) remains the documented path to create login profiles, and the AGENTS.md blurb keeps the "tell the user to run setup" guidance (`core/agent_docs.py:152-156`). |
| PyPI publish | `pyproject.toml:1-70` (packaging metadata), release workflow implied by CHANGELOG tags | Publishing `hyperresearch` wheels to PyPI. | DEFER | Distribution channel is out of scope for the opencode port; consume from source/vendor per scaffolding decision. |

## 18. Packaging + entry

| Area | Reference citation | What it does | Port decision | opencode-port target / justification |
|---|---|---|---|---|
| Package entry | `src/hyperresearch/__init__.py:1-3`, `__main__.py:1-5`, `pyproject.toml:7,:11,:58-60` | `__version__`, `python -m hyperresearch`, console scripts `hyperresearch`/`hpr`, requires-python >=3.11,<3.14. | PORT-VERBATIM | mirror (name collision with PyPI package irrelevant while deferred) |

## Survey notes (deviations from the planning checklist)

1. `src/hyperresearch/cli/` holds **38** `.py` files, not 39.
2. `mcp/server.py` registers **13** tools but its docstring still says "8"
   (`server.py:3`).
3. Agent prompt constants number **16**, not 15 — counted by direct
   enumeration of the module-level `*_AGENT` prompt constants in
   `core/hooks.py` (16 declarations at lines :90 LOCI_ANALYST, :294
   DEPTH_INVESTIGATOR, :585 DIALECTIC_CRITIC, :719 DEPTH_CRITIC, :838
   WIDTH_CRITIC, :994 INSTRUCTION_CRITIC, :1320 PATCHER, :1496
   POLISH_AUDITOR, :1858 DRAFT_ORCHESTRATOR, :2059 SYNTHESIZER, :2494
   READABILITY_REFORMATTER, :2709 SOURCE_ANALYST, :2908 RESEARCHER,
   :3173 CORPUS_CRITIC, :3293 BROWSER_FETCHER, :3419 CITE_CHECKER):
   15 port + browser-fetcher deferred. The `install_hooks` roster summary at
   `hooks.py:3558-3563` is NOT the count source — it names only the 12
   pipeline agents (no `researcher`, `cite-checker`, or `browser-fetcher`).
4. The 16-step skill texts are NOT in `templates.py`/`render.py`; they are
   packaged markdowns under `src/hyperresearch/skills/` (§12).
5. `graph/__init__.py` and `export/__init__.py` are one-line package
   markers; all graph logic lives in the four `core/*` modules (§5).
