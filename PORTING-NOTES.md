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

### Known inherited issues (filed, NOT fixed — upstream-faithful by design)

Adversarial read of the verbatim module; listed for the adversaries and for a
future hardening wave, not patched in this piece:

- **Charset decode discards cp1252 pages as binary.** `builtin._download`
  decodes with `utf-8`/`errors="replace"`; Windows-1252 pages come through
  mojibake-heavy (or U+FFFD-dense) and can trip the binary-garbage gate.
  Proper fix needs a charset-detection dependency — deferred deliberately;
  no stdlib-only answer is reliable.
- **Login-wall / bot heuristics false-positive on prose.** `cf_signals` /
  `login_signals` substring-match page TEXT, so an article *mentioning*
  Cloudflare or "log in to see the dataset" can be fenced. Upstream design
  trade-off; kept verbatim.
- **`fetch_many` ordering + perf assumptions.** Results are zipped against
  inputs with `strict=False` (order assumption on crawl4ai's return), and
  PDF fetches run synchronously inside the async batch lane. Upstream
  design; revisit if batch throughput ever matters.
- **Fetcher's interim ModuleNotFoundError paths** (`core.escalation`,
  `cli.fetch._save_assets`) — sequenced intentionally with P1-8/P1-10; the
  self-cleaning ignores force their removal then.

## P1-4 hardening — gauntlet verdict-r1 findings fixed

From `evidence/gauntlet/P1-4-verdict-r1.md`. All four findings are defects
inherited verbatim from upstream v0.10.0 (diff-checked against the pinned
reference tree). Security/data-integrity trumps verbatim, same rule as the
P1-1/P1-2 waves. Every regression test was proven to FAIL against pre-fix
code via git-stash rounds (13 failed / 43 passed in the falsification window,
with the PoC log capturing pre-fix code issuing `follow_redirects=True`
straight into the attacker-controlled redirect).

