# PORTING NOTES — hyperresearch (Claude Code) → hyperresearch-opencode

Running log of deliberate deltas from upstream
[jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch)
v0.10.0. Later pieces append here. Upstream attribution: Jordan Gibbs, MIT —
this port adapts that code under the same license.

## P0-2 — Scaffold

### requires-python: `">=3.11,<3.14"` → `">=3.11"`

Upstream capped below 3.14 because core dependency Crawl4AI pins
`lxml~=5.3`, which does not build on 3.14 (see upstream
`src/hyperresearch/cli/__init__.py`'s version-guard comment). With Crawl4AI
demoted to an optional extra (below), the blocker is gone and the harness
must run on the host's Python 3.14, so the cap is dropped entirely.
Classifiers gain `Programming Language :: Python :: 3.14`.

### Crawl4AI demoted from core dep to optional extra

Upstream ships Crawl4AI as a hard core dependency AND a `crawl4ai` extra;
here it is extra-only (`pip install hyperresearch[crawl4ai]`). opencode
replaces the browser-fetcher lane Crawl4AI served. Consequence documented on
the `all` extra:

- Upstream: `all = ["hyperresearch[crawl4ai,mcp,exa,tavily,watch]"]`
- Ours: `all = ["hyperresearch[mcp,exa,tavily,watch]"]` — crawl4ai excluded so
  `[all]` stays installable on Python 3.14; the browser lane is opt-in via the
  explicit `crawl4ai` extra.

All other floors are verbatim from upstream: typer>=0.9.0, rich>=13.0,
pyyaml>=6.0, pydantic>=2.0, jinja2>=3.1, platformdirs>=4.0, pymupdf>=1.24,
httpx>=0.27; extras mcp=["mcp>=1.6,<2"], exa=["exa-py>=2.0.0"],
tavily=["tavily-python>=0.3"], watch=["watchdog>=4.0"]; dev list unchanged
(already crawl4ai-free).

### Version: `0.10.0` → `0.10.0.post1`

PEP 440 post-release marking "port of 0.10.0 with deliberate deltas", so port
artifacts are distinguishable from upstream's while sorting after it.
`hyperresearch.__version__` mirrors this (enforced by `tests/test_scaffold.py`).

### mypy `python_version`: `"3.11"` → `"3.14"`

Installed mypy 2.3.1 accepts 3.14 as a check target, so strict mode checks
against the version we actually run. No fallback needed; no per-module
overrides were required for the skeleton (typer ships types). Later pieces add
overrides with comments only where third-party libs lack stubs.

### CLI scaffold deltas (upstream `cli/__init__.py`)

- Dropped the Python-version stderr warning guard: obsolete now that 3.14 is
  supported by design.
- Dropped the Windows cp1252 UTF-8 reconfigure shim: its stated reason was
  crash-safety for Crawl4AI's rich logger, which no longer exists in core.
- Entry-point contract preserved exactly: `hyperresearch` and `hpr` console
  scripts both point at `hyperresearch.cli:app`; `python -m hyperresearch`
  delegates through `__main__.py` like upstream. Scaffold app lives in
  `cli/main.py` (placeholder `--version/-V` eager callback mirroring
  upstream's), re-exported by `cli/__init__.py`; later pieces replace the
  assembly, not the contract.

### Ruff / pytest config

Mirrored verbatim: same select/ignore rule sets, same per-file-ignores entries
(including files not yet ported — globs simply don't match until later pieces
create them, and the policy travels with the config), line-length 100,
`src = ["src"]`. Kept `target-version = "py311"` to mirror upstream; ruff
0.16.4 accepts it. pytest ini_options identical: `testpaths = ["tests"]`,
`addopts = "-ra -q --strict-markers"`.

### Environment evidence (P0-2 install)

Host: Linux, Python 3.14.5 (only interpreter). Venv `.venv/` created with
`python3 -m venv`; `pip install -e ".[dev]"` succeeded first try, all wheels,
no source builds. Recorded versions:

| Tool      | Version |
|-----------|---------|
| python    | 3.14.5  |
| pip       | 26.1.1  |
| ruff      | 0.16.4  |
| mypy      | 2.3.1 (compiled) |
| pytest    | 9.1.1   |
| typer     | 0.27.1  |
| pymupdf   | 1.28.2  |

Spike S0-6 input: **pymupdf 1.28.2 installed as a prebuilt cp314 wheel and
imports cleanly on Python 3.14** (`import pymupdf` OK) — no build toolchain
needed. Also note mypy resolved to 2.x despite our floor of `mypy>=1.8`
(upstream floor kept verbatim); if later pieces hit mypy 2.x breaking changes,
tighten to an upper bound then.

## P0-3 — Spikes (S0-1, S0-2, S0-3, S0-4, S0-6) + toolchain policy alignment

Full method/transcripts/verdicts under `docs/spikes/`; raw command output
under `evidence/spikes/`. Summary of deliberate deltas each spike forces:

### S0-1 nested subagents: REFUTED → flat orchestration design

An opencode subagent has NO task tool (child session export shows zero tool
calls; it answers `NO_TASK_TOOL_AVAILABLE`). Level-1 delegation
(primary → subagent) works and returns child results faithfully
(`NESTED_OK` round-tripped through the `general` agent). Two consequences:

- Port orchestration depth is capped at primary → subagent; "researcher
  spawns fetcher" chains are flattened into sequential task calls from the
  primary session.
- Investigators call `hpr fetch-batch` directly; roster prompts carry a
  "## Degraded mode" clause describing direct calls.

Method correction recorded (F-METHOD): `opencode run --agent <subagent>` is
not drivable from the CLI — opencode falls back to the default build agent
with a warning. Subagents can only be exercised via a primary driver.

### S0-2 agents dir naming: CONFIRMED (both dirs load)

`.opencode/agent/<name>.md` AND `.opencode/agents/<name>.md` both appear in
one `opencode agent list`, merged with built-ins and global user agents.
Default mode renders `(all)` unless frontmatter restricts it, so port roster
agents set `mode: subagent` explicitly. A cold-init discovery miss was seen
once by the coordinator across ~5 fresh trees but not reproduced this
session — installers must re-run discovery after writing agent files and
treat first-run absence as retryable, never fatal.

### S0-3 tool-lock: CONFIRMED — belt-and-braces adopted

All three mechanisms produced REAL denials on live transcripts (not config
inspection): frontmatter `tools.write:false`, frontmatter `tools.edit:false`
(tool removed from toolset entirely), and a project plugin
`.opencode/plugins/denywrite.js` hooking `tool.execute.before` to throw on
`tool === "write"` (hard error in transcript even for UNLOCKED agents; hook
API taken from host-installed `@opencode-ai/plugin@1.17.13` types since no
working examples existed on this host). Patcher/polish-auditor ship BOTH
layers: frontmatter locks as layer 1, the deny plugin as backstop. Known
accepted gap: bash remains available under both mechanisms.

### S0-4 skill-load: CONFIRMED(static)-DYNAMIC-DEFERRED

Skills load from `<project>/.opencode/skills/<name>/SKILL.md` (probe found at
its exact scratch path via `opencode debug skill`) and
`~/.config/opencode/skills/<name>/SKILL.md` (7/7 global skills resolve
there). Dynamic freshness across steps is explicitly deferred to P3 E2E;
until then installed skills are write-once artifacts.

### S0-6 packaging: CONFIRMED (tiered), with metadata-trap finding

pymupdf 1.28.2 works end-to-end on 3.14 (render→extract round trip).
`.[all]` resolves without crawl4ai. Crawl4AI 0.7.3's dry run RESOLVES
(metadata-only false pass: lxml 5.4.0 sdist satisfies `~=5.3`), but a real
install FAILS building lxml on cpython-3.14 — upstream's blocker holds in
practice, so crawl4ai stays an opt-in ≤3.13 extra and opencode carries the
browser lane on the supported host. Rule recorded for later pieces: a pip
dry-run may only ever support a "metadata resolves" claim; installability
claims need a real install.

### mypy `python_version`: `"3.14"` → `"3.11"` (reverted)

P0-2 critic finding F3: single language-level policy — lint (ruff
`target-version = "py311"`) and type-check calibrate to the declared floor
3.11, while runtime correctness is proven by pytest on the host interpreter
3.14. Evidence: `evidence/gauntlet/P0-2-verdict-r1.md`. Post-fix gate green
in one pass: `.venv/bin/mypy src` → "Success: no issues found in 4 source
files"; `.venv/bin/ruff check .` → "All checks passed!"; `.venv/bin/pytest
-q` → exit 0 (1 passed). Raw outputs: `evidence/spikes/postfix-{mypy,ruff,
pytest}.txt`. This supersedes the P0-2 entry above that moved it to 3.14.

## P1-1 — Foundation layer: models + core (frontmatter/note/vault/db/migrations/sync/patterns)

Ported near-verbatim from upstream v0.10.0. Sources (14 files, 13 listed in the
piece brief + `core/config.py`): `models/{__init__,note,graph,output,search}.py`
and `core/{__init__,frontmatter,note,patterns,config,vault,db,migrations,sync}.py`.

### Transitive scope addition: `core/config.py`

`core/vault.py` (in-brief) imports `VaultConfig` from `core/config.py` at module
level — a hard dependency, not a lazy one. Rather than stub it (forbidden), the
whole file was ported verbatim. It is stdlib-only (tomllib/dataclasses/pathlib)
so it drags nothing else in. Its dedicated test `test_core/test_config_sections.py`
came along for the parts whose imports resolve within P1-1 (see skipped list).
Note: upstream has NO `tests/test_core/test_db*.py` or
`tests/test_core/test_migrations*.py` — db/migrations behavior is covered
indirectly by `test_vault.py` (init → init_schema → migrate) and `test_sync.py`.

### Behavioral adaptation (the only one): `Vault.init` no longer injects agent docs

Upstream ended `Vault.init()` with a lazy
`from hyperresearch.core.agent_docs import inject_agent_docs; inject_agent_docs(root)`
— Claude-Code-specific CLAUDE.md injection, and `core/agent_docs.py` is outside
P1-1 scope. The call was removed and replaced with a comment pointing at the
future agent-docs piece; `Vault.init` now writes no agent docs at all. Two
upstream tests that assert CLAUDE.md creation are kept in place but marked
`pytest.mark.skip` with reasons (`test_agent_docs_created`,
`test_init_only_creates_claude_md`) so the future piece can restore them adapted
to AGENTS.md.

Kept verbatim despite mentioning Claude (documentation-only, no code path):
- `config.py` `ChromeSettings` docstring ("Claude-in-Chrome" lane) — describes
  the `[chrome]` section semantics that later pieces (escalation) will re-home;
  rewriting it here would desync config docs from the escalation design.
- `config.py` `exclude_patterns` entry `"CLAUDE.md"` — harmless sync exclusion,
  already alongside `"AGENTS.md"` upstream.

### mypy --strict annotation deltas (zero logic changes)

Upstream targets non-strict mypy; our gate is strict. Every delta below is an
added type annotation or type-parameter, each marked with a "Delta vs upstream"
comment in-source:

| File | Delta |
|------|-------|
| models/search.py | `SearchResponse.filters: dict` → `dict[str, Any]` |
| core/note.py | `write_note.extra_frontmatter: dict \| None` → `dict[str, Any] \| None`; local `kwargs: dict` → `dict[str, Any]` |
| core/sync.py | `SyncResult.errors: list[dict]` → `list[dict[str, Any]]`; added parameter annotations `vault: Vault`, `note: Note`, `conn: sqlite3.Connection` on `compute_sync_plan`, `execute_sync`, `_upsert_note_to_db`, `_delete_note_from_db`, `_resolve_links_incremental`, `_resolve_null_links` (adds module-level `from hyperresearch.core.vault import Vault` — safe, vault imports sync only lazily inside `auto_sync`) |
| core/vault.py | `__exit__(self, *args)` → `*args: object` |
| core/config.py | `_build_section` given a TypeVar signature `(type[_SettingsT], dict[str, Any]) -> _SettingsT`; `_toml_array(items: Iterable[str])`, `_toml_value(value: Any)`, `_section_lines(section: Any)`; `profile_overlays: dict` → `dict[str, Any]`. One narrow `# type: ignore[arg-type]` on the `fields(section_cls)` line: stdlib stub requires `DataclassInstance`, which a TypeVar'd `type[T]` does not satisfy (mypy limitation, not a lib-without-types case) |

No third-party per-module mypy overrides were needed (pydantic ships types).

### Python 3.14 drift

None encountered. Upstream already uses `datetime.now(UTC)`, stdlib `tomllib`,
and `StrEnum`; all 90 tests passed unmodified on 3.14.5 on first run.

### Test fixtures / tests delta summary

- `tests/conftest.py`: autouse `_reset_render_state` fixture guarded with
  try/except ImportError around `from hyperresearch.core import hooks`
  (core/hooks is a later piece). Fixture docstring kept verbatim; once hooks
  lands the guard resumes resetting automatically. All other fixtures
  (`tmp_vault`, `seeded_vault`) byte-identical.
- `tests/test_core/test_config_sections.py`: trimmed of out-of-scope pieces —
  removed `TestGateThreading` entirely (every test builds
  `hyperresearch.web.base.WebResult`); removed
  `TestProfileOverlayRoundtrip.test_builtin_override_survives_save` and the
  `resolve_profile` tail of `test_overlays_survive_save` (both need
  `core.profiles`). Config-level round-trip assertions of the latter retained.
- Everything else byte-identical to upstream: test_core/{__init__,test_note,
  test_frontmatter,test_vault,test_sync,test_patterns}.py,
  test_graph/{__init__,test_links}.py.

Result: 90 passed, 2 skipped (both skips = agent-docs-dependent vault tests);
ruff clean; `mypy src` strict clean (18 source files).

### Out-of-scope imports discovered (feed later builders)

- `core/db.py` ↔ `search/fts.py`: schema defines FTS5 tables `notes_fts` /
  `claims_fts`; sync writes into `notes_fts` directly. The search package
  (`search/filters.py`, `search/fts.py`) plus its test `test_search/test_fts.py`
  must land before any CLI search command.
- `core/vault.py` → `core/agent_docs.py` (`inject_agent_docs`): must return as
  the AGENTS.md-installing piece; restore the two skipped vault tests then.
- `core/config.py` → nothing beyond stdlib, BUT `profile_overlays` exists to be
  consumed by `core/profiles.py` (`resolve_profile`); profiles piece should take
  `test_config_sections.py`'s removed profile assertions back.
- `models/graph.py` consumers live in `cli/graph.py` / graph package (later);
  `models/output.py` Envelope is the CLI-wide JSON output contract for P1-9/10;
  `models/search.py` SearchResult/SearchResponse pair with search/filters+fts.

### Gauntlet r2 remediation: latent upstream defects fixed as deltas

Round 2 of the blind gauntlet (ours won) empirically reproduced five latent
defects inherited verbatim from upstream. Disposition per
`evidence/gauntlet/P1-1-verdict-r2.md`: findings 1-4 fixed in our port (data
loss/corruption trumps verbatim), finding 5 filed below. Every fix carries a
regression test that fails against the pre-fix code (verified by re-running
the new tests against HEAD sources).

1. **CRITICAL — migration rebuild dropped `notes` with foreign keys ON**
   (`core/migrations.py`). `db.get_connection` sets `PRAGMA foreign_keys=ON`
   on every vault open, and under enforcement a `DROP TABLE notes` performs
   an implicit DELETE that fires ON DELETE CASCADE against tags /
   note_content / embeddings / claims / assets and ON DELETE SET NULL against
   sources.note_id — so auto-migrating a legacy vault silently destroyed all
   child data. Fixed with the standard SQLite table-rebuild procedure:
   `migrate()` now disables foreign-key enforcement around the whole run
   (committing first — the pragma is a no-op inside a transaction), gates the
   result on `PRAGMA foreign_key_check`, and always re-enables enforcement in
   a finally block. Regression tests:
   `TestMigrationPreservesChildData::test_legacy_vault_migration_preserves_child_rows`,
   `test_sources_note_id_not_nulled_by_rebuild`,
   `test_foreign_keys_re_enabled_after_migration`
   (tests/test_core/test_migrations.py, new file).

2. **HIGH fragility hardening, same file.** New `_clear_rebuild_leftovers()`
   runs at `migrate()` start: a crash mid-rebuild previously left a committed
   notes_v7/notes_v8 scratch table and bricked the vault forever on "table
   already exists" (executescript's implicit pre-commit had already persisted
   the DDL); leftovers are now removed — or promoted back to `notes` when a
   crash landed between DROP TABLE and the RENAME, where the scratch is the
   only copy of the data. Version stamping moved to AFTER each version's
   migration ran AND committed (a stamped version can no longer precede its
   schema change), and dict-gap versions are skipped rather than stamped.
   Tests: `TestInterruptedRebuildRecovery::*`.

3. **MEDIUM — TOML string escaping** (`core/config.py`). `_toml_value` and
   the inline f-strings in `save()` spliced strings raw between quotes, so a
   value containing `"`, `\`, or a newline/control char produced INVALID TOML
   — saving a config corrupted it against `load()`. Strings are now emitted
   via `json.dumps` (its output is a valid TOML basic string: escapes exactly
   the set TOML requires), applied also to `_toml_array` items and the
   `[vault]`/`[web]`/`[pipeline]` inline interpolations. Tests:
   `TestTomlStringEscaping::*` (tests/test_core/test_config_sections.py).

4. **LOW-MED — scalar tag coercion** (`models/note.py`). The `tags` validator
   iterated any input, so YAML frontmatter `tags: research` (a plain str)
   became ['r','e','s','e','a','r','c','h']. Upstream intent checked at the
   reference tree (same file): identical code, nothing consumes the
   char-splitting deliberately — it is an unguarded iteration bug, fixed here
   by coercing str → [value] (lowercased/stripped like list items). Tests:
   `test_scalar_tag_string_becomes_single_tag`,
   `test_scalar_tag_string_is_lowercased_and_stripped`
   (tests/test_core/test_note.py).

5. **Coverage gap closed** (round-1 residual): context-manager tests for
   `with Vault(...) as v:` proving the sqlite connection is closed (and not
   leaked on exception) after exit — `test_context_manager_opens_and_closes_connection`,
   `test_context_manager_closes_on_exception` (tests/test_core/test_vault.py).

### Known inherited issues (filed, NOT fixed — upstream-faithful by design)

Filed from the same verdict; fix opportunistically if a later piece touches
these files:

- `write_note` collision loop TOCTOU (`core/note.py:125-131`): checks
  `file_path.exists()` then writes; concurrent writers can still collide.
- slugify symbol-title fallback seed collision (`models/note.py:70-74`):
  distinct symbol-only titles hash the *stripped* text, which is empty for
  all of them, so `!!` and `??` both seed `note-<same-hash>`.
- `exclude_patterns` knob consumed nowhere (`core/config.py:222-227` defines;
  `core/sync.py:97` walks `rglob("*.md")` without consulting it).

## P1-3 — Graph layer: linker/graphrank/quality/independence (+ similarity)

Ported near-verbatim from upstream v0.10.0. Sources (6 files, 5 listed in the
piece brief + one transitive): `graph/__init__.py` (byte-identical docstring
module) and `core/{linker,graphrank,quality,independence,similarity}.py`.
Linker test coverage (`tests/test_graph/test_links.py`) had already landed
byte-identical in P1-1; untouched here.

### Transitive scope addition: `core/similarity.py`

`core/independence.py` (in-brief) imports `jaccard`/`shingle` from
`core/similarity.py` at module level — a hard dependency. Same disposition as
P1-1's `core/config.py`: ported verbatim rather than stubbed. It is stdlib-only
(hashlib/struct/collections). Its MinHash/LSH half has no upstream test file of
its own; it becomes exercisable when the dedup CLI piece lands.

### mypy --strict annotation deltas (zero logic changes)

Every delta below is an added type annotation/import, each marked with a
"Delta vs upstream" comment in-source:

| File | Delta |
|------|-------|
| core/similarity.py | `jaccard(a: set, b: set)` → `a: set[str], b: set[str]` |
| core/linker.py | `auto_link(vault, ...) -> dict` → `vault: Vault`, `-> dict[str, list[str]]`; module-level `from hyperresearch.core.vault import Vault` added (no cycle: vault imports neither linker nor independence) |
| core/graphrank.py | `compute_centrality(conn)` → `conn: sqlite3.Connection`; local `new_rank = {}` → `dict[str, float]` |
| core/quality.py | `compute_quality_scores(conn, ...)` → `conn: sqlite3.Connection` |
| core/independence.py | `compute_independence(vault, ...) -> dict` → `vault: Vault`, `-> dict[str, Any]`; `params: tuple` → `tuple[str, ...]`; `rows` given `list[dict[str, Any]]`; bare generics parameterized on `cluster_kind`/`by_url`/`by_wire`/`groups`/`clusters` (`dict`→`dict[str, Any]`, `frozenset`→`frozenset[str]`, `clusters = []` annotated) |

No third-party overrides needed; all four modules were already strict-clean
modulo these annotations.

### Test porting decisions (surveyed all of upstream tests/)

Upstream has NO dedicated `test_linker*`/`test_graphrank*`/`test_quality*`
files; coverage of this piece's modules lives inside two multi-domain files.
Per "take what resolves in-scope", each was split at class boundaries into new
files; every ported class is byte-identical to upstream (verified by diff):

- `tests/test_core/test_source_ranking.py` (NEW): TestSchemaV9 + TestPageRank +
  TestQualityComposite verbatim. The brief conditioned on the file "not
  importing core.scholar/web.base": the module-level scholar import blocks
  taking the file whole, but the graphrank/quality portions themselves only
  need config/graphrank/quality/migrations/note/sync — all present since P1-1 —
  so they are taken into a fresh file with the scholar/search/cli imports left
  behind. Deferred classes (land them with their owners):
  - TestDoiExtraction → needs `hyperresearch.core.scholar.extract_doi` (P1-5)
  - TestRankedSearch → needs `hyperresearch.search.fts.search_fts` + cli app
    (search package / CLI pieces); asserts quality-ranked FTS ordering, i.e.
    the consumer side of compute_quality_scores
- `tests/test_core/test_independence.py` (NEW): TestIndependence verbatim,
  extracted from upstream `tests/test_core/test_verification.py`. Rest of that
  file deferred: TestCiteCheckExtraction/TestVerificationLints/
  TestCJKLengthCheck/TestTelemetryAndVerify/TestFinishGate/
  TestCiteCheckerAgentInstall → core/citecheck.py, core/runs.py, core/hooks.py,
  CLI (later pieces).

Not taken (incidental term matches only): `test_dissertation_profile.py` and
`test_scholar_enrichment.py` mention `quality_score` as a DB column inside
tests owned by profiles/scholar pieces.

Result: 127 passed, 2 skipped (the two pre-existing agent-docs skips), ruff
clean, `mypy src` strict clean (24 source files).

### Out-of-scope imports discovered (feed later builders)

- `core/scholar.py` consumes `core.quality.compute_quality_scores`
  (enrichment tail) — P1-5 must also backfill TestDoiExtraction +
  TestRankedSearch into `tests/test_core/test_source_ranking.py`.
- `cli/dedup.py` imports `minhash_signature`/`lsh_candidates` from
  `core/similarity.py` at module level — the dedup CLI piece gets similarity's
  untested half for free.
- `cli/link.py`, `cli/research.py`, `cli/fetch_batch.py` call
  `auto_link`; `cli/sources.py` calls `compute_independence`;
  `cli/repair.py` + `cli/graph.py` call `compute_centrality` +
  `compute_quality_scores` — all lazy imports, no wiring done in P1-3.

## P1-2 — Search layer (fts/filters) + embeddings (+ P1-3 side-fixes)

Ported near-verbatim from upstream v0.10.0. Sources (4 files):
`search/{__init__,fts,filters}.py` and `core/embed.py`.
`tests/test_search/test_fts.py` (deferred by P1-1 until the search package
existed) taken whole.

### Drift verdict on P1-3's `core/similarity.py`

Re-diffed against upstream as required: byte-faithful modulo exactly the two
strict-mypy annotation deltas already declared in §P1-3 (`jaccard` params
`set[str]`, plus its "Delta vs upstream" comment). No other drift found; not
re-ported. The G13-LSH-BANDING guard below is the only functional change,
applied on top.

### mypy --strict annotation deltas (zero logic changes)

Every delta below is an added type annotation/import, each marked with a
"Delta vs upstream" comment in-source:

| File | Delta |
|------|-------|
| search/filters.py | `to_sql -> tuple[str, list]` → `tuple[str, list[Any]]`; local `params: list` → `list[Any]`; module-level `from typing import Any` |
| search/fts.py | `ranking: dict \| None` → `dict[str, Any] \| None`; return `list[dict]` → `list[dict[str, Any]]`; `filter_params: list` → `list[Any]`; `results = []` annotated `list[dict[str, Any]]` |
| core/embed.py | `_note_text(row)` → `row: sqlite3.Row`; `embed_sync(vault, ...) -> dict` / `semantic_search(vault, ...) -> list[dict]` → `vault: Vault`, `dict[str, Any]` / `list[dict[str, Any]]`; local `todo = []` annotated `list[tuple[sqlite3.Row, str]]`, `results = []` annotated; `cosine` locals `dot`/`norm_a`/`norm_b` annotated `float` (mypy 2.3.1 infers `sum(...)` as `float \| Literal[0]`, making the final division Any); module-level `from hyperresearch.core.vault import Vault` + stdlib `sqlite3`/`typing.Any` imports (no cycle: vault imports neither embed nor search) |

### Gauntlet r1 side-fixes landed here (from evidence/gauntlet/P1-3-verdict-r1.md)

1. **MEDIUM G13-LSH-BANDING** — `core/similarity.py` `lsh_candidates`:
   upstream computed `rows_per_band = num_perm // bands` unguarded;
   `bands > num_perm` gave 0-row bands whose empty-slice hash puts every doc
   in one bucket per band, so ALL pairs became candidates (reproduced against
   upstream reference: bands=200/num_perm=128 returned the unrelated pair).
   Fixed with an explicit domain guard `not 0 < bands <= num_perm` raising
   `ValueError`. Chose raising over clamping: clamping would silently change
   LSH banding recall semantics instead of surfacing misuse, and the future
   dedup consumer must never silently degrade into O(n²) all-pairs or silent
   misses. Regression tests: `TestLshBandingGuard::*`
   (tests/test_core/test_similarity.py — new file; upstream ships no test for
   this module).

2. **LOW G13-REFVOCAB-ORDER** — `core/linker.py` ref_vocab population: both
   population queries now ORDER BY stable unique keys
   (`notes ... ORDER BY id`; `aliases ORDER BY alias, note_id`), keeping the
   existing last-wins assignment — the winner is deterministic: highest note
   id wins duplicate titles/aliases. Honesty note recorded: on a stock vault
   SQLite happens to insert/scan rows id-ascending, so pre-fix behavior
   coincided with the rule on this platform; the nondeterminism is
   plan/storage-order dependent (any reorder flips the link target).
   tests/test_core/test_linker_determinism.py covers it with duplicate-title
   fixtures locking the contract, plus one forced physical-reorder case
   (alias row delete+reinsert) that demonstrably fails against pre-fix code
   (verified against the upstream module directly).

### Test porting decisions

- `tests/test_search/{__init__,test_fts}.py`: byte-identical to upstream
  (diff-verified), incl. the degenerate-query/broken-index error-contract
  tests.
- Upstream `tests/test_core/test_claims_and_embed.py` split at the class
  boundary like P1-3 did for its multi-domain files: `TestEmbeddings` moved
  byte-identical (diff-verified) into NEW tests/test_core/test_embed.py with
  claims imports trimmed; `TestClaimsIngest` stays deferred with its owner
  (`core/claims.py` + CLI app, later pieces).

Result: 166 passed, 2 skipped (the two pre-existing agent-docs skips), ruff
clean, `mypy src` strict clean (28 source files).

### Out-of-scope imports discovered (feed later builders)

- `cli/dedup.py` imports `minhash_signature`/`lsh_candidates` from
  `core/similarity.py` at MODULE level — dedup CLI piece gets the now-tested
  LSH half wired for free (and inherits the bands≤num_perm contract).
- `cli/search.py` + `mcp/server.py` + `serve/server.py` consume
  `search_fts`/`SearchFilters` (lazy); `cli/embed_cmd.py` consumes
  `embed_sync`/`semantic_search` (lazy) — none wired in P1-2.
- `TestRankedSearch.test_quality_reorders_equal_relevance`
  (upstream tests/test_core/test_source_ranking.py:173) needs ONLY
  `hyperresearch.search.fts.search_fts` via an in-method import — it is NOW
  fully resolvable and awaits the P1-5 backfill into
  tests/test_core/test_source_ranking.py alongside TestDoiExtraction (its
  sibling `test_search_cli_ranked_flag` still needs the CLI app).


## P1-2 hardening — verdict-r1 findings F1/F2/F4 fixed

From `evidence/gauntlet/P1-2-verdict-r1.md`. Each fix carries a regression
test proven to FAIL against the pre-fix code (git-stash round, like P1-1).
Upstream inherits all four findings; data-correctness/injection trumps
verbatim here, same rule as the P1-1 remediation wave.

1. **F1 (MEDIUM) — bm25 weights interpolated raw into SQL** (`search/fts.py`
   bm25() f-string). A string ranking weight reached the SQL text verbatim:
   non-numbers surfaced as raw `sqlite3.OperationalError` ("no such column")
   or a generic syntax-error SearchQueryError, and crafted values like
   `'0.0, 999'` silently RESTRUCTURED the statement (shifting weight onto
   other columns — live-proven in the verdict). `search_fts` now coerces
   each weight with `float()` at function entry via `_coerce_weight()`;
   non-numeric OR non-finite values raise `SearchQueryError` naming the
   offending key, so only provably numeric literals are interpolated.
   Numeric strings (config plumbing) coerce cleanly instead of reaching SQL.
   Tests: `test_numeric_string_weights_are_coerced`,
   `test_non_numeric_weight_raises_search_query_error_naming_weight`,
   `test_weight_string_cannot_restructure_bm25_statement`
   (tests/test_search/test_fts.py).

2. **F2 (MEDIUM) — bare-date `before` excluded the entire final day**
   (`search/filters.py`). `created` stores full ISO timestamps, which sort
   lexicographically AFTER their own date prefix, so
   `created <= '2024-01-15'` dropped every note created ON that day
   (end-to-end reproduced). Semantics now defined explicitly: a bare
   YYYY-MM-DD `before` compiles to an EXCLUSIVE bound at midnight next day
   (`created < '2024-01-16'`) — includes 2024-01-15T23:59:59.999, excludes
   next-day 00:00:00. Full datetime inputs keep the exact inclusive `<=`
   bound; `after` semantics untouched (`>=`, already covers the day from
   its first instant — mirror-checked). Date-shaped-but-invalid input
   (`2024-13-45`) raises ValueError with a clear message instead of a
   confusing SQLite type error downstream.
   Tests: `TestBeforeDateBoundary::*`
   (tests/test_search/test_filters.py, NEW file),
   `test_before_bare_date_boundary_end_to_end`.

3. **F4 (LOW) — `has_backlinks=False` silently ignored ('1=1').** Upstream
   intent checked first, as required: reference `cli/search.py` normalizes
   with `has_backlinks or None` — upstream NEVER implements a negative
   query; False is purely a CLI default sentinel meaning "no constraint".
   Since our CLI piece is not ported yet, we chose the loud-failure branch:
   `has_backlinks=False` now raises `NotImplementedError` explaining the
   truthy-only design, so a future consumer that forgets the `or None`
   mapping gets an immediate error instead of silently wrong results. True
   (positive subquery) and None (unconstrained) unchanged.
   Tests: `TestHasBacklinks::test_false_raises_not_implemented_rather_than_silent_ignore`,
   `test_true_keeps_positive_subquery`, `test_none_stays_unconstrained`.

4. **F3 (LOW-MED) operator-sniffing passthrough** stays FILED per the
   verdict's own disposition — not touched in this wave.

Result after hardening (combined with §P1-6 below): 257 passed, 6 skipped
(unchanged skips), ruff clean, `mypy src` strict clean (36 source files).


## P1-4 — Web layer: providers/base + fetcher (+PDF text extraction, junk gates)

Ported near-verbatim from upstream v0.10.0. Sources (7 files):
`web/{__init__,base,builtin,tavily_provider,exa_provider,crawl4ai_provider}.py`
and `core/fetcher.py`. Tests: all 7 upstream `tests/test_web/` files taken
(6 test modules + empty `__init__.py`; 7 of those byte-identical, one adapted
— below). Source-side, `web/__init__.py`, `exa_provider.py` are byte-identical;
the rest carry only the marked deltas.

### Junk detection: real locations (brief asked to verify by reading)

- **`web/base.py`** — the gates themselves:
  `is_binary_garbage_char` / `binary_garbage_ratio` / `is_binary_garbage`,
  `WebResult.looks_like_junk()` (empty content, bot-detection, error pages,
  search-index pages, raw-PDF-internal markers, binary-garbage ratio,
  cookie/boilerplate walls) and `WebResult.looks_like_login_wall()`.
- **Thresholds live in `core/config.py::JunkGates`** (`min_content_chars`,
  `sample_window`, `binary_garbage_ratio`, cookie/login-wall sizes,
  `extra_*_signals`) — already in-tree since P1-1's verbatim config port;
  nothing added here.
- **`core/patterns.py` contains NO junk patterns** — verified by reading; the
  survey's guess was wrong. Fetcher merely *consumes* the base.py gates via
  `vault.config.junk`.

### THE delta: crawl4ai imports made lazy (module importable without the extra)

Upstream `crawl4ai_provider.py` opens with four module-level
`from crawl4ai import ...` lines. That was safe upstream because crawl4ai was
a hard core dependency; here it is an opt-in extra that cannot install on
Python 3.14, so a top-level import would make the whole module — including
the offline PDF/smart-wait helpers and every test touching them —
unimportable. The four imports moved into the only two methods that use them
(`Crawl4AIProvider.__init__`: BrowserConfig/CrawlerRunConfig/
DefaultMarkdownGenerator + PruningContentFilter; `_make_crawler`:
AsyncWebCrawler/AsyncPlaywrightCrawlerStrategy/UndetectedAdapter), with a
TYPE_CHECKING-only binding preserving the `-> AsyncWebCrawler` annotation.

Honesty note on the brief: "upstream already guards imports" is only PARTLY
true. Verified guards upstream: (a) factory-level — `get_provider` wraps both
import AND construction of crawl4ai/tavily providers in try/except ImportError
(preserved byte-identical); (b) two of seven test files use
`pytest.importorskip` (stealth: on `crawl4ai.browser_adapter`;
fetch_many_fallback: on the provider module). NOT guarded upstream, because
absence was impossible there: `test_pdf_diagnostics.py` imports the provider
module bare at module level, and `test_junk_detection.py::
test_single_shared_implementation` imports `_looks_like_binary` from it.
With lazy imports these run unmodified in our tree.

User-facing contract verified unchanged:
`get_provider("crawl4ai")` still raises
`ImportError("crawl4ai provider requires: pip install hyperresearch[crawl4ai]")`
(construction-time instead of import-time; same except-block catches both).

Consequence wins: `test_pdf_diagnostics` (7 tests) and the shared-junk-
implementation regression now RUN without the extra, and
`test_fetch_many_fallback`'s importorskip passes so its 2 fake-crawler tests
run offline instead of skipping (guard kept verbatim; it still skips in an
environment where even the lazy module fails).

### Test porting decisions

- 7 files byte-identical to upstream (diff-verified): `__init__.py`,
  `test_junk_detection.py`, `test_pdf_diagnostics.py`,
  `test_crawl4ai_stealth.py`, `test_fetch_many_fallback.py`,
  `test_tavily_provider.py`, `test_exa_provider.py`.
- `test_fetch_settings.py` adapted minimally: module-level importorskip on
  the provider module kept verbatim (now passes thanks to lazy imports, so
  TestSmartWaitJs + TestLooksLikeBinary run); the three tests that CONSTRUCT
  a real Crawl4AIProvider (TestProviderConstruction ×2,
  TestGetProviderThreading ×1) gained an inline
  `pytest.importorskip("crawl4ai", ...)` helper — constructing the provider
  genuinely needs the package, which is not installable here. Skips cleanly.

### No-network audit

Every new test is offline: tavily tests inject a fake SDK module into
sys.modules; exa tests patch MagicMock clients onto the installed exa_py
(no HTTP issued); PDF tests stub `httpx.get` with canned responses;
junk/fetch-settings/smart-wait tests are pure functions; stealth +
construction tests skip without the package. No live network anywhere.

### PDF extraction path exercised (pymupdf wheel present)

pymupdf 1.28.2 cp314 wheel installed as a core dep, so
`pytest.importorskip("pymupdf")` passes and `test_pdf_diagnostics` exercises
REAL extraction offline: builds in-memory PDFs (`pymupdf.open()` →
`new_page()` → `insert_text()` → `tobytes()`), feeds them through
`_fetch_pdf` with stubbed httpx, and asserts extracted text plus
`looks_like_junk() is None` (magic-bytes-beat-content-type round trip);
the scanned-PDF/no-text-layer OCR diagnostic likewise. The missing-pymupdf
diagnostics (one-shot warning latch) are exercised by faking ImportError
via `builtins.__import__` monkeypatching.

### mypy --strict annotation deltas (zero logic changes)

| File | Delta |
|------|-------|
| web/base.py | `WebResult.metadata/media/links` bare `dict`/`list[dict]` → `dict[str, Any]`/`list[dict[str, Any]]`; adds `Any` import |
| web/builtin.py | HTMLParser overrides annotated per typeshed (`tag: str`, `attrs: list[tuple[str, str \| None]]`) + `__init__ -> None`; urllib branch binds `resp: Any` with one `# type: ignore[no-redef]` (same function also binds `resp` from httpx above; typeshed's `IO[Any]` has no `.url`) |
| web/crawl4ai_provider.py | `cookies: list[dict]` → `list[dict[str, Any]]`; `browser_kwargs: dict[str, Any]`; `links`/`web_results`/`failed_pdf_urls` given explicit annotations; `_import_pymupdf() -> Any` (callers use the returned module directly) |
| web/tavily_provider.py | one ignore comment on the lazy `from tavily import TavilyClient` (see next section); zero logic/annotation changes |
| core/fetcher.py | `vault` param → `vault: Vault` (module-level Vault import, no cycle); return `dict` → `dict[str, Any]`; `extra_meta`/`saved_assets` parameterized; `.get(result.raw_content_type or "", "")` (`or ""` for the str key — None maps to "" exactly as upstream's default did) |

### mypy strict vs stub-less optional SDKs: per-line ignores, no config change

The lazy third-party imports (`bs4`, `crawl4ai` + two submodules,
`crawl4ai.async_crawler_strategy`, `crawl4ai.browser_adapter`,
`playwright.async_api`, `tavily`) are unresolvable under strict mypy on this
host (none ship stubs; most aren't installable). A central
`[[tool.mypy.overrides]] ignore_missing_imports` block would fix it, but this
piece's file ownership excludes `pyproject.toml`, so each site instead carries
a `# type: ignore[import-not-found]` with a Delta comment — inside owned files,
self-cleaning (the ignore reads as unused and FAILS the gate if the module
ever becomes resolvable, forcing removal). Two mypy behaviors worth recording:
only the FIRST import of a given missing module errors (later imports of the
same module are cached and must NOT carry ignores), and exa_py needed nothing
(it ships py.typed). A later piece that owns pyproject may consolidate these
into one override block if it prefers.

### Forward references to later pieces (kept verbatim, self-cleaning ignores)

`fetch_and_save` lazily imports three not-yet-ported modules on paths that
cannot execute until they land: `core.scholar.extract_doi` (**main path** —
every successful fetch calls it), `core.escalation.maybe_enqueue_blocked_fetch`
(login-wall / bot-detection branches), `cli.fetch._save_assets` (save_assets
branch). Each carries `# type: ignore[import-untyped]` marked for removal
with its piece — strict mode's warn_unused_ignores will FAIL the gate once
the real module exists, forcing cleanup. Consequence: `fetch_and_save` cannot
run end-to-end until P1-5 (scholar). Upstream ships NO direct tests for
fetcher (verified by grep over upstream tests/) so there is nothing to skip
or defer here; its test window opens when scholar lands (P1-5 backfill).

Result: 211 passed, 6 skipped (2 pre-existing agent-docs skips + 1 module
skip = stealth file ×3 tests + 3 crawl4ai-construction skips), ruff clean,
`mypy src` strict clean (35 source files).

### Out-of-scope imports discovered (feed later builders)

- `cli/fetch.py` has its OWN inline fetch pipeline (not this fetcher) plus
  `_save_assets`, which `core/fetcher.py` imports lazily — the cli/fetch
  piece owns removing that ignore.
- `core/escalation.py::maybe_enqueue_blocked_fetch` consumed by fetcher's
  login-wall/bot branches — escalation piece must provide it (signature used
  here: `(vault, url, reason, *, vault_tag=None, detail=None) -> item_id`).
- `core/scholar.extract_doi(url, raw_html, content)` consumed on fetcher's
  main path — P1-5 backfill should also restore fetcher end-to-end tests.
- `mcp/server.py` + `serve/server.py` presumably consume `fetch_and_save`
  (MCP-side entry per brief) — later wiring, untouched here.
- `web.base.get_provider` future callers: `cli/research.py`,
  `cli/fetch_batch.py` (surveyed earlier pieces noted them as lazy).

## P1-6 — Untrusted-source fencing (core/untrusted)

Ported near-verbatim from upstream v0.10.0. Sources (2 files):
`core/untrusted.py` + `tests/test_core/test_untrusted.py`, BOTH byte-identical
to upstream (diff-verified against the pinned reference tree). This is the
first ported module that needed ZERO strict-mypy/ruff deltas — upstream had
already annotated every signature.

### Consumer trace (exhaustive; brief's guesses checked and refuted)

Grep over the whole upstream tree: the ONLY runtime consumers of
`is_untrusted`/`wrap_body` are two lazy-import call sites, both in
not-yet-ported CLI files. The survey's candidate hosts are NOT consumers —
verified: `core/vault.py`, `models/output.py`, and upstream `cli/_output.py`
contain zero untrusted references. Upstream deliberately fences at the
PRESENTATION layer only; vault/db store raw bodies, and the fence must wrap
what a subagent READS, not what is persisted.

1. `cli/note.py::show` — JSON-with-body branch (`if not meta:` block,
   upstream lines ~218–222): lazily imports both functions; when
   `is_untrusted(data.get("source"), data.get("type"))`, sets
   `data["body"] = wrap_body(body, data["source"])` and
   `data["untrusted"] = True`, else attaches the body bare. The `--raw`
   sibling path intentionally prints stored bytes unfenced (raw = file dump).
2. `cli/search.py::search` — body-bearing results (upstream lines ~189–198),
   same lazy import; per result with a body:
   `r["body"] = wrap_body(...)` + `r["untrusted"] = True`. HARD ORDERING
   CONSTRAINT recorded in upstream's own comment: this MUST run AFTER the
   token-budget truncation loop so the closing fence can never be severed
   by the cut. Any future port that reorders these loses the guarantee.

Non-code complements (prompt-side, no imports): `core/hooks.py` documents the
`<untrusted-source url="...">` contract to subagents at three sites;
`core/agent_docs.py` describes the fence in generated docs. Both land with
their own pieces and must keep that wording consistent with this module.

End-to-end fence assertions also live in CLI-owned upstream tests, deferred
with their owners: `tests/test_cli/test_commands.py::
test_search_json_wraps_fetched_bodies_as_untrusted`,
`test_note_show_json_wraps_fetched_body_as_untrusted` (+ the third variant at
line ~208), and `tests/test_cli/test_oa_fetch.py:156` (banner sits INSIDE the
fence). The owning pieces backfill these adapted to our fixtures.

### Integration glue disposition: none possible yet, engagement documented

Both runtime hooks belong to later pieces (the `note show` and `search` CLI
commands), so NOTHING engages at runtime in this commit — there is currently
no code path in-tree that emits a note body. Per the piece brief this is the
documented-deferral branch: zero already-ported files were touched, because
upstream itself touches none — wiring is exclusively the two lazy imports
inside `cli/note.py` / `cli/search.py`. When each lands it must reproduce
the call shape above (including `untrusted: true` markers and the
truncation-before-wrap order) or the fence is cosmetic.

### Upstream weak spots observed (FILED, NOT FIXED — verbatim mandate)

Adversarial read of the verbatim module; listed for the adversaries, not
patched:

- W1 URL sanitizer strips only C0 + DEL (`[\x00-\x1f\x7f]`); U+0085 /
  U+2028 / U+2029 survive, and `str.splitlines()` treats those as line
  breaks — a crafted URL can still start a visual new line inside the
  attribute region (quoting holds; line-spoofing does not).
- W2 BODY control characters are never sanitized (only the URL is): ANSI/CSI
  escapes from an attacker page flow through `wrap_body` verbatim into
  terminal output and prompts.
- W3 Fence neutralization is ASCII-literal: homoglyph/fullwidth tag
  lookalikes and split-forms like `</untrusted-\nsource>` survive verbatim;
  whether they defeat a reader depends entirely on its tokenizer.
- W4 `is_untrusted` fails OPEN on storage quirks: a source with leading
  whitespace (`" https://…"`) or any scheme-stripped/normalized form silently
  disables fencing.
- W5 Trusted types are wholesale-trusted: fetched URLs quoted INTO
  interim/source-analysis/moc/index bodies render unfenced (trust propagates
  via `note_type` alone).
- W6 The neutralized tag keeps the visible `untrusted-source-inner` substring
  (forensics by design); exact-string counters stay correct (tested: exactly
  one real close tag), but fuzzy matchers may miscount.

Result: 237 passed, 6 skipped (unchanged pre-existing skips), ruff clean,
`mypy src` strict clean (36 source files).

### Out-of-scope imports discovered (feed later builders)

None new: `core/untrusted.py` is stdlib-only (html/re) and imports nothing
from the project; nobody in-tree consumes it until the CLI pieces above.

## P1-6 hardening — fence-probe findings F-01/F-02 fixed (was W4/W2)

The adversarial probe suite at `/tmp/opencode/fence-probes/`
(`run_probes.py`, with `audit_fixups.py` as the corrected P7/P12 record)
proved two of the filed weak spots exploitable; both are now fixed in-tree
with regression tests that FAIL against the pre-fix module (git-stash
round, like P1-1). Probe outcomes moved: P9 BROKE → NEUTRALIZED,
P10 BROKE → NEUTRALIZED; nothing else changed.

1. **F-01 / was W4 (MEDIUM) — `is_untrusted` failed OPEN on padded URLs.**
   The scheme check ran on the raw string, so storage whitespace defeated
   classification: `is_untrusted(' https://attacker.example/', 'note')` was
   False and the note rendered UNFENCED despite being web-fetched.
   `is_untrusted` now strips surrounding whitespace before scheme
   classification — fail CLOSED (padded http(s) still wraps). Trusted-type
   gating unchanged; whitespace-only and typo'd schemes stay unclassified
   (padding alone never CREATES an untrusted verdict).
   Tests: `test_whitespace_padded_http_source_still_untrusted[*]`,
   `test_padded_source_still_respects_trusted_types`,
   `test_whitespace_or_typo_stays_unclassified`.

2. **F-02 / was W2 (MEDIUM) — body control bytes passed through verbatim**
   (terminal boundary spoofing: `\x1b[2J` clear-screen + OSC title-retitle
   rendered outside-looking-in). `wrap_body` now sanitizes BODY text before
   fence neutralization while leaving the fence markers themselves intact
   (they are appended after): ESC-initiated sequences stripped (CSI,
   OSC incl. unterminated-to-BEL/ESC/end so no dangling ESC survives, and
   other two-byte forms), then remaining C0 controls except \n\t, plus DEL
   (mirroring the URL sanitizer). ORDER IS LOAD-BEARING and documented
   in-source: strip FIRST, neutralize SECOND — a control byte used to
   splice a forged tag (`</\x00untrusted-source>`) reassembles into text
   the fence neutralizer then sees and renames; neutralizing first would
   leave a live closer behind. Clean bodies stay BYTE-EXACT through
   wrap→unwrap (audit_fixups P12 redo: all four benign cases lossless;
   run_probes P12's residual BROKE is its known rstrip-all-newlines false
   positive).
   Tests: `test_wrap_body_neutralizes_ansi_and_osc_in_body`,
   `test_wrap_body_strips_unterminated_osc_sequence`,
   `test_wrap_body_benign_multiline_body_round_trips_byte_exact`.

Probe-suite honesty note: run_probes/audit_fixups P7 flags `compile` via
naive AST call-name collection (it sees the two `re.compile()` calls);
identical on HEAD BEFORE these changes, and its substantive assertion
(`payload_inside_fence=True`) passes pre and post. Filed weak spots W1/W3/
W5/W6 remain FILED, NOT fixed.