1. **HIGH SSRF-FETCHLANES → new `web/_netguard.py`.**
   `validate_url_public(url)`: scheme ∈ {http, https}; hostname present, no
   embedded credentials; `socket.getaddrinfo` must resolve and EVERY address
   returned must be globally routable (`ip.is_global and not is_multicast`)
   — rejects loopback (127/8, ::1), RFC1918, fc00::/7 ULA, link-local
   (169.254/16 incl. the 169.254.169.254 metadata service, fe80::/10),
   unspecified (0.0.0.0/::), documentation/benchmarking/reserved ranges —
   with the address class named in the rejection message. Applied at
   `crawl4ai_provider._fetch_pdf` BEFORE the request AND on every redirect
   hop: `guarded_get()` replaces `httpx.get(follow_redirects=True)` with
   manual following (max 5 hops, each Location re-validated, relative
   Locations resolved per-hop); `builtin._download` httpx lane uses the same
   helper and its urllib fallback uses `guarded_urlopen` behind
   `GuardedRedirectHandler` (validates inside urllib's own redirect hook).
   No config toggle was added on purpose: agent-chosen URLs are
   attacker-influenceable, so a disable flag would re-open the hole.
   DNS rebinding (check-vs-connect TOCTOU) documented out of scope in the
   module docstring.
   Tests: tests/test_web/test_ssrf_guard.py —
   `TestValidateUrlPublic` (loopback literal/IPv6/DNS-resolved, metadata
   service, RFC1918/ULA/link-local/unspecified/documentation parametrized,
   mixed record sets, unresolvable hosts),
   `TestGuardedGet::test_redirect_into_loopback_never_requested`,
   `_test_redirect_to_new_host_is_revalidated`,
   `_test_non_http_location_scheme_rejected`, `_test_more_than_five_hops_raises`,
   `TestFetchPdfContainment::test_public_shaped_redirect_into_loopback_blocked`
   (the verdict PoC end-to-end: loopback hop dies at validation, never
   requested), `TestBuiltinLaneContainment::*`.

2. **MEDIUM JUNKGATE-INVISIBLE-PADDING.** `web/base.py::strip_invisible`
   removes ZWSP/ZWNJ/ZWJ/U+2060–2064/BOM/soft-hyphen/Mongolian-vowel-sep/
   Arabic-letter-mark before length accounting AND signal matching:
   `looks_like_junk` (near-empty gate, cf/error/search/pdf signal windows,
   cookie-wall length) and twin gate `looks_like_login_wall` (same defect
   class). Invisible padding can no longer fake substance, and signal phrases
   split by zero-width characters ("Just\u200b a\u200b moment") match again.
   Tests: tests/test_web/test_junk_detection.py `TestInvisiblePadding::*`
   (ZWSP-padded spam and soft-hyphen padding now junk; split bot-wall signal
   detected; padded login wall detected; legit CJK/accented text with stray
   invisibles unaffected; direct pin on the strip set).

3. **ENV-CONDITIONAL MYPY DIRT retired via config.** Inline
   `# type: ignore[import-not-found]` on tavily (wrong-code whenever
   tavily-python IS installed) and NO ignore on exa_py (hard error whenever
   exa-py is ABSENT) replaced by `[[tool.mypy.overrides]]
   module=["tavily.*","exa_py.*"] ignore_missing_imports=true` +
   comment pointing at it. Proven clean in THREE SDK-presence configurations
   without touching the project venv:
   - A — project venv as-is (exa-py present+typed, tavily absent): clean;
   - B — hard-link-free full clone of `.venv` with exa_py removed, both SDKs
     absent, first-party editable install intact: clean;
   - C — same clone with a stub-less fake `tavily` package (no py.typed)
     dropped into site-packages: clean;
   and DIRTY pre-fix in B/C (stash rounds): B showed exactly
   `exa_provider.py:47 [import-not-found]`; C showed exactly
   `tavily_provider.py:45 unused-ignore + wrong-code import-untyped vs
   import-not-found` plus the exa error — i.e. the two env-conditional
   failures CI never saw because dev extras always installed exa and nobody
   had installed tavily.

4. **LOW ARXIV-HOST-SPOOF.** `_is_pdf_url` and the abs→pdf rewrite now use
   exact-host/suffix matching (`_on_arxiv_host`: hostname == arxiv.org or
   endswith .arxiv.org) instead of substring/netloc containment, so
   `notarxiv.org.evil.com` neither lane-chooses as arXiv nor gets its path
   rewritten to a different target. Tests: `TestArxivExactHost::*`.

### Twin sweep (defect-class completeness, this wave)

Searched the whole tree for the three wrong constructs:

- Unvalidated direct-fetch sites (`httpx.get`/`urlopen` outside _netguard):
  found 2 — `core/scholar.py:105` and `core/oa.py:361`. Both are
  fixed-API-host lanes (Unpaywall/Europe PMC constants; oa.py additionally
  gates resolver URLs through `check_oa_url` first). Outside this wave's
  file ownership (web/** only) — FILED: when ownership allows, route both
  through `_netguard.guarded_get` to inherit per-hop revalidation
  (oa.py's own NOTE already anticipates collapsing into a web-level check).
- Substring host matching: found 1 more — `core/scholar.py:73`
  (`"doi.org" in netloc`) — classification-only lane (DOI extraction from
  links), not a security boundary; FILED with the same future wave.
- Raw-content length gates: all three in-scope sites (min_content_chars,
  cookie_wall_max_chars, login_wall_max_chars) now measure invisible-stripped
  text. Out-of-scope raw-length uses are heuristics/stats (`oa.py:197`
  paywall trigger — false-negative costs one cached API call; `fetcher.py`
  word_count stat) — noted, not gated.

Result after hardening: 449 passed, 96 skipped (skips unchanged),
ruff clean, `mypy src` strict clean (46 source files).

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

## P1-5 — Open-access recovery + scholar enrichment

Ported near-verbatim from upstream v0.10.0. Sources (3 files):
`core/{oa,enrich,scholar}.py`. Tests: two new files byte-identical to
upstream (`tests/test_core/test_oa_recovery.py` — 61 tests,
`tests/test_core/test_scholar_enrichment.py` — 10 tests) plus the scheduled
backfill into `tests/test_core/test_source_ranking.py` (below).

### Composition with web/base.py (P1-4): verified, zero web/* changes

Every touchpoint lines up with what P1-4 landed; nothing under `web/` was
modified:

- `oa._fetch_jats` constructs `WebResult(url=..., title=..., content=...)`
  lazily inside the function — matches our base.py signature.
- `needs_oa_recovery` reads `result.raw_content_type` / `result.content` —
  present on our WebResult.
- `_try_candidates` gates candidates with
  `recovered.looks_like_junk(vault.config.junk)` (`str | None` contract) and
  routes PDFs through `web.crawl4ai_provider._fetch_pdf(url,
  vault.config.fetch)` — exists since P1-4 with exactly that shape.
- No signature mismatch appeared; the "fix on our side if trivially
  mechanical" branch was never needed.

### The one cross-file delta: fetcher.py forward-reference retired

P1-4 left `from hyperresearch.core.scholar import extract_doi # type:
ignore[import-untyped]` on `fetch_and_save`'s MAIN path, explicitly "marked
for removal with its piece". With scholar.py real, strict mode's
warn_unused_ignores fails the mypy gate, so the ignore comment was dropped
(the import itself is unchanged). Honesty note: `core/fetcher.py` is outside
this piece's file ownership grant. This is recorded as the single deliberate
exception — it is precisely the cleanup P1-4's note scheduled for P1-5,
purely mechanical (comment removal, zero behavior change), and unavoidable
for a green mypy gate. The two remaining forward-references
(`core.escalation.maybe_enqueue_blocked_fetch`, `cli.fetch._save_assets`)
keep their ignores until their pieces land.

### mypy --strict annotation deltas (zero logic changes)

Diff-audited line-by-line against upstream; every delta below is an added
annotation/import or typed local, each marked "Delta vs upstream" in-source:

| File | Delta |
|------|-------|
| core/scholar.py | `_http_get_json`/`_fetch_json`/`lookup_metadata` return `dict \| None` → `dict[str, Any] \| None`; `conn` params → `sqlite3.Connection` (module-level sqlite3 import, annotation-only); `backfill_dois`/`score_sources` take `vault: Vault` (module-level Vault import — no cycle: vault imports neither); `params: tuple` → `tuple[str, ...]` ×2; `resp.json()` / `json.loads(...)` bound to typed locals before return (strict `no-any-return`); `score_sources -> dict` → `dict[str, Any]` |
| core/oa.py | TYPE_CHECKING block (Iterator/sqlite3/ET/ScholarSettings/Vault/WebResult — all annotation-only; runtime imports stay lazy exactly as upstream); `needs_oa_recovery(result, settings)` annotated `WebResult`/`ScholarSettings`; `conn` params typed throughout; generator returns → `Iterator[OALocation]`; bare `list[dict]`/`dict` parameterized ×4; inner `walk`s annotated; `oa_frontmatter -> dict[str, str]`; `_fetch_jats -> WebResult \| None`; `_try_candidates`/`recover_full_text`/`rescue_full_text` fully annotated with `prov: Any` (duck-typed `.fetch` provider; real provider typing arrives with the CLI piece); getaddrinfo address coerced `str(info[4][0])` (typeshed types it `str \| int`; runtime identical) |
| core/enrich.py | `existing_tags: list[dict]` → `list[dict[str, Any]]`; `scored = []` annotated `list[tuple[str, float]]`; adds `Any` import |

### No-network audit — every path offline by stubbing, then proven empirically

All HTTP/DNS in the new tests is stubbed at the seams upstream designed for
exactly this:

- **JSON APIs** (Unpaywall `/v2/{doi}?email=`, Europe PMC
  `/search?query=DOI:"..."`, OpenAlex, Semantic Scholar): tests monkeypatch
  `scholar._http_get_json` with per-URL-substring canned responses
  (`_stub_http` / `_stub_openalex` helpers record call URLs for assertions).
- **DNS**: the `public_dns` fixture monkeypatches `oa.socket.getaddrinfo` to
  hand back a public address; per-test variants return link-local
  169.254.169.254, loopback, or raise OSError. Non-HTTP-scheme /
  credential-embedded / bare-hostname cases reject BEFORE any resolution.
- **JATS full text**: `oa._http_get_text` monkeypatched (canned XML or None).
- **PDF lane**: `crawl4ai_provider._fetch_pdf` monkeypatched at module level —
  importable without the crawl4ai extra thanks to P1-4's lazy imports, so the
  PDF recovery paths RUN here rather than skip.
- **Landing-page lane**: a duck-typed `FakeProvider.fetch`.

Empirical proof: all 93 new/backfilled tests were run inside `unshare -rn`
(user+network namespace), after verifying in that same namespace that
networking is unreachable (`urllib.request.urlopen('https://api.openalex.org')`
→ `URLError: Network is unreachable`). Result: 93 passed offline.

Unpaywall/EuropePMC paths exercised offline: Unpaywall `is_oa` true/false;
`best_oa_location` first + dedup against `oa_locations`; version ranking
(published > accepted > submitted, unknown last); PDF-beats-better-version
rule; landing-page fallback when no `url_for_pdf` anywhere; closed-access
fall-through to Europe PMC; arXiv ids declined outright. Europe PMC:
`isOpenAccess=Y/N` gating, pmcid required, `fullTextXML` URL construction,
JATS→markdown parsing (title/abstract/nested-section headings/xref tails kept
without eating sentences/back-matter dropped/figure captions/list items/
unparseable+empty → None). Orchestration: never-shrink bar,
`oa_min_full_text_chars` floor rejecting repository record pages, junk-gate
rejection, per-candidate fall-through on None AND on raise, attempt cap,
SSRF refusal before fetch, disabled-config no-ops, rescue path incl. its
independent `oa_rescue_blocked` switch. Disclosure: substitution vs rescue
banners (rescue asserts NOTHING came from source; multi-line reasons stay
inside the blockquote via `_one_line`), version-of-record quoting warning,
`oa_*` frontmatter shape incl. `kind="rescued"`.

### Test porting decisions

- `tests/test_core/test_oa_recovery.py`,
  `tests/test_core/test_scholar_enrichment.py`: byte-identical to upstream
  (diff-verified).
- `tests/test_core/test_source_ranking.py` backfill: module-level
  `from hyperresearch.core.scholar import extract_doi` added (upstream
  position); TestDoiExtraction taken whole, verbatim, at its upstream slot
  between TestSchemaV9 and TestPageRank; TestRankedSearch taken with only
  `test_quality_reorders_equal_relevance` — it needs just
  `search_fts(quality_ranked=...)`, resolvable since P1-2 (P1-2's notes named
  it for exactly this backfill). Its sibling `test_search_cli_ranked_flag`
  stays deferred with the CLI piece (typer app). Pre-existing classes
  untouched (diff-verified region TestSchemaV9..TestDoiExtraction boundary).

### enrich.py ships with no upstream tests

Verified by grep over upstream tests/: there is NO test file exercising
`auto_tag`/`auto_summary`/`enrich_note_file` (test_scholar_enrichment.py
tests scholar.score_sources despite the name). Consumers are
`cli/research.py`, `cli/repair.py`, `cli/fetch_batch.py`, `mcp/server.py` —
all lazy imports, none wired here. Nothing to skip or defer; the test window
opens with those pieces.

Result: 335 passed, 6 skipped (unchanged skips), ruff clean, `mypy src`
strict clean (39 source files). Offline proof above.

### Out-of-scope imports discovered (feed later builders)

- OA orchestration consumers are `cli/fetch.py` (rescue at :332, recover at
  :418, banner/frontmatter emission) and `cli/fetch_batch.py` (:166/:197/:220)
  — both lazy-import `recover_full_text`/`rescue_full_text`/
  `recovery_notice`/`oa_frontmatter`; the fetch CLI pieces must reproduce
  those call shapes (incl. `blocked_reason=` wording and original-chars
  accounting).
- `cli/sources.py` consumes `score_sources`/`backfill_dois` (lazy) — sources
  CLI piece gets them ready-made with full offline coverage.
- `core/scholar.extract_doi` on fetcher's main path is NOW live end-to-end
  (fetch_and_save imports it unguarded since the ignore removal); upstream
  ships no direct fetcher tests (grep-verified in P1-4), so no test debt
  moved — the fetch CLI's e2e tests remain with their owner.
- oa.py docstring references `web.safe_http.check_url` (PR #53) as a future
  collapse target for `check_oa_url` — that module does not exist in upstream
  v0.10.0 either; comment kept verbatim for the future hardening piece.
- `enrich_note_file` consumers (research/repair/fetch_batch/mcp) listed
  above; `auto_tag`'s inline `import math` kept verbatim (loop-local).

## P1-5 hardening — twin-site SSRF closure (ownership granted)

Closes the two fixed-API-host fetch lanes and the one substring host
classifier FILED by the P1-4 hardening twin sweep ("when ownership allows,
route both through `_netguard.guarded_get`") — core/{oa,scholar}.py ownership
granted with the P1-7 remediation wave. Both regressions were proven to FAIL
against pre-fix code before the fix landed (pre-fix, the stubbed lanes issued
`follow_redirects=True` requests and the spoofed hosts classified as
DOI-bearing; 7 failed / 4 passed across the 11 twin tests in the window —
the 4 both-side passes are positive/soft-failure contract pins).
Patterns mirror tests/test_web/test_ssrf_guard.py; fully offline.

- **`core/scholar.py::_http_get_json`** (OpenAlex/S2/Unpaywall/EPMC lookups)
  now goes through `web._netguard.guarded_get`: start URL validated, then
  every redirect hop re-validated (manual following, relative Locations
  resolved per-hop, >5 hops rejected). `UnsafeUrlError` logs
  `blocked by SSRF guard while fetching ...` at WARNING and returns None —
  the module's every-failure-is-soft contract is unchanged.
  Tests: test_scholar_enrichment.py::TestHttpGetJsonSsrfGuard::* (loopback
  start never requested; public-shaped 302 → intranet.internal dies BEFORE its
  request; success path unchanged).
- **`core/oa.py::_http_get_text`** (Europe PMC JATS full text): same routing.
  `check_oa_url` still gates candidate URLs up front, but only their initial
  address — redirects were previously unchecked on this lane.
  Tests: test_oa_recovery.py::TestHttpTextSsrfGuard::* .
- **`core/scholar.py::extract_doi` doi.org classifier**: `"doi.org" in netloc`
  substring replaced by exact/suffix match (`host == "doi.org" or
  host.endswith(".doi.org")`, mirroring crawl4ai's `_on_arxiv_host`), so
  `notdoi.org.evil.com` / `doi.org.evil.com` no longer route their PATH through
  the DOI extractor. `parsed.hostname` (port-stripping, already lowercased)
  replaces raw `netloc`.
  Tests: test_scholar_enrichment.py::TestDoiHostExactMatch::* (spoofed
  suffix/prefix rejected; real host, www subdomain, and :443 port still
  classify).

## P1-7 — Profiles/render/levers/templates machinery + indexgen (+ [models] alias table)

Ported near-verbatim from upstream v0.10.0. Sources (6 files):
`core/{profiles,render,levers,templates}.py` and
`indexgen/{__init__,generator}.py`. Tests:
`tests/test_core/{test_profiles,test_render,test_levers,test_prompt_golden,
test_dissertation_profile,test_indexgen}.py` plus fixtures under
`tests/fixtures/golden_prompts/**` and the P1-1-scheduled restoration in
`test_config_sections.py`.

### THE delta: `[models]` alias table + EMPTY-INHERIT ModelMap defaults

Planner-decided default (this is the one behavioral change of the piece):

- Upstream `ModelMap` shipped Claude-facing per-role pins (sonnet ×7 fetch/
  verify-lane roles, opus ×6 drafting/critic roles). Our port's default alias
  map is EMPTY-INHERIT: every ModelMap field defaults to `""`, and `""` means
  "run this agent on the session model" — opencode agents inherit the session
  model unless explicitly pinned. All 13 upstream role keys are still
  recognized (`extra="forbid"` set unchanged), so upstream configs parse and
  round-trip.
- New vault-global alias table under `[models]` in `.hyperresearch/config.toml`
  (`role = "model-or-alias"`). Resolution per role, most specific wins:
  profile-overlay `models = { role = ... }` > `[models]` > inherit (`""`).
  An explicit `""` in a profile overlay genuinely inherits even over a global
  pin (dict merge is per key). Unknown role or non-string value anywhere in
  either layer fails loudly through the existing `ProfileError("invalid
  profile …")` wrapper.
- `VaultConfig` gained `model_overrides: dict[str, Any]` (raw `[models]`
  table) — loaded in `load()`, round-tripped verbatim by `save()` like
  `profile_overlays`, so a config write never silently drops role pins.
  This is a small scheduled extension of `core/config.py` ("profile/config/
  render machinery" names config in the piece scope); no other config
  behavior touched.

Consequences folded into the ported tests (each marked "Delta vs upstream
(P1-7)" in-source):

- `test_profiles.py::TestBuiltins.test_full_matches_shipped_pipeline_values`
  pins `models.fetcher == ""` / `models.synthesizer == ""` where upstream
  pinned sonnet/opus.
- `TestUserOverlay.test_models_overlay_swaps_one_agent` asserts unspecified
  roles stay `""`.
- Upstream `test_empty_model_assignment_rejected` was REPLACED by
  `TestModelsAliasTable.test_explicit_empty_assignment_means_inherit`: `""`
  was an error upstream; it is now the inherit sentinel. Whitespace-only
  values normalize to `""`.
- New `TestModelsAliasTable` (11 tests): cross-profile pinning, overlay-beats-
  table precedence, unknown-role/non-string/non-table rejection, whitespace
  normalization, VaultConfig save/load round-trip, empty-section tolerance.

Everything else in profiles/render/levers/templates/indexgen is verbatim
modulo strict-mypy annotations (table below).

### Golden prompts: outcome (regenerated once, frozen)

Policy applied literally: "if output matches upstream byte-for-byte, say so
instead of regenerating."

- Method: upstream's own template sources (the 8 skill .md files and the 10
  agent constants in upstream `core/hooks.py`) were rendered through THIS
  port's `build_render_context(None)`/`render_prompt` and diffed against
  upstream's committed goldens. hooks.py was loaded BY FILE PATH purely as a
  string container (all its hyperresearch imports are lazy); every
  `hyperresearch.*` import resolved to the port tree (asserted in the script).
  First attempt of this experiment was INVALID (reference tree prepended to
  sys.path imported upstream's engine) and was discarded before any fixture
  was written.
- Result: **skills 8/8 BYTE-MATCH** — copied verbatim, zero regeneration,
  zero deltas.
- Agents: **exactly ONE line differs per file** — the `model:` frontmatter
  line (`model: sonnet` / `model: opus` upstream vs `model: ` here). That is
  solely the decided `[models]` empty-inherit default above. Per policy those
  10 lines were regenerated once so the frozen fixtures equal current output
  exactly:

  golden delta: agent `model:` frontmatter lines empty (sonnet/opus → "") —
  [models] empty-inherit default (see §P1-7 THE delta). Files:
  browser_fetcher L12, cite_checker L11, depth_critic L9,
  depth_investigator L11, dialectic_critic L9, instruction_critic L12,
  loci_analyst L11, readability_reformatter L12, researcher L9, width_critic
  L8. Post-regeneration re-run: 18/18 BYTE-MATCH.

- Raw evidence: `evidence/p1-7/golden-model-line-deltas.txt` (pre-regen diff
  vs upstream goldens) and `evidence/p1-7/golden-render-check.txt` (18/18
  match against the frozen fixtures).

### test_prompt_golden.py staged, not activated

Every test in the file renders template sources owned by `core/hooks.py` +
the `skills/` package — a later piece per PARITY §13–14 (PORT-ADAPT;
opencode-facing variants land there, per plan). Following the P1-1 skip-
in-place precedent: the file is byte-faithful except (a) the hooks imports
are guarded try/except (same pattern as conftest's `_reset_render_state`),
(b) a module-level `pytestmark = pytest.mark.skipif(not _HOOKS_AVAILABLE)`
stages all 72 tests, (c) two import blocks re-ordered by `ruff --fix` (I001;
our ruff sorts what upstream's didn't), (d) the module docstring documents
the freeze + activation path. When the hooks piece lands its module, the
tests activate UNCHANGED against the frozen fixtures — any drift then maps
to that piece's own golden-delta lines. conftest needed no edit.

### Test porting decisions (surveyed all of upstream tests/)

- `test_render.py`: byte-identical copy (diff-verified); fully resolvable.
- `test_profiles.py`: `TestBuiltins`/`TestUserOverlay`/`TestValidation` run
  (with the ModelMap adaptations above + the new alias-table class);
  `TestProfileCli` kept byte-faithful but skipped (needs the typer app +
  tmp_vault CLI wiring — PARITY §15 piece restores verbatim).
- `test_levers.py`: `TestCompose` runs unmodified. `TestRenderCli`/`TestVerifyGate`
  need `core/runs.py` (`init_run`/`load_manifest`/`verify_run`) and the CLI
  app — skipped via guarded `core.runs` import; bodies byte-faithful.
  `levers.render_shims` keeps upstream's lazy `core.runs` import with a
  self-cleaning `# type: ignore[import-untyped]` (P1-4 pattern): until runs
  lands it raises ImportError AFTER writing the shim files; warn_unused_
  ignores fails the gate when runs arrives, forcing removal.
- `test_dissertation_profile.py`: `TestDissertationProfile` runs unmodified;
  `TestLiteratureMatrix`/`TestTargetGrouping` skipped pending `core/claims.py`
  (+ typer app for the matrix-file test); bodies byte-faithful behind a
  guarded claims import.
- Upstream ships NO indexgen tests anywhere (grep-verified; only consumers
  are `cli/{index,repair,watch}.py`, later pieces). NEW
  `tests/test_core/test_indexgen.py` (11 offline smoke tests) pins the
  module against OUR Vault — page set, frontmatter/footer shape, stale-page
  cleanup, 3+-note tag/month thresholds, orphan + most-linked logic, stats
  tables — mirroring the P1-2 precedent of covering upstream-untested
  modules at landing.
- `test_config_sections.py`: restored the two assertions P1-1 deferred to
  "the profiles piece" — the `resolve_profile` tail of
  `test_overlays_survive_save` and `test_builtin_override_survives_save`,
  both now byte-equal to upstream.

### mypy --strict annotation deltas (zero logic changes)

| File | Delta |
|------|-------|
| core/profiles.py | `_FULL/_LIGHT/_PREMIER/_DISSERTATION: dict` → `dict[str, Any]`; `BUILTIN_PROFILES: dict[str, dict]` → `dict[str, dict[str, Any]]`; `_load_user_overlays` return + local `out` parameterized |
| core/render.py | `_dash`/`_hyphen` params annotated `tuple[int, int]` (jinja passes profile ranges) |
| core/levers.py | TYPE_CHECKING `Vault` import; `vault` params annotated ×4; `_decomposition_path -> Path`; `validate_levers`/`_header`/`_domain_block`/`read_levers`/`set_levers` dict params/returns → `dict[str, Any]`; `compose_shims` already typed upstream; `written` annotated `list[str]`; lazy core.runs ignore (above) |
| core/templates.py | `get_template`/`list_templates` dir param annotated `Path \| None` (upstream bare `None` default, unannotated); `templates: list[dict]` → `list[dict[str, str]]` |
| indexgen/generator.py | TYPE_CHECKING `Vault` + module-level stdlib `sqlite3` (Row typing, annotation-only); constructor param annotated; `build_all`/`_write_index`/builders given explicit returns; bare `dict[str, list]`/locals parameterized (`sqlite3.Row`, `dict[str, int]`, `list[str]`) |
| core/config.py | field only: `model_overrides: dict[str, Any]` + load/save lines (THE delta above) |

Ruff: pyproject's pre-seeded per-file-ignores for profiles/render/
test_render/test_prompt_golden (en-dash RUF001/RUF002 policy) covered this
piece exactly as staged in P0-2; no lint-config changes.

Result: **404 passed, 96 skipped**, ruff clean, `mypy src` strict clean
(45 source files). Skip ledger: 6 pre-existing (2 agent-docs vault, 3
crawl4ai fetch_settings, 1 stealth) + 72 golden-module staging + 5
profile-CLI + 8 levers runs/CLI + 5 claims-dependent. Passed delta
+69 over P1-5's 335.

### Out-of-scope imports discovered (feed later builders)

- `core/hooks.py` + `hyperresearch/skills/**` (PARITY §13–14): own the
  golden-test activation; templates must render against the frozen fixtures.
  Note for that piece: with stock profiles, `<< p.models.X >>` renders ""
  (empty-inherit) — its installer decides how opencode frontmaterializes
  unset roles (omit line vs placeholder); any deviation from the frozen
  goldens becomes its documented golden deltas.
- `core/runs.py`: consumes levers' `RunError/_save/load_manifest/
  record_event` tail (signatures used: `_save(vault, tag, manifest)`;
  `record_event(vault, tag, dict)`; `load_manifest` raising `RunError` when
  absent) AND owns the verify gate's `levers-rendered` check + `init_run`
  used by the deferred lever tests.
- `cli/levers_cmd.py` + `cli/profile_cmd.py`: wire compose/render/set and
  profile show/list/validate/use; restore the five skipped profile-CLI tests
  verbatim.
- `core/claims.py`: restores the skipped matrix/grouping tests (also needs
  `cli/claims_cmd.py` for the file-writing variant).
- `cli/{index,repair,watch}.py`: consume `IndexGenerator.build_all` /
  single builders (lazy upstream); `VaultConfig.index_pages` lists the five
  canonical page stems already built here.

## P1-7 remediation — gauntlet verdict-r1 defects D1–D6 fixed

From `evidence/gauntlet/P1-7-verdict-r1.md`. D1 was OUR regression (the
`[models]` layer added in the P1-7 port); D2–D6 were inherited verbatim from
upstream v0.10.0 (diff-checked against the pinned reference tree). Disposition
per verdict: all six fixed in-port as cheap correctness wins. Falsification
discipline unchanged from prior waves: of the 34 new tests, 27 FAILED against
pre-fix code before the fix landed; the other 7 are both-side contract pins
(zero stays legal where designed, stale-page cleanup still works, documented
lever keys still accepted, real doi.org hosts still classify ×3, soft-failure
contract) that pass on BOTH sides and would catch over-rejection regressions.
Window highlights: the D1 PoC raised bare `TypeError: 'str' object is not a
mapping` outside the ProfileError wrapper and the D4 PoC died on
`FileNotFoundError ... index/_tag-ml/theory.md` after the unlink sweep.

1. **D1 MEDIUM — non-table `models` overlay escaped the ProfileError wrapper.**
   `[profile.full] models = "haiku"` reached `{**aliases, **overlay["models"]}`
   and died with a bare TypeError OUTSIDE the try/except around
   `Profile(**merged)` (upstream wraps this same case). The overlay's shape is
   now validated at the merge boundary:
   `ProfileError: profile '<name>': models overlay must be a table of role =
   model assignments, got str`.
   Test: TestP17Remediation::test_non_table_models_overlay_rejected_as_profile_error
   ("haiku" / 5 / true / [1,2]).

2. **D2 MEDIUM — dict-of-Range fields skipped ordering validation.**
   `_range_ordered` covered only the tuple Range fields; an inverted entry like
   `word_targets = { short = [9000, 200] }` validated clean and reached
   prompts. New `_dict_ranges_ordered` applies the same low<=high rule per
   entry to must_read / word_targets / char_targets_no_word_boundary /
   citation_totals, naming the offending key
   (`range 'short' low 9000 > high 200`). `depth_budget_brackets` is
   deliberately NOT ordered-checked — its rows are (score_threshold, budget),
   not ranges, and ship inverted by design ((30, 15) …).
   Tests: TestP17Remediation::test_inverted_dict_range_rejected ×4 fields.

3. **D3 MEDIUM — no non-negativity validation on scalar knobs.**
   `source_min = -5` resolved happily into gates that can never fire. Upstream
   semantics checked FIRST per the audit's guard: zero IS load-bearing and
   stays legal — chapters == (0, 0) means unchaptered, depth_budget_brackets
   bottom out at score threshold 0, a zero interval/cap means off/always — and
   no shipped upstream value anywhere is negative. Negatives are therefore
   rejected wholesale by a `"*"` validator walking scalars, range elements,
   dict values, and bracket rows, with the key path in the message
   (`critic_finding_caps['dialectic'] must be non-negative (got -3)`). Bools
   exempt (int subclass).
   Tests: TestP17Remediation::{test_negative_scalar_knob,test_negative_cap_value,
   test_negative_range_element,test_negative_float_knob}_rejected +
   test_zero_stays_legal_where_designed.

4. **D4 HIGH-operational — '/' in a tag crashed build_all AFTER it had unlinked
   every existing index page**: `_tag-{tag}.md` became a nested path whose
   parent never exists (`FileNotFoundError index/_tag-ml/theory.md`), leaving a
   vault with zero indexes until the next successful rebuild. Two-part fix:
   - tags are slugified for filenames AND `_tags.md` wikilink targets with the
     same `slugify()` used for note ids (`ml/theory` → `_tag-mltheory.md`),
     so any tag yields a flat, non-empty, length-capped filename;
   - `build_all` is now render-then-swap: every page renders into memory
     first; stale pages NOT in the new generation are unlinked second;
     replaced pages are overwritten in place, never unlinked. Any mid-render
     failure leaves the previous generation byte-identical on disk.
   Tests: TestTagSlugSafety::* , TestCrashSafeRebuild::* .

5. **D5 LOW-MED — raw title/tag interpolation corrupted markdown/YAML.**
   Titles/summaries/tags were f-stringed straight into generated pages: a
   newline started its own bullet or heading inside an auto-maintained page,
   and a literal `"` closed the hand-written double-quoted YAML title scalar.
   All free-text interpolations now collapse whitespace to single spaces
   (`_flat`), and frontmatter scalars escape backslash then quote
   (`_yaml_scalar`) — a note titled `Real Title\ninjected: …` renders as one
   inline bullet line and a tag `say "hi"` produces parseable
   `title: "Tag: say \"hi\""`.
   Tests: TestInterpolationEscaping::* .

6. **D6 LOW — unknown lever keys silently no-op'd**, contradicting the
   module's fail-loud posture: upstream validated the register/depth enums but
   merged unknown keys straight through, so a typo'd key just ran on defaults.
   `validate_levers` now rejects any key outside the documented decomposition
   schema (register / register_confidence / domain_notes / inference_depth /
   rationale) BEFORE the merge — None-valued ones included, since the value
   filter would otherwise hide the typo behind a null.
   Tests: TestCompose::test_unknown_key_rejected,
   ::test_none_valued_unknown_key_rejected,
   ::test_documented_extra_keys_accepted.

Result after remediation: **483 passed, 96 skipped** (+34 regressions over the
449 baseline; skip ledger unchanged), ruff clean, `mypy src` strict clean
(46 source files).

## P1-8 (part 2): verification/escalation/claims test port
Ported upstream test_verification.py -> tests/test_core/test_verification.py,
test_escalation.py, claims half of test_claims_and_embed.py -> test_claims.py
(embed half already in test_embed.py from P1-2). Skip ledger (each names its activator):
- Content-gate positives (quote-integrity/retracted-citations named checks; CJK-pass;
  well-formed-pass; finish-marks-done; finish-blocks-quote; fix-then-done; verify-includes-gates):
  rule engines live in cli/lint.py -> P1-10. Until then verify_run's ImportError branch
  fails closed BY DESIGN (upstream-faithful); negatives still prove the gate blocks.
- TestVerificationLints (whole class), citecheck/claims/run-status CLI methods,
  TestFetchGateIntegration, TestEscalationCli, TestRunStatusIntegration: typer app verbs -> P1-9/P1-10.
- TestIndependence: covered by test_independence.py (P1-3).
- TestCiteCheckerAgentInstall, TestBrowserFetcherAgent: core.hooks installers -> Phase 2 renderer piece.
NOTE for P1-10 builder: activating the content-gate skips is part of your done-definition;
AC-4's negative battery depends on them.

## P1-9 — vault-ops CLI groups + assembly

Ported near-verbatim from upstream v0.10.0. Sources (19 files): the 17 in-brief
modules `cli/{note,tag,topic,graph,index,batch,assets,export,git_cmd,watch,
archive,dedup,link,repair,vault_tag,template,_output}.py`, plus the scheduled
`cli/main.py` (init/status/sync — upstream :1-169) and the `cli/__init__.py`
assembly replacing the P0-2 placeholder scaffold.

### Assembly (`cli/__init__.py`)

Mirrors upstream registration order exactly (root commands :60-102, sub-app
block 1 :104-127, block 2 :129-150), minus P1-10's research-ops groups: root
commands install/setup/search/fetch/fetch-batch/research/import/serve/mcp;
sub-apps config/lint (block 1) and profile/claims/embed/run/escalation/
citecheck/levers/sources (block 2). Every omitted slot carries an explicit
"P1-10 slot" marker at its upstream position so final assembly is a pure
insertion. The P0-2 deltas stand (no pyver guard, no Windows cp1252 shim);
the version callback and app constructor are byte-identical to upstream.
Entry contract unchanged: `hyperresearch.cli:app`.

### Byte fidelity + strict-mypy deltas (annotation-only unless stated)

Byte-identical (diff-verified, zero deltas): `index.py`, `link.py`,
`vault_tag.py`, `template.py`. All other files carry only marked deltas:

| File | Deltas |
|------|--------|
| _output.py | bare generics parameterized ×4 (`_print_dict`, `_print_list`, `print_note_summary`, `print_vault_status`) |
| main.py | empty containers annotated (`by_status`/`by_type: dict[str,int]`, `top_tags: list[dict[str,Any]]`) |
| note.py | `_fetch_note -> dict[str,Any] \| None`; containers annotated; `note_new`'s heterogeneous `data: dict[str,Any]`; `payload: dict[str,Any]` |
| tag.py / topic.py / graph.py | container annotations; topic's `_build_rich_tree` fully annotated (TYPE_CHECKING `rich.tree.Tree`) |
| batch.py | helpers fully annotated (`_discover_vault -> Vault`, `_get_matching_notes`, `_batch_update_files`, `_update_file_frontmatter`; TYPE_CHECKING Vault import) |
| assets.py / export.py | `params: list[Any]` |
| git_cmd.py | TWO behavioral fixes (below) + container annotations |
| watch.py | handler methods annotated; `_quick_lint(vault: Vault)`; `str(event.src_path)` coercion — newer watchdog stubs type src_path bytes; runtime identical |
| archive.py | `data: dict[str,Any]` declared once before the three branch assignments; `moved: list[dict[str,str]]` |
| dedup.py | bare dicts/lists parameterized throughout helpers |
| repair.py | ONE behavioral delta (below) + local rename |

Typing-only ignores: `meta.status/tier/content_type = <raw str>` assignments in
note.py update and repair.py promotion carry `# type: ignore[assignment]` with
an in-source comment — NoteMeta runs `use_enum_values=True` so the runtime value
IS the raw string upstream assigns; the declared StrEnum annotation is what mypy
objects to. Behavior byte-identical.

### Behavioral delta 1: repair.py step 6 is a documented no-op

Upstream ends `repair` with a lazy
`from hyperresearch.core.agent_docs import inject_agent_docs; modified =
inject_agent_docs(vault.root)` on the DEFAULT path (--docs is default-on).
core/agent_docs.py is a later piece (AGENTS.md injector); rather than crash
every default invocation, the call is removed per the P1-1 precedent and the
step reports `agent_docs: []` / "Already up to date", with an in-source comment
naming the restoration condition. Restore together with core/agent_docs.py.

### Behavioral fixes 2+3: git_cmd.py inherited defects (fixed, falsified pre-fix)

Both were found by the new smoke battery, verified against the pinned reference,
and are the mechanical kind this repo fixes when it owns the file:

1. **`git log` could never succeed anywhere.** Upstream appends the SINGLE argv
   token `"-- *.md"` (`args.append("-- *.md")`). subprocess passes it verbatim;
   git answers `fatal: unrecognized argument: -- *.md`, rc=128 → NOT_GIT error
   path → "Not a git repository" for every user with a perfectly valid repo.
   Fixed by splitting into separator + pathspec (`args.extend(["--", "*.md"])`);
   verified `*.md` matches nested research/notes/*.md via git's non-shell
   pathspec semantics. Falsification: pre-fix code exits 1 in a committed repo
   (observed during development; test_log_lists_md_commits fails against
   verbatim behavior).
2. **Untracked .md never rendered "untracked".** `git status --porcelain`
   emits the two-char code `??`, but the change-type map keyed `"?"` — the
   lookup always fell through to the raw `"??"`. The map AND the rich style
   table both name "untracked", proving intent. Map key corrected to `"??"`.
   Falsification: test_changed_reports_untracked_md fails against verbatim code
   (returns "??" instead).

### Filed inherited defect (NOT fixed — needs core/ ownership)

`link --auto --dry-run` does not prevent file modification: cli/link.py calls
`auto_link(...)` FIRST (which appends Related sections via core/linker.py), and
only consults dry_run when deciding whether to re-sync the DB. Net effect:
"--dry-run ... Show what links would be added" still EDITS files on disk, it
just leaves them out of the DB until the next sync. A correct fix needs a
dry-run-aware linker (snapshot/restore or a flag threaded into auto_link) —
core/linker.py is outside this piece's ownership. Pinned as actual behavior in
test_vault_ops.py::TestLinkCli::test_dry_run_skips_db_sync_but_still_writes_files
with the defect documented in-source.

### Test porting decisions (surveyed all of upstream tests/test_cli/)

Upstream ships nine CLI test files; three are wholly this piece's, one is split:

- `tests/test_cli/__init__.py` + `test_note_ops.py` (6 tests),
  `test_archive.py` (5), `test_vault_tag.py` (7): BYTE-IDENTICAL copies
  (diff-verified).
- `test_commands.py`: trimmed of exactly the P1-10-owned tests —
  test_search_text + test_search_json_wraps_fetched_bodies_as_untrusted
  (cli/search.py) and test_lint (cli/lint.py) — each removal site carries a
  comment naming the owner and ordering a verbatim restore. Everything else
  byte-faithful, including the three `<untrusted-source>` fence variants whose
  note-show two ARE this piece (P1-6 scheduled their backfill here; they pass
  unmodified against the ported wrap). Kept upstream's plain `os.chdir`
  fixture style verbatim.
- NEW `tests/test_cli/test_vault_ops.py` (38 offline smoke tests): upstream
  has NO CLI coverage for topic verbs, graph backlinks/outlinks/orphans/hubs/
  stub/rank, tag alias/suggest, note update, all five batch verbs, export
  vault, git views, template show, dedup, link, assets, or repair — covered
  here through the typer app per the established cover-at-landing practice
  (P1-2 similarity guard, P1-7 indexgen). Git lanes use a throwaway repo;
  everything else touches only tmp files. This file is what surfaced the two
  git_cmd defects above.
- ACTIVATED SKIP (the only one owned by this piece):
  tests/test_core/test_runs.py::TestWorkspaceIsolation::
  test_vault_tag_collision_includes_run_dirs — needed
  `cli.vault_tag._existing_tags`, which now exists; skip marker removed,
  test passes unmodified.

### Skipped-still ledger (all naming owners; NONE activatable by P1-9 files)

Every remaining suite skip names its activator; for the record grouped by
owner — P1-10: content-gate positives ×6 (cli/lint.py rule engines),
TestVerificationLints ×4 (lint), citecheck/run-verify/run-finish verbs ×3,
run resume/status ×3, lint helper unit tests ×3 (_run_artifact/_query_files),
fetch-gate + escalation CLI ×2, claims ingest verb ×1, TestProfileCli ×5
(profile_cmd), levers render/verify ×8 (levers_cmd), matrix/grouping ×3
(claims_cmd + claims module). Phase-2 renderer: golden module staging ×72,
hooks agent installer ×2. Environment: crawl4ai extra ×4. Agent-docs piece:
vault AGENTS.md doctrine ×2.

Result: **607 passed, 120 skipped** (+72 passed, −1 skipped vs the 535p/121s
baseline), ruff clean, `mypy src` strict clean (67 source files, was 46).
Command surface check: `hpr --help` lists exactly the 10 root commands + 11
sub-apps above; hidden root `show` alias resolves to note show.

### Out-of-scope imports discovered (feed later builders)

- `cli/note.py::new` renders templates via core.templates (present since P1-7);
  nothing new unresolved. All lazy imports across the 17 modules resolve
  in-tree EXCEPT the two known forward references: core/agent_docs.py
  (repair step 6 — see delta 1) and, untouched here, the P1-10 modules
  themselves.
- For P1-10: `watch.py::_quick_lint` stays a self-contained quick summary —
  upstream wires `--lint` to THIS helper, not cli/lint.py; do not couple them.
- For the agent-docs piece: restore repair step 6 (call + modified-paths
  report) and the two vault AGENTS.md skips together.
