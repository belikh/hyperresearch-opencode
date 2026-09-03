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

## Critic-gap closure wave (post-P1-9)

Four blind gauntlet critics picked this tree over upstream for P1-5/7/8/9 and
named six residual gaps. All six closed; every behavioral fix falsified
pre-fix (final test versions run against stashed-original source: all FAIL;
post-fix: PASS). Gates at close: pytest 617 passed / 120 skipped
(baseline 607/120), ruff clean, mypy --strict clean.

### H-1 — indexgen crash-window + hostile month key (`indexgen/generator.py`)

`_build_by_month` interpolated raw frontmatter `created` into the FILENAME
`_month-{created[:7]}.md`. Filenames are inert dict keys during render, so a
hostile value (`../../pwn`) staged fine — then crashed `write_text` with
FileNotFoundError AFTER `build_all` had unlinked every page not in the fresh
set: vault left indexless, render-then-swap guarantee voided. Tag slugs were
re-verified safe without changes (slugify strips `/ . \` + caps length);
title interpolation was already escaped via `_yaml_scalar`/`_flat`.

Fix: month keys must fullmatch `\d{4}-\d{2}` or build_all raises ValueError
during RENDER (before any disk mutation); `_stage()` additionally enforces
`^_[\w.-]+\.md$` on EVERY staged filename as a structural invariant, so no
data-derived filename can reach the write phase unsafe. Prior generation
stays byte-identical on any failure. Falsification:
`test_hostile_created_raises_before_touching_disk` → pre-fix FAILED with
`FileNotFoundError: .../research/index/_month-../../p.md`, post-fix PASS.
Pin (both sides pass): `test_happy_path_month_pages_unchanged`.

### H-2 — test double-skip defect (`tests/test_core/test_levers.py`,
### `tests/test_core/test_dissertation_profile.py`)

TestRenderCli and TestLiteratureMatrix carried a conditional skipif AND an
unconditional class-body `pytestmark = pytest.mark.skip` that won forever —
with a copy-pasted reason ("levers render / profile matrix" in both files).
Removed both unconditional marks; each class keeps ONE conditional skipif
whose condition probes what it really needs (core.runs/core.claims AND the
typer verb group). Probes import `hyperresearch.cli.levers_cmd` /
`hyperresearch.cli.claims_cmd` — the exact modules upstream registers for
those groups, so the skips self-release when P1-10 lands. Verified today:
skips report accurate reasons via the single mechanism; with levers_cmd
stubbed into sys.modules, skipif evaluates False (tests would run).
Not behavioral code → not in the falsify-required set; mechanism proof above.

### H-3 — Vault import-cycle risk (`core/{runs,escalation,citecheck,claims}.py`)

All four imported Vault at module level purely for annotations while running
under `from __future__ import annotations`. Moved behind TYPE_CHECKING
(grep-verified zero runtime uses in each file; generator/batch already used
the pattern). mypy --strict clean post-move.

### H-4 — `index show` path escape (`cli/index.py`)

User-supplied name joined raw onto `vault.index_dir`: `../secret` read any
file outside the vault. Now resolves and requires containment within
index_dir; escapes emit the standard envelope (`INVALID_PATH`, exit 1) in
both JSON and plain modes. Benign-but-missing names keep upstream's plain
not-found path (left as upstream). Falsification:
`test_dotdot_escape_rejected_with_envelope` → pre-fix exit 0 with the secret
file's contents served; post-fix PASS. Also pins benign `_tags` show.

### H-5 — `note mv` destination escape + silent overwrite (`cli/note.py`)

`vault.root / new_path` accepted absolute paths (Path join replaces root)
and `..`; POSIX rename silently OVERWROTE an existing destination file.
Destinations must now resolve inside `vault.root` (`INVALID_PATH`); an
existing destination is refused (`DEST_EXISTS`) with both notes intact.
Falsification: dotdot / absolute / collision tests → pre-fix all exited 0
(move out succeeded, alpha-note silently destroyed by collision); post-fix
PASS with clean envelopes. Pin: normal move still works.

### H-6 — dangling numbered citations dropped (`core/citecheck.py`)

`extract_pairs` skipped `[N]` with no Sources entry (`if num in numbered_map`)
while wikilinks recorded dangling entries — fabricated `[7]` sailed past the
ship-gate dangling counts. Now `numbered_map.get(num)`: unmapped numbers
record note_id=None → triage counts them dangling. Mapped-but-unresolved [N]
behavior unchanged (already None pre-fix). Upstream structure otherwise kept
(this IS a delta vs upstream v0.10.0, adopted deliberately). Falsification:
`test_unmapped_numbered_citation_is_dangling` → pre-fix pairs == []; post-fix
dangling pair recorded.

### Deliberately left filed rather than fixed

- `_build_raw_pending`/`_build_by_month` embed DB date strings into body
  bullets WITHOUT `_flat()` — a newline-bearing `created` could break one
  bullet line. Not a crash window, unreachable through sync's NoteMeta
  validation; left for upstream parity (needs a content-level decision).
- `note mv` self-move (destination == current path) now errors DEST_EXISTS
  instead of silently "succeeding" — consequence of the collision guard,
  judged correct (a scripted no-op rename is a user error).
- `note mv` FileNotFoundError when the DB row exists but the file is gone
  remains unhandled (upstream parity).
- TestLiteratureMatrix's pure-core tests stay class-skipped until P1-10
  (skipif is class-granular); splitting classes would deviate from the
  upstream test structure beyond this wave's mandate.

### Wave 2 (untrusted U1-U5)

A fresh blind critic re-audited core/untrusted.py (P1-6 surface), confirmed
the upstream deltas, and named five residual gaps. All five closed in
core/untrusted.py alone (single consumer cli/note.py::show untouched — same
signatures, benign-output byte-compatible). Every behavioral fix falsified
pre-fix via git stash round: tests committed first against HEAD source (17
FAILs recorded below), then against `git stash push --
src/hyperresearch/core/untrusted.py` (same 17 FAILs + 1 helper ImportError),
then after pop: file green. Gates at close: pytest 640 passed / 120 skipped
(baseline 617/120; +23 tests), ruff clean, mypy --strict clean (67 files).
ReDoS probe on the new matcher: linear, worst shape 57ms @ 100KB adversarial
input (possessive quantifiers; see U-1).

U-1 (HIGH) — Unicode-confusable forged closers bypassed _FENCE_TAG_RE:
`<\u200b/untrusted-source>`, `</untru\u00adsted-source>`,
`</\ufeffuntrusted-source>` and bidi-overlay variants survived neutralization
verbatim, so a downstream Cf-normalizing consumer could reassemble a LIVE
closing fence inside "inert" data. Fix (fail-CLOSED): fence candidates are
now matched on a Cf-stripped skeleton — every tag-name letter tolerates runs
of Unicode format chars (category Cf), plus Cf in the structural slots around
`/`. Anything whose skeleton matches is forged and renames to the canonical
sentinel. Implementation notes: (a) the Cf set is a HARDCODED 21-range table
(Unicode 16.0, 170 codepoints) — computing it from unicodedata at import was
measured at ~641ms/process on the `note show` path; drift guard
test_cf_table_covers_running_unicode fails CLOSED if a running interpreter's
Unicode DB knows a Cf codepoint the table lacks. (b) Separator runs use
possessive quantifiers (*+, py3.11+): separator classes are disjoint from the
surrounding literals so semantics are unchanged, but catastrophic backtracking
on adversarial input ("<" * 50k, Cf floods) is foreclosed — benchmarked
linear. (c) Scope rule: only candidates whose Cf-stripped SKELETON equals the
fence-tag pattern are treated as forged. A letter-SUBSTITUTING overlay
(`</untr\u202ested-source>` → skeleton `untrsted-source`) does NOT match and
is left inert-by-construction (not reassemblable into the canonical closer by
Cf normalization); the additive embedding `</untr\u202eusted-source>`
(skeleton = exact closer) IS neutralized. Both probed in tests.
Falsification: 5× test_wrap_body_neutralizes_unicode_confusable_fences[*]
→ pre-fix `assert forged not in wrapped` failed with the payload surviving
byte-verbatim into wrapped output (e.g. '<\u200b/untrusted-source>' is
contained here: …); post-fix all PASS with forensic
`</untrusted-source-inner>` emitted. Pins: benign Cf prose
(test_benign_format_characters_pass_through_unmangled) and the pre-existing
byte-exact round-trip prove no wholesale Cf mangling.

U-2 (MED) — C1 controls unhandled: sanitization covered C0+DEL only; the C1
range U+0080-U+009F passed through. Now _C0_C1_CONTROL_RE (renamed from
_C0_CONTROL_RE) includes \x80-\x9f, and _ESCAPE_SEQ_RE gained an 8-bit CSI
alternative `\x9b[0-?]*[ -/]*[@-~]` so lone-byte CSI dies WHOLE
(`\x9b2J` consumed exactly like `\x1b[2J`, no param/final debris); non-CSI C1
initiators (NEL/DCS/ST/OSC single-byte forms) die as stray controls. C0/OSC
behavior byte-compatible with the F-02 battery, untouched and green.
Falsification: test_wrap_body_neutralizes_lone_byte_csi_sequence +
4× test_wrap_body_strips_stray_c1_controls[*] → pre-fix '\x9b'/'\x85'/
'\x90'/'\x9c'/'\x9d' survived in wrapped output.

U-3 (LOW-MED) — control-prefixed source classification fail-open:
is_untrusted stripped whitespace only, so "\x00https://attacker.example/"
classified not-fetched and rendered UNFENCED. Fix: _SOURCE_NOISE_RE strips
C0/space/DEL/C1/Cf GLOBALLY before the scheme check (not edge-only: a spliced
scheme "ht\x00tps://…" must classify too; stripping can only ever create a
scheme prefix that wasn't visible — fail-closed direction). Guards pinned:
trusted types still win, blank/non-http sources still False.
Falsification: 4× test_control_padded_http_source_still_untrusted[\x00|\x1b|
\u200b-prefix, ht\x00tps-splice] → pre-fix returned False (fail-OPEN);
post-fix True.

U-4 (MED) — replacement tag not fixpoint-stable: the emitted
<untrusted-source-inner> sentinel itself matched _FENCE_TAG_RE ('\b' fires
before '-'), so RE-wrapping degraded tags (-inner-inner…) forever. Fix
(normalize-to-canonical flavor): the matcher consumes any existing
obscured '-inner' run and the replacement re-emits ONE canonical suffix —
sanitize(sanitize(x)) == sanitize(x) over the adversarial corpus
(test_sanitization_is_a_fixpoint, incl. stealth-obscured inner suffixes,
'-inner-inner', ambiguous '-innerness' residue which is stable-unmatched).
Honest scope note: wrap∘wrap cannot be literally equal (each wrap adds an
envelope by contract); the guaranteed-and-tested properties are: '-inner-
inner' never appears at ANY wrap depth, the sentinel inventory is stable from
the first wrap on, and exactly one live closer exists at the tail. To make
the property directly testable, the line-86 pipeline was extracted into
_sanitize_body(body) — structure-only refactor, zero behavior change of its
own. Attacker-preseeded sentinels fold to canonical rather than stacking.
Falsification: test_rewrap_does_not_degrade_sentinel_tags +
test_attacker_supplied_inner_suffixes_fold_to_canonical → pre-fix
'-inner-inner' present in twice-wrapped output; post-fix absent at depth 3.
test_sanitization_is_a_fixpoint → ImportError against pre-helper revisions
(behavioral degradation covered by the two black-box tests above).

U-5 (LOW) — html.escape mangled query URLs in provenance: output is plain
prompt text, NOT HTML, so '&'-to-'&amp;' corrupted the one provenance field
shown to the reader while adding zero safety. Replaced wholesale with
deletion-based _URL_NOISE_RE: <, >, ", ' deleted outright (no new tag can
start, the attribute cannot be closed early) plus the same control set as
before, extended to C1/Cf for parity with U-2/U-3. Legitimate query URLs now
survive copy-paste intact. Falsification:
test_query_url_survives_verbatim_in_provenance_attribute → pre-fix attribute
read '…&amp;hl=en&amp;num=20'; post-fix byte-equal to input URL. Companion
test proves breakout is still dead (zero quotes/'<' inside attribute
content); the pre-existing test_wrap_body_escapes_url_attribute passes
UNMODIFIED against the new mechanism.

Wave pins (both sides green): test_cf_table_covers_running_unicode,
test_benign_format_characters_pass_through_unmangled,
test_control_padded_source_still_respects_trusted_types,
test_control_padding_does_not_create_classification,
test_url_defusal_without_html_escape_still_blocks_breakout.

## P1-10 — research-ops CLI half: 16 groups wired, serve/mcp shims, agent_docs, repair --docs real

### Draft disposition (16 untracked modules from the crashed builder)

Each draft was byte-diffed against upstream `src/hyperresearch/cli/<name>.py`
(pinned 15010c5) before anything else. Result:

| Module | Verdict | Delta vs upstream |
|---|---|---|
| citecheck_cmd.py | kept, byte-identical | none |
| claims_cmd.py | kept + annotations | TYPE_CHECKING Vault; `summary: dict[str, Any]` |
| config_cmd.py | kept + rename delta | `coerced: str \| bool` (upstream rebinds `value` str→bool) |
| embed_cmd.py | kept, byte-identical | none |
| escalation_cmd.py | kept + annotations | TYPE_CHECKING Vault; `extra_meta: dict[str, Any]` |
| fetch.py | kept + annotations/renames | signatures annotated; `_rescue -> WebResult \| None`; narrowing assert on rescue pair; `rescued_result` rebind-rename; `extra_meta`/asset lists `dict[str, Any]` |
| fetch_batch.py | kept + annotations/asserts | batch-state annotations (`pending` tuple shape, `failed_urls`, `created_notes`); narrowing assert on rescue pair |
| import_cmd.py | kept, byte-identical | none |
| levers_cmd.py | kept + annotations | TYPE_CHECKING Vault; `updates: dict[str, str]`; `result: dict[str, Any]` |
| lint.py | kept + guarded hook import + annotations/renames | see below |
| profile_cmd.py | kept + annotations | TYPE_CHECKING Vault (`_discover_vault -> Vault \| None`); `row: dict[str, Any]` |
| research.py | kept + annotations | `_save_result` fully typed (sqlite3.Connection/WebProvider/WebResult); `created_notes: list[dict[str, Any]]`; `_extract_links_from_results(results: list[WebResult])` |
| run_cmd.py | kept + annotations | TYPE_CHECKING Vault; `_resolve_tag(vault: Vault, ...)` |
| search.py | kept, byte-identical | none |
| setup.py | kept, verbatim body | hooks import silenced via pyproject override |
| sources.py | kept, byte-identical | none |

Six drafts needed zero source changes beyond nothing at all; the rest carry
annotation-only deltas plus the renames/narrows itemized above. Every
non-annotation delta is mypy-necessity-proven: reverting any one of them to
upstream's exact code reproduces strict-mypy errors on pre-fix code
(verified live for the two lint.py renames — 5 errors [assignment/index]
reappear with upstream naming; for fetch.py:357 and config_cmd.py:77 the
pre-fix errors are in this piece's first mypy log below). Renames bind each
name exactly once; no test, output string, or exit path changes.

### lint.py — the one structural delta

Upstream line 12 is a bare `from hyperresearch.core.hooks import
SCAFFOLD_ONLY_SECTION_HEADERS`. core.hooks is Phase-2 (agent renderer), so
the bare import cannot resolve here. The port keeps a guarded import whose
ImportError fallback carries a **byte-identical copy** of the upstream
constant tuple (diffed against core/hooks.py@15010c5). When hooks lands, the
real import resumes automatically and the fallback becomes dead code.
Falsification: swapping the guard for the verbatim bare import breaks test
collection outright (`tests/test_cli/test_lint.py … ImportError:
hyperresearch.core.hooks`, "1 error during collection"); with the guard,
test_lint.py is 64/64.

### Wiring

`cli/__init__.py` now mirrors upstream registration order exactly:
setup/init/status/sync/search/fetch/fetch-batch/research/tags/show(hidden)/
dedup/archive-run/vault-tag/import/repair/watch/serve/mcp root commands;
note/graph/index/lint/export/config/topic/batch/template/git/tag sub-apps;
then profile/claims/embed/run/escalation/citecheck/levers/sources/assets/link.
**Exclusion (coordinator decision): `install` lands with P2-16**, where the
opencode renderer exists; its slot is commented at both the import site and
the registration site, and tests/test_cli/test_help_smoke.py pins that it
must NOT answer until then.

### serve.py / mcp_cmd.py

Both are **verbatim ports** — upstream already lazy-imports
`hyperresearch.serve.server` / `hyperresearch.mcp.server` inside the
handlers, so every registered verb answers --help today with zero shim text.
The missing-package consequence is deferred by design: mcp invocation prints
upstream's own "requires pip install hyperresearch[mcp]" message and exits 1
(upstream-faithful); serve invocation would raise ModuleNotFoundError after
vault discovery until P1-11 lands the package. The future-module imports are
silenced via a pyproject `[tool.mypy.overrides] ignore_missing_imports`
entry (same pattern as tavily/exa, P1-4) instead of inline ignores — inline
ignores go stale-unused the day the real packages land (this exact failure
mode had just bitten core/runs.py:482 and core/fetcher.py:184, whose stale
ignores were removed this piece).

### agent_docs + repair --docs

core/agent_docs.py ported byte-verbatim (268 lines). cli/repair.py's
documented no-op ("Already up to date") replaced with upstream's real call:
lazy `inject_agent_docs(vault.root)`, modified-paths reported in
`report["agent_docs"]`. Help text was already upstream's honest
"--docs/--no-docs Update CLAUDE.md". The P1-9 placeholder pin in
test_vault_ops.py::TestRepairCli::test_full_pipeline_report_shape now
asserts the real contract (`["CLAUDE.md (created)"]`).
Falsification: running that test against HEAD's repair.py (no-op variant)
FAILS (`assert ['CLAUDE.md (created)'] == []` → AssertionError); against the
fixed file it passes.

### Tests restored / ported / added

- Restored the P1-9 trims in tests/test_cli/test_commands.py verbatim:
  test_search_text, test_search_json_wraps_fetched_bodies_as_untrusted,
  test_lint.
- Ported upstream files we lacked, byte-verbatim: tests/test_cli/test_lint.py
  (64 tests), test_fetch_batch.py (1), test_oa_fetch.py (10). Upstream has no
  other per-group CLI files we lack (test_install_browser.py /
  test_install_profile.py belong to the deferred install piece).
- Added tests/test_cli/test_help_smoke.py (AC-7 arm): introspection pin
  (battery == registered surface, so new registrations fail loudly) +
  parametrized --help sweep over all 18 root commands (incl. hidden `show`,
  lazy `serve`/`mcp`) and all 21 sub-apps, plus the install-absence pin.
  41 tests.

### Skips activated / removed (dependencies land NOW)

Removed skips whose gates arrived with this piece:
- test_core/test_runs.py: TestRunCli class skip; test_resume_unblocks;
  test_lint_resolves_run_scoped_loci; test_lint_falls_back_to_legacy_flat_path;
  test_lint_query_files_both_layouts (5 skip sites).
- test_core/test_verification.py: 6 content-gate skips (verify_run now runs
  quote-integrity/retracted-citations for real through the landed
  cli/lint.py); TestVerificationLints class skip; citecheck/run-verify/
  run-finish CLI skips (9 sites).
- test_core/test_escalation.py: TestFetchGateIntegration,
  TestEscalationCli, TestRunStatusIntegration class skips (3).
- test_core/test_claims.py: test_claims_cli (1).
Total: 18 stale skip sites removed. test_levers.py /
test_dissertation_profile.py needed no edits — their H-2 probes
(`cli.levers_cmd` / `cli.claims_cmd`) release themselves now that the
modules exist and the app registers them. Kept, deliberately:
core.hooks installer skips (Phase-2 agent renderer) in
test_escalation.py::TestBrowserFetcherAgent and
test_verification.py, the crawl4ai-extra skips, and the P1-3
coverage-pointer skip.

### Gates at close of piece

- pytest: 791 passed, 88 skipped, 0 failed (skips = Phase-2 core.hooks,
  crawl4ai extra, coverage pointers only)
- ruff check . : All checks passed!
- mypy --strict: Success: no issues found in 86 source files
- `.venv/bin/hpr --help` + every registered verb/sub-app --help: exit 0

### Fail-closed remediation

Blind-critic wave on our tree (post-P1-10/P2-13/P1-11) named three gaps,
two shared-inherited from upstream@15010c5 (verified by diff against the
READ-ONLY reference). Files touched: `cli/lint.py`, `cli/setup.py`, their
tests only. Lint JSON schema keys (`data.issues`/`data.summary`/`count`/
`vault`) are unchanged — only `ok`/`error`/`error_code` flip when the gate
fails.

**F-1 — lint gate fail-open (shared-inherited; HIGH).** Upstream and our
port both ended `lint()` with an unconditional `success(...)` envelope: the
engine always exited 0 even with `summary.errors > 0`, so audit-gate /
quote-integrity / retracted-citations had no machine-consumable enforcement.
Fix: errors now fail closed — exit code 1 plus an `ok:false`
(`error_code="LINT_ERRORS"`) envelope whose error message names every failing
CHECK (sorted rule names); warnings/info alone stay exit 0.
Falsification (pre-fix, live run of `/tmp/opencode/falsify_f1_prefix.py`,
which seeds a vault with a hallucinated quote + a retracted citation):

```
[pre-fix] hpr lint --json EXIT CODE: 0
[pre-fix] envelope ok: True
[pre-fix] summary: {'errors': 2, 'warnings': 1, 'info': 2, 'total': 5}
[pre-fix] rules carrying severity=error: ['extract-coverage', 'quote-integrity']
```

Same probe post-fix: `EXIT CODE: 1`, `envelope ok: False`.

Ship-gate consumption trace (second half of F-1): `core/runs.py::verify_run`
imports `_check_quote_integrity`/`_check_retracted_citations` from cli.lint
in-process (:481-501) and emits each result as a check NAMED by its rule
name (`check(rule, not errors, ...)`), so a blocking detail reads
"N error(s) — first: <message>"; `finish_run` persists the failing check
NAMES into `manifest["verify"]["failed_checks"]` (:555-559) and flips status
to blocked/blocked_on=verify; `cli/run_cmd.py::run_finish` prints
`FAIL <check name>` and exits 1. The remediation keeps those two imported
symbols, their signatures, and their severity semantics byte-stable — pinned
by tests/test_core/test_verification.py::test_finish_blocks_hallucinated_quote
(asserts `by_name["quote-integrity"]["ok"] is False` and the name lands in
`failed_checks`), passing unchanged.

**F-2 — unknown `--rule` silently healthy (inherited seam; MED).**
`rules_to_run = [rule] if rule else ...` matched zero blocks for any
unrecognized name → empty issues → healthy vault, exit 0. Fix: validate
against RULES right after vault discovery; unknown name → exit 1 with an
`UNKNOWN_RULE` envelope listing all valid rules.
Falsified pre-fix by construction (no validation existed; any string was
accepted silently).

The advertised-but-unimplemented `stale-indexes` rule (upstream ships only
the RULES dict entry, grep over reference src/ confirms no engine):
CHOSEN OPTION = implement minimal semantics, because the index generation
marker already exists — `IndexGenerator._stage` stamps every generated page
with frontmatter `updated:` at build time (indexgen/generator.py:119-126),
so no convention had to be invented, and warning severity keeps the full
battery able to exit 0 (an always-error "not implemented" stub would have
made every indexed vault permanently unhealthy, contradicting F-1's
healthy-vault-exits-0 requirement). Semantics: an index page is stale when
any note file's mtime exceeds the page's generation marker; pages with a
missing/unreadable marker are flagged too (freshness unprovable ≠ healthy);
severity warning (rebuild is routine maintenance, not a gate blocker).
Pre-fix, `--rule stale-indexes` reported silent health for every input.

**F-3 — setup child-script injection (inherited verbatim from upstream
setup.py; MED).** `_create_profile_interactive` f-string-spliced
profile_name into generated python passed to
`subprocess.run([sys.executable, "-c", <source>])`. Fix: the script is now a
module constant reading `sys.argv[1]`; `_profile_create_command(name)` puts
the name in its own argv element — pure data, never parsed.
Falsification (pre-fix, `/tmp/opencode/falsify_f3_prefix.py`, extracting the
exact shipped template and interpolating hostile names):

```
[pre-fix] backslash payload: spliced child source DOES NOT EVEN PARSE
          (child crashes before crawl4ai import): unterminated string literal @ line 6
[pre-fix] quote-paren payload: spliced child source parses as VALID PYTHON
[pre-fix] statements inside async main(): ['Assign', 'Assign', 'Expr', 'Expr', 'Expr']
[pre-fix] attacker statement reached main()'s body as CODE: True
[transport] argv round-trip of hostile name -> stdout: 'x"); print("INJECTED-CODE-EXECUTION"); profiler.create_profile("y'
```

Tests added: test_lint.py +6 (gate defects exit 1 naming quote-integrity +
retracted-citations with schema keys pinned; warnings-only stays exit 0;
unknown rule exits 1 listing valid rules; stale-indexes clean-after-build /
flags-newer-note-then-clears-on-rebuild / flags-unmarked-page).
test_setup.py new file, 12 cases (child script has no `{profile_name}` hole
and parses standalone; command builder round-trips hostile names as argv[3];
argv transport delivers payloads as data; end-to-end `_create_profile_interactive`
against a stubbed crawl4ai proves quote/backslash/semicolon/`$()`/backtick
names reach create_profile intact with no injected statement executing).

### Remediation gates at close

- pytest: 917 passed, 88 skipped, 0 failed (was 791+88 at piece close; +108
  from intervening pieces' work, +18 from this remediation)
- ruff check . : All checks passed!
- mypy --strict: Success: no issues found in 89 source files

## P2-13 — opencode agent-file renderer (`core/opencode_install.py`)

Retargets the upstream Claude Code subagent installer (hooks.py
`install_hooks`, :3548) to `.opencode/agents/hyperresearch-*.md`. Roster =
16 upstream agent constants − browser-fetcher (declared non-goal, PARITY
§13) = **15**, counted from the authoritative `install_hooks` installer
tuple (:3569-3589). Prompt constants are embedded VERBATIM (upstream
hooks.py spans noted inline); bodies are never re-authored.

### Directory delta vs PARITY §13

PARITY's per-agent rows name `.opencode/agent/…` (singular); this piece
renders `.opencode/agents/…` (plural) per the P2-13 mission brief, which is
also S0-2's pre-approved standardization target ("standardize the port on ONE
directory (.opencode/agents/, the plural form used by our roster)"). Both
dirs load identically (S0-2 CONFIRMED).

### Roster (15) — class / deny-set / task allowlist / hidden

| File (`hyperresearch-*.md`) | Class | `tools:` deny-set | `permission:` denies | `task:` allowlist | `hidden` |
|---|---|---|---|---|---|
| -fetcher.md | fetch worker (RESEARCHER_AGENT) | — | — | — | true |
| -loci-analyst.md | Layer 2 | — | — | — | true |
| -depth-investigator.md | Layer 3 delegator | — | — | hyperresearch-fetcher (after `"*": deny`) | true |
| -source-analyst.md | leaf deep-read | — | — | none (leaf) | true |
| -dialectic-critic.md / -depth-critic.md / -width-critic.md / -instruction-critic.md | Layer 5 critics | — | — | — | true |
| -patcher.md | Layer 6 | `{write: false}` EXACTLY | `{write: deny}` | — | true |
| -polish-auditor.md | Layer 7 | `{write: false}` EXACTLY | `{write: deny}` | — | true |
| -readability-recommender.md | Step 16 (READABILITY_REFORMATTER_AGENT) | — | — | — | true |
| -corpus-critic.md | Layer 3.7 | — | — | — | true |
| -draft-orchestrator.md | Layer 4 | — | — | — (F-CS1 restrictive resolution) | true |
| -synthesizer.md | Step 11 | `{edit: false, bash: false}` | `{edit: deny, bash: deny}` | — | true |
| -cite-checker.md | Step 14.5 | — | — | — | true |

Decisions, each traceable:

- **Deny-sets**: S0-3 verdict table as amended by countersign F-CS2, then
  narrowed by the P2-13 mission: patcher/polish-auditor carry `tools:
  {write: false}` EXACTLY (Edit stays enabled — their job is Edit hunks);
  synthesizer carries `{edit: false, bash: false}`. The spike's extra
  `bash: false` for patcher/polish was dropped by the mission's "EXACTLY".
- **Permission denies** mirror the same sets in opencode's `permission:`
  frontmatter block form. Provenance honesty: the S0-3 transcripts prove the
  *tools*-map denial structurally (tool removed from toolset); the
  `permission:` YAML block form (`permission:\n  edit: deny`) is the agent-file
  syntax documented by opencode's own customize-opencode skill, captured at
  `evidence/spikes/S0-4-debug-skill-project-and-global.txt`. Caveat logged:
  opencode's documented permission-key list does NOT include a `write` key
  (keys: read/edit/glob/grep/list/bash/task/external_directory/...), so for
  patcher/polish-auditor the real belt is the tools map; `permission: {write:
  deny}` mirrors intent and is harmless if ignored.
- **Task allowlist**: only depth-investigator delegates upstream ("Delegate
  to `hyperresearch-fetcher` via the Task tool", hooks.py:401-404; its
  Claude frontmatter carried Task, :306). Emitted as `permission.task`
  pattern map with `"*": deny` FIRST and the allow LAST — opencode evaluates
  the LAST matching rule (documented in the captured skill text).
  draft-orchestrator gets none: its own procedure says "You don't spawn
  subagents" and countersign F-CS1 resolved the layer-comment contradiction
  restrictively. Residual risk: `task` pattern semantics are not live-proven
  by a spike, and are moot today because S0-1 proved opencode subagents get
  no task tool at all; the block encodes intended policy for the day nesting
  ships.
- **hidden: true for all 15**: every upstream description addresses an
  orchestrating pipeline step ("Use this agent in Layer N…", "Delegate to
  this agent…", "Step N …"), never the end user; S0-1 F-METHOD proved
  subagent-mode files cannot be user-invoked anyway; hidden affects
  listing/autocomplete only — opencode's own internal agents (compaction,
  title, summary) work exactly this way and remain task-spawnable.
- **model:** emitted ONLY when the role's ModelMap value is non-empty
  ([models] table > profile overlay > inherit), omitted otherwise so the
  session model inherits (P1-7 empty-inherit decision). Role mapping follows
  upstream's AGENT_FILE_MODEL_FIELD (critics share the `critics` alias;
  readability-recommender keeps its ModelMap key despite the recommender
  rename).

### Frontmatter template (emitted shape)

```markdown
---
name: hyperresearch-<role>
description: "<upstream description, single logical line>"
mode: subagent
hidden: true
model: <alias>            # OMITTED entirely when role unset in ModelMap
tools:                    # only patcher/polish-auditor/synthesizer
  <tool>: false
permission:               # denies mirror the tools set; task map for delegators
  <tool>: deny
  task:
    "*": deny
    hyperresearch-fetcher: allow
---
<!-- rendered from profile "<gear>" (hyperresearch <version>) — edit the profile or the package template, not this file -->

<upstream prompt body, byte-faithful>
```

Scalars are plain when unambiguous, JSON-double-quoted otherwise (a bare `*`
would parse as a YAML alias — keys go through the same emitter). The file is
generated deterministically; same inputs → byte-identical outputs (proven
same-process AND cross-process).

### Body fidelity + substitution fidelity

- Golden contract unchanged from P1-7: `render_prompt(constant, ctx)` ==
  frozen fixture for all 10 covered constants (new tests re-pin 3 of them:
  RESEARCHER/LOCI_ANALYST/CITE_CHECKER). The uncovered constants — SIX of
  them (16 − 10): patcher/polish-auditor/synthesizer/corpus-critic/
  draft-orchestrator AND source-analyst [count corrected by countersign
  remediation X-4; this line originally claimed "5" and omitted
  source-analyst] — ride the same code path; cite-checker additionally
  proves full installed-body equality against golden + `{hpr_path}`
  substitution. As of countersign remediation X-2 all 15 installed files
  are pinned byte-for-byte by tests/fixtures/agent_goldens_opencode/, so
  the unpinned-constant gap is closed entirely (see "### Countersign
  remediation" below).
- Per-template substitution replicates each upstream `_install_*_agent`
  helper exactly: `.format(hpr_path=posix)` for fetcher/loci/
  depth-investigator/source-analyst/dialectic/depth-critic/width-critic;
  literal `.replace("{hpr_path}", posix)` for cite-checker and
  draft-orchestrator; identity for instruction-critic/patcher/synthesizer/
  readability-recommender; `.format(scaffold_only_sections=…)` for
  polish-auditor, whose scaffold bullets come from `_render_scaffold_only_bullets(indent="- ")`
  (hooks.py:79-83 + :3864) — prepending a bullet indent to ALREADY-bulleted
  lines, so upstream-installed output carries DOUBLED `- - ` bullets.
  Replicated exactly per the replicate-quirks-verbatim doctrine
  (countersign X-1; the renderer originally normalized them to single
  bullets and failed the frozen goldens).
  Filed-not-fixed upstream quirk replicated verbatim: CORPUS_CRITIC is
  substituted with the RAW hpr_path (no POSIX normalization,
  hooks.py:3923) — Windows-only cosmetic divergence.
- **Claude-specific string deltas in bodies: NONE (count = 0).** The only
  Claude references in the upstream template range (Claude-in-Chrome MCP
  tools, hooks.py ~:3298-3250 region) live inside BROWSER_FETCHER_AGENT,
  which this piece excludes. No CLAUDE.md→AGENTS.md rewrite was needed; the
  port doctrine translation applies to AGENTS.md blurb injection (P1-10 /
  §15), not to these bodies.

### Deliberate deferrals (documented, not forgotten)

- S0-1's three-artifact degraded-mode surgery (delete the investigator's
  Task delegation prose, add a Degraded-mode clause) is NOT applied here —
  P2-13's mandate is byte-faithful bodies. The policy half lands now
  (permission.task allowlist; no Claude `tools` allowlist is reproduced);
  the prose half belongs to whichever piece owns template-level edits, and
  is inert until opencode grants nested task access anyway.
- Pruning of retired/stale agent files (`_prune_retired_agents`,
  readability-reformatter → -recommender migration) is installer-surface
  work for P2-16; `render_agents` writes exactly the 15 roster files.

### Tests

`tests/test_core/test_opencode_install.py` (22 tests): exact-count/name-shape
(a); frontmatter matrix parametrized over all 15 stems × mode/hidden/model-
omission/tools-exactness/permission-exactness (b); [models] alias flow +
unset-role omission (b2); byte determinism + idempotent re-render reporting
(c); atomicity probe — monkeypatched mid-write failure leaves only complete
files, no temp droppings, converges on next run (d); frozen-golden pins ×3 +
installed-body equality for cite-checker and patcher (e); spec-table
integrity. **Falsification pre-fix: the suite was written first and run
against HEAD without the module — collection failed with
`ModuleNotFoundError: No module named 'hyperresearch.core.opencode_install'`
(all 22 tests dead).** Two test-side defects were caught by the module during
GREEN (double-prefixed stems; body-split off-by-one) and fixed in the tests,
not papered over in the module.

### pyproject

Requirement 6 verified: no temporary mypy override entry exists for
`core.opencode_install` (the [[tool.mypy.overrides]] list covers core.hooks /
serve / mcp only) — nothing to prune. Ruff needed NO new suppression: the
prompt constants do not trip RUF001 (en/em dashes are not confusables), so
the provisional module-level noqa was removed after ruff flagged it unused.

### Gates at close of piece

- pytest (full suite): **862 passed, 88 skipped, 0 failed**
- ruff check .: All checks passed!
- mypy --strict (new module + tests): Success, no issues found in 2 files

### Countersign remediation (2026-08-23)

Countersign verifier F-CS2-fixwave returned SIGN-OFF WITH FIXES (X-1..X-4);
all four closed in this wave:

- **X-1 (MED) — polish-auditor body drift.** Upstream's installer renders the
  polish-auditor scaffold list via `_render_scaffold_only_bullets(indent="- ")`
  (hooks.py:79-83 + :3864), PREPENDING a `- ` bullet to already-bulleted
  lines, so live upstream-installed output carries DOUBLED `- - ` bullets.
  Our renderer pre-formatted single-bullet lines, silently normalizing them —
  a replicate-quirks-verbatim violation (same doctrine as the corpus-critic
  raw-path precedent). Fixed by mirroring upstream mechanics byte-exactly
  (`_render_scaffold_only_bullets` helper called with `indent="- "`).
  FALSIFICATION: probe comparing all 15 rendered bodies against LIVE
  upstream-installed bodies (installer run v0.10.0 @15010c5 into scratch
  vault /tmp/opencode/p213-refcap) FAILED pre-fix on exactly 1/15 —
  hyperresearch-polish-auditor.md, first diff at body line index 45
  (`'- \`## User Prompt (VERBATIM ...\`'` vs upstream `'- - \`## User Prompt
  (VERBATIM ...\`'`); 14/15 matched; post-fix 15/15 match.
- **X-2 (golden hole) — frozen installed-file goldens for ALL 15.** The
  builder had pinned only 9 of 15 roster constants via P1-7 template goldens;
  source-analyst was among the unpinned. Captured ALL 16 upstream-installed
  agent files ONCE by RUNNING upstream's `install_hooks` live into a scratch
  vault under /tmp/opencode/p213-refcap (reference code used read-only via
  sys.path import with our .venv python; reference clone and our package deps
  untouched). Froze tests/fixtures/agent_goldens_opencode/ — 15 fixtures
  (browser-fetcher excluded), each = opencode-frontmatter delta + provenance
  header + UPSTREAM-installed body bytes (verified byte-equal to our renderer
  output AND to the live capture at generation time). New test (f):
  render_agents output byte-compares against these fixtures for ALL 15,
  plus an inventory guard (exactly the roster filenames) and an explicit
  doubled-bullet quirk pin. The "fidelity could silently rot" hole is closed.
- **X-3 (doc) — S0-3 spike table amendment.** docs/spikes/S0-3-tool-lock.md
  final table prescribed `tools: {write: false, bash: false}` for
  patcher/polish-auditor; shipped artifact carries `{write: false}` EXACTLY
  (mission-narrowed; edit intentionally kept per corrected deny-set history).
  Dated amendment appended to the spike (history retained verbatim),
  pointing here.
- **X-4 (wording) — render_agents docstring.** Now states atomicity is
  PER-FILE (temp+rename per file; NO whole-set transaction/rollback; a
  mid-render failure leaves already-written complete files in place until a
  converging re-run). Also includes the count correction above: §Body-fidelity
  originally claimed "5 uncovered constants" omitting source-analyst — actual
  unpinned set was SIX (16 P1-7-era constants − 10 covered); corrected inline.

Gates after remediation:

- pytest (full suite): **934 passed, 88 skipped, 0 failed** (+17 vs pre-wave:
  15 parametrized golden byte-compares + inventory guard + doubled-bullet
  quirk pin)
- ruff check .: All checks passed!
- mypy --strict (core.opencode_install + its tests): Success, no issues found
  in 2 source files

## P1-11 — MCP server package (`hyperresearch.mcp`)

Ported near-verbatim from upstream v0.10.0. Sources (2 files):
`mcp/__init__.py` (byte-identical, diff-verified) and `mcp/server.py`
(near-verbatim; full delta inventory at
`evidence/p1-11/final-delta-vs-upstream.diff`, every delta marked in-source).
The module registers EXACTLY 13 tools via `@server.tool()` — search_notes,
read_note, read_many, list_notes, get_backlinks, get_hubs, vault_status,
lint_vault, check_source, list_sources, fetch_url, create_note, update_note —
proven by FastMCP's own public introspection:
`asyncio.run(server.list_tools())` returns exactly that name set
(test-pinned). Stale docstring "Exposes 8 tools" (server.py:3) KEPT verbatim —
upstream quirk documented in PARITY survey note 2; 13 tools actually ship.

### SDK dependency + import discipline (verified against the reference)

Extra spec matches upstream byte-for-byte including its rationale comment:
`mcp = ["mcp>=1.6,<2"]` (upper-bounded because mcp 2.x removed
`mcp.server.fastmcp`). Install-gate outcome on Python 3.14: mcp 1.29.0
(pure-Python wheel) was already present via the dev extra and satisfies our
bound; `.venv/bin/pip install -e ".[mcp]"` resolves cleanly
(`evidence/p1-11/pip-install-mcp-extra.txt`). Bare `pip install "mcp"` was
deliberately NOT run against the project venv — unbounded, it can upgrade
into the 2.x line upstream's own `<2` bound excludes.

Upstream imports `from mcp.server.fastmcp import FastMCP` at MODULE top
level — importing the server without the SDK crashes at import time BY
UPSTREAM DESIGN; the guard is the CLI shim, not the module. Replicated
verbatim. Proofs:

- WITH SDK: `import hyperresearch.mcp.server` OK (`server` is a
  `FastMCP` instance); `hpr mcp` launches the stdio server and exits 0 on
  stdin EOF, no traceback (only the mcp SDK's own pydantic_settings
  IncompleteFieldDefinitionWarning — third-party, py3.14 observation).
- WITHOUT SDK (genuine `--without-pip` venv): `ModuleNotFoundError: No module
  named 'mcp'` at module import.
- WITHOUT SDK via `hpr mcp`: prints upstream's exact line
  "MCP server requires: pip install hyperresearch[mcp]" to stderr, exit 1.

All hyperresearch imports stay lazy exactly as upstream, so launching needs
no vault until the first tool call. Note: `cli/mcp_cmd.py`'s delta comment
says "until P1-12 lands hyperresearch.mcp" — piece number is stale (P1-11
landed it); that file was outside this piece's ownership, and its actionable
  half (prune the pyproject override) IS done here.

### THE behavioral delta: untrusted fencing on read_note/read_many

Brief said "verify upstream does this and port faithfully". Verified — and
REFUTED: upstream `mcp/server.py` returns stored bodies RAW (no
`is_untrusted`/`wrap_body` anywhere in upstream mcp/; P1-6's exhaustive
consumer trace named only `cli/note.py::show` and `cli/search.py`). Since the
brief makes the fence an explicit acceptance criterion ("consumer engagement
point promised back in P1-6") and this repo's precedent consistently fixes
security gaps over verbatim (SSRF netguard, U-waves), the port engages the
fence at both body-emitting read tools, mirroring those consumers' call
shapes:

- `read_note`: lazy untrusted import; when `is_untrusted(source, type)`, body
  is replaced with `wrap_body(...)` and `"untrusted": true` added — same
  shape as cli/note.py::show. Trusted/local notes byte-unchanged (no key).
- `read_many`: same policy per note, guarded on truthy body like
  cli/search.py, marker set per fenced note only.

Falsification (A/B, outputs kept): the battery was written FIRST and run
against the pre-delta near-verbatim module — exactly the two fence tests
FAILED with raw unfenced bodies (34 passed; the third failure was a
test-side FK bug, fixed in-test;
`evidence/p1-11/falsification-pre-delta.txt`); post-delta all green
(`evidence/p1-11/post-delta-mcp-suite.txt`). Reverting the two marked blocks
reproduces the failures. This is the piece's ONE behavioral divergence from
upstream v0.10.0; a reviewer can veto by reverting those blocks alone.

### lint_vault delegation checked (brief vs reality)

Upstream delegates to NOTHING: `lint_vault` runs four inline SQL rule queries
over `vault.db` (missing-tags / missing-summary / broken-links / orphaned-
notes), no import from cli/lint. Kept verbatim; wiring (bound vault → issue
dicts with rule/severity/note_id/message + totals/warnings) is pinned by
tests instead.

### mypy --strict annotation deltas (zero logic changes unless stated)

| Site | Delta |
|------|-------|
| module head | TYPE_CHECKING Vault import; `_vault: Vault \| None`; `_get_vault() -> Vault` (runtime vault import stays lazy) |
| read_many | `notes, not_found = [], []` → annotated `list[dict[str, Any]]` / `list[str]` |
| list_notes | tuple-unpack split: `clauses: list[str]`, `params: list[Any]` |
| lint_vault | `issues: list[dict]` → `list[dict[str, Any]]` |
| create_note | `extra = {}` → `extra: dict[str, str]` |
| update_note | `changed: list[str]`; `meta.status = status` carries `# type: ignore[assignment]` (NoteMeta use_enum_values precedent from P1-9 note.py/repair.py) |
| read_note / read_many | payload dicts hoisted to typed locals (`data` / `note: dict[str, Any]`) — part of THE delta above |

### pyproject

Requirement: prune the temporary override entry for `hyperresearch.mcp.*` —
done; the P1-10 override block now lists only `core.hooks` + `serve.*` with
the comment updated to record the pruning. The `mcp` extra itself needed no
change (mirrored verbatim since P0-2).

### Tests (upstream ships none for mcp/ — grep-verified over reference tests/)

NEW `tests/test_mcp/{__init__,test_server.py}` — 37 tests, cover-at-landing
practice, ALL OFFLINE. Direct handler invocation against tmp vault fixtures
(the process-global `_vault` singleton is monkeypatch-bound to the fixture);
full stdio handshake / transport E2E DEFERRED TO P3 by design:

- Tool-count contract: FastMCP's own `list_tools()` == exactly the 13 names;
  every name has a callable handler.
- Read roundtrip: list_notes summaries carry no bodies; read_note full
  payload (title/status/tags/parent/body/summary); read_many splits ids and
  reports not_found; search_notes attaches bodies and converts
  SearchQueryError into "Invalid search query:" text.
- Untrusted fencing (THE delta): external-source note comes back fenced with
  `"untrusted": true`, forged inner closer neutralized to
  `-inner` sentinel with exactly one live closer at the tail; mixed
  read_many fences only the fetched note.
- Write-path guards: unknown/pathy note_id → NOT_FOUND envelope; create_note
  writes+syncs+reads back with tags normalized ("KEPT" → kept); hostile
  title "../../etc/passwd" cannot escape notes_dir (slugify strips it);
  no-op update reports changes []; status/tag edits round-trip to disk+DB.
- lint_vault wiring: flags broken-links ([[nonexistent-topic]]) +
  orphaned-notes on the seeded vault; rule filter restricts output.
- Navigation/sources: get_backlinks sources set; get_hubs inbound counts;
  vault_status totals incl. broken_links == 1; check_source miss→hit;
  list_sources ordering + domain filter.
- fetch_url offline: fetch_and_save stubbed at its lazy-import seam —
  success passthrough (tags parsed), ValueError → DUPLICATE_URL, other →
  FETCH_ERROR.
- Module-level env-conditional skip mirrors the crawl4ai pattern:
  without the mcp SDK the whole file skips with an accurate reason naming
  upstream's top-level import design.

Result: **899 passed, 88 skipped** (+37 passed / skips unchanged vs the
862p/88s baseline), ruff clean, `mypy src` strict clean (89 source files).
Raw gates: `evidence/p1-11/gate-pytest.txt`, `gate-ruff.txt`,
`gate-mypy.txt`.

### Remediation (fencing coherence)

Blind-critic remediation wave on the landed piece (five findings M-1..M-5;
scope held to `mcp/server.py` + `tests/test_mcp/test_server.py` + this
section; nothing committed). Theme: close the remaining paths by which
untrusted text or unvalidated write input crossed the tool boundary.

- **M-1 (HIGH) search_notes fenced.** The body-attach loop joined only
  `note_content.body` and emitted stored bodies RAW — the one body-emitting
  tool bypassing the fence read_note/read_many already apply. Fix mirrors
  cli/search.py's attach shape exactly: join `n.source` alongside the body,
  then per result `wrap_body(...)` + `"untrusted": true` when
  `is_untrusted(source, type)`. Trusted results stay byte-unchanged, no key.
- **M-2 (MED) get_backlinks context fenced.** `links.context` is verbatim
  source-note line text (`sync.py`: `line.strip()[:200]`), so a backlink from
  a web-fetched note smuggled attacker text unfenced. Chose WRAPPING over
  omitting snippets — wrapping IS the established policy shape (every other
  fenced consumer wraps; none omit), and nothing is lost. SELECT extended
  with `n.source, n.type`; each entry wraps + flags individually, exactly
  like read_many's per-note policy. Trusted-source entries untouched.
- **M-3 (MED) update_note status validated.** NoteMeta has
  `use_enum_values` but no `validate_assignment`, so any caller string stuck
  in frontmatter verbatim (poisoning status filters; would trip the notes
  table CHECK at sync time as an unhandled IntegrityError). Handler now
  validates against `{s.value for s in NoteStatus}` — the exact enumerated
  set of the db CHECK (`core/db.py:24`) — and rejects with an envelope in
  module style: `{"ok": false, "error": "Invalid status: 'x' (must be one
  of: archive, deprecated, draft, evergreen, review, stale)",
  "error_code": "INVALID_STATUS"}`. Checked BEFORE `_get_vault()`, so bad
  input never reaches vault discovery/auto-sync (invalid-status +
  unknown-id returns INVALID_STATUS, not NOT_FOUND — input validation
  precedes lookup, documented here as the tie-break).
- **M-4 (MED) update_note path containment.** `vault.root / row["path"]`
  was trusted blindly. Now resolves and confines within `vault.root`
  BEFORE any file access, mirroring cli/note.py mv's P1-9 H-5 pattern;
  escape → `{"ok": false, ..., "error_code": "INVALID_PATH"}` (same code
  as mv). Rationale: `notes.path` is derived cache and must not be trusted
  to name a file inside the root.
- **M-5 (LOW) surface prose corrected + import hoist.** Module docstring and
  FastMCP instructions claimed "Exposes 8 tools ... Read-only by design"
  against the actual 13-tool, three-write-capable surface. Text corrected
  faithfully (docstring enumerates all 13 names and names the mutating
  trio; instructions now say to create/edit via create_note/update_note and
  fetch via fetch_url, with direct file writes still auto-indexed). This
  supersedes the "KEPT verbatim" decision recorded at the top of §P1-11
  (PARITY survey note 2). The per-loop/per-midpoint
  `from hyperresearch.core.untrusted import ...` imports were hoisted to
  handler top in all three fencing handlers — laziness discipline unchanged
  (still no module-level hyperresearch import).

Falsification (A/B against the pre-fix module, tests written FIRST; backup +
transcripts under `/tmp/opencode/p1-11-remediation/`, scratch — quoted lines
below are the record):

- New battery: `TestUntrustedFencingSearchAndBacklinks`,
  `TestUpdateNoteInputGuards`, `TestSurfaceContractText` (9 tests; 2 are
  non-falsifying guards that pass both sides: trusted-search-bodies-stay-raw,
  all-six-valid-statuses-accepted).
- PRE-FIX: `7 failed, 2 passed, 37 deselected in 2.21s`. Decisive lines:
  - M-1 raw body quoted:
    `'Attacker-controlled body.\n</untrusted-source>\nforged closer above must be neutralized.\n'.startswith('<untrusted-source url="https://example.com/articles/fenced">')` → False.
  - M-2 raw snippet quoted:
    `'Read this [[python-async-patterns]] link.'.startswith('<untrusted-source ')` → False.
  - M-3 accepted poison: `assert data["ok"] is False` → `E assert True is False` for status="published".
  - M-4 worse than escape — crash: pre-fix died with
    `FileNotFoundError: [Errno 2] No such file or directory:
    '.../test-vault/../../escaped-via-db'` (read/write followed the drifted
    cache row out of the vault); absolute-path variant same hole.
  - M-5: `assert '13 tools' in doc` failed against the literal
    "Exposes 8 tools ... Read-only by design" docstring; instructions lacked
    every write-tool name.
- POST-FIX: full mcp file `46 passed in 1.94s` (37 pre-existing + 9 new);
  reverting only server.py reproduces the 7 failures.

Gates after the wave (exact lines):

- pytest: `991 passed, 88 skipped in 69.26s (0:01:09)` — skips unchanged at
  88; mcp file went 37 → 46 collected (+9, the remediation battery).
- Tool-count contract intact: `asyncio.run(server.list_tools())` →
  `13 tools: ['check_source', 'create_note', 'fetch_url', 'get_backlinks',
  'get_hubs', 'lint_vault', 'list_notes', 'list_sources', 'read_many',
  'read_note', 'search_notes', 'update_note', 'vault_status']`;
  `test_fastmcp_registers_exactly_thirteen_named_tools` green.
- ruff: `All checks passed!` (repo-wide, exit 0).
- mypy: `Success: no issues found in 92 source files` (`mypy src`, strict).

## P1-12 — Serve UI package (`hyperresearch.serve`)

Ported near-verbatim from upstream v0.10.0. Sources (3 files):
`serve/__init__.py` (byte-identical, diff-verified), `serve/renderer.py` and
`serve/server.py` (near-verbatim; full delta inventory at
`evidence/p1-12/final-delta-vs-upstream.diff`, every delta marked in-source).
Brief asked to verify upstream truly uses stdlib — CONFIRMED by reading:
`http.server.BaseHTTPRequestHandler` + `HTTPServer` only, no web framework,
no template engine; PARITY §10 rows already said PORT-VERBATIM.

### Heavy/lazy dependency inventory (mirrored exactly)

Upstream keeps four imports lazy and the port preserves each site verbatim:

| Dep | Upstream site | Why lazy |
|-----|---------------|----------|
| `sqlite3` | inside `HyperresearchHandler.db` property | first request opens the vault DB connection (cached on the class) |
| `signal`, `sys` | inside `run_server` | serve-only runtime |
| `webbrowser` | inside `run_server` (--open branch) | GUI environments only |
| `hyperresearch.search.fts` | inside `_serve_search` | search lane only |

With the package landed, the P1-10 shim resolves for real:
`cli/serve.py::serve` → `run_server(vault, ...)` verified end-to-end with a
scratch vault under /tmp/opencode — index route 200 (`text/html;
charset=utf-8`), note route 200, `/api/graph` JSON correct, unknown route 404,
SIGINT prints "Stopped." and exits cleanly. Transcript:
`evidence/p1-12/manual-serve-transcript.txt`. Note: cli/serve.py's delta
comment still says "until P1-11 lands hyperresearch.serve" — piece number is
stale (P1-12 landed it); that file is outside this piece's ownership and its
actionable half (prune the pyproject override) IS done here (same situation
as cli/mcp_cmd.py after P1-11).

### Module map (routes → handlers)

| Route | Handler | Emits |
|-------|---------|-------|
| `/` or `` | `_serve_index` | all-notes list (id/title/summary escaped) |
| `/note/<id>` | `_serve_note` (unquote → parametrized SQL) | meta chips + render_markdown body + backlinks |
| `/tag/<tag>` | `_serve_tag` (unquote → parametrized SQL) | tag listing |
| `/tags` | `_serve_tags` | tag cloud with counts |
| `/search?q=` | `_serve_search` | reflected query + FTS results w/ `<mark>` snippets |
| `/graph` | `_serve_graph` | canvas page + GRAPH_JS |
| `/api/graph` | `_serve_graph_api` | nodes/edges JSON |
| anything else | inline 404 branch of `do_GET` | `<h1>Not Found</h1>` |
| `run_server(vault, port, open_browser)` | binds 127.0.0.1, SIGINT-serviced handle_request loop | process lifecycle |

### XSS audit — every interpolation point probed, not trusted

Method: crafted a vault whose note title/body/tags/summary carry
`<script>alert(...)`, `<img src=x onerror=...>`, `javascript:` href/src, a
quote-smuggling attribute breakout (`x" onmouseover="alert(5)`), hostile
wiki-link target AND display, plus the unterminated-tag snippet bait; fetched
every rendered route over real sockets (ephemeral port) and asserted raw
markup absent / entity forms present. Battery: `tests/test_serve/
test_server.py::TestXssBattery`. Findings:

| # | Interpolation site | Data source | Verdict |
|---|--------------------|-------------|---------|
| 1 | `_send` `<title>{title}` | callers | safe — every caller passes literal or `html_mod.escape()`d value |
| 2 | nav brand-sub / recent links | config name, DB id+title | safe — escaped |
| 3 | index rows | DB id/title/summary | safe — escaped |
| 4 | note 404 reflection | URL path | safe — escaped |
| 5 | note tags href+label | DB tags | safe — escaped both positions |
| 6 | note backlinks | DB source_id/title | safe — escaped |
| 7 | tag/tags pages h1/href/label | URL + DB | safe — escaped |
| 8 | search h1/title/error/results | URL query + FTS | safe — escaped; snippet is escape-BEFORE-marker-substitution so `<mark>`/`</mark>` are the only live markup (upstream's own #72 fix, now proven end-to-end over HTTP) |
| 9 | renderer `_link`/`_image` href/src | body markdown URLs | safe — whole-body `html.escape(body)` runs BEFORE pattern matching (quotes arrive as `&quot;`, cannot close the attribute) AND `_is_safe_url` scheme allowlist rejects `javascript:`/`data:` incl. entity-encoded (`&#106;avascript:`), control-split (`java\tscript:`) and NUL forms |
| 10 | renderer wiki-links target/display | body | safe — targets/display cut from already-escaped text; href is always `/note/…`-prefixed so no scheme can be injected |
| 11 | graph API titles | DB | safe — `json.dumps` under `application/json`; canvas draws text via `fillText`, no HTML parsing |
| 12 | note `class="status {status_class}"` | DB status | **NOT injectable — probed**: tool flows validate via NoteMeta StrEnum, and the SCHEMA ITSELF carries `CHECK (status IN ('draft',…,'archive'))` (core/db.py:24), so even direct SQL tampering is refused (`sqlite3.IntegrityError`). Kept upstream-verbatim with an in-source audit note; pinned permanently by `TestDbTamperSinks::test_hostile_status_is_refused_by_schema_even_under_direct_sql` |
| 13 | note `{row["word_count"]}` words | DB word_count | **WAS INJECTABLE — FIXED in-port** (see below) |

#### Inherited defect fixed: raw `word_count` sink (the one behavioral delta)

Unlike `status`, `word_count INTEGER` has NO check constraint, and SQLite's
INTEGER affinity stores non-numeric text VERBATIM — so crafted DB bytes reach
the raw f-string interpolation. Reachability argument: vault directories are
git repositories and `.hyperresearch/hyperresearch.db` ships with them (no
ignore rule anywhere in either tree), making another writer's rows this UI's
input; the same trust-boundary logic the repo applied in the SSRF waves.
Fix: escape at the sink — `html_mod.escape(str(row["word_count"]))`; legal
ints render byte-identically.
Falsification (`evidence/p1-12/falsification-wordcount-sink.txt`): with the
line reverted to upstream-verbatim, direct-DB payload `'3"><script>
alert(13)</script>'` is reflected LIVE into the note page
(`<span>3"><script>alert(13)</script> words</span>` — test fails pre-fix);
with the fix, entities only. Regression test:
`test_hostile_db_word_count_rendered_inert`.

TWINS: searched serve/ for other raw row-data f-string interpolations after
the fix — found 2 surviving raw sites, both dispositioned: `status_class`
(finding 12 above, schema-CHECK-guarded) and int-only counters
(`{len(rows)}`, `{len(results)}`, COUNT(*) `{r["c"]}` — not string-typed).

#### Filed observations (verified, NOT defects — upstream-faithful)

- Protocol-relative URLs (`//cdn.example.com/x.png`) pass `_is_safe_url` by
  design (documented in-code: no scheme); loads remote images but executes
  nothing — privacy trade-off upstream chose, kept.
- No `do_HEAD`: HEAD requests get stdlib's 501. Quirk, kept verbatim.
- Renderer code-block restore contains a dead `html.escape(block)` call
  (result discarded) and double-escapes block content (block was captured
  post-escape, then `html.escape(code_content)` runs again). Cosmetic mojibake
  for `<`&co inside fenced code only; preserved byte-verbatim.
- Single-threaded `HTTPServer` + per-class cached connection: fine for the
  localhost single-user design point; no auth by design (127.0.0.1 bind).

### mypy --strict annotation deltas (zero logic changes except §word_count)

| Site | Delta |
|------|-------|
| renderer module head | `from collections.abc import Callable`; explicit `MD_PATTERNS: list[tuple[re.Pattern[str], str \| Callable[[re.Match[str]], str]]]` (strict mode cannot join str/lambda tuple element types) |
| renderer locals | inner `save_code_block`/`replace_wiki_link` params annotated; `code_blocks`/`table_lines`/`result_lines`/`rows` given `list[str]` |
| server module head | `TYPE_CHECKING`-guarded sqlite3/Vault imports (annotation-only; runtime sqlite3 stays lazy inside `db` exactly as upstream); `Any` import |
| server class attrs | `vault: Vault \| None = None`, `_db: sqlite3.Connection \| None = None` (runtime defaults still plain None) |
| `db` property / `_build_nav` | narrowing asserts `vault is not None` (annotation-era precedent); `db -> sqlite3.Connection` |
| server methods | `-> None` returns throughout; `_send` signature split across lines (same defaults/order); `_send_json(data: dict[str, Any])`; `log_message(format: str, *args: Any)`; `inbound_counts: dict[str, int]`; `edges` comprehension typed |
| `run_server` | `(vault: Vault, port: int = 8080, open_browser: bool = False) -> None`; `_shutdown(sig: int, frame: object) -> None` |

### pyproject

Requirement: prune the temporary `hyperresearch.serve.*` mypy override — done;
the P1-10 block now lists only `hyperresearch.core.hooks` with its comment
updated to record both prunes (mcp P1-11, serve P1-12). cli/serve.py needed
no edit (its import resolves for real now).

### Tests

- `tests/test_serve/{__init__,test_xss}.py`: byte-identical copies of
  upstream's shipped serve tests (diff-verified) — 23 tests.
- NEW `tests/test_serve/test_server.py` — 25 tests, cover-at-landing practice
  (upstream ships NO server-level tests): real `HTTPServer` on ephemeral
  ports, never a fixed port. Route smoke ×10 (`/`, ``, `/tags`, `/graph`,
  `/api/graph`, search variants, note, tag, index-content), 404 behavior ×2
  (unknown route; hostile missing-note-id reflected escaped),
  content-types ×2 (`text/html; charset=utf-8`, `application/json`),
  XSS battery ×7 (note page/nav/tags/tag-page/search-reflection/snippet-
  markers/backlinks), DB-tamper sinks ×2 (schema-CHECK pin + word_count
  regression), lazy-db pin + bind-conflict `OSError` ×2. All offline except
  loopback sockets.

Result: **982 passed, 88 skipped, 0 failed** (+48 vs the 934p/88s baseline =
exactly the 23 upstream + 25 new serve tests), ruff clean ("All checks
passed!"), mypy strict clean ("Success: no issues found in 92 source files",
was 89). Raw gates: `evidence/p1-12/gate-{pytest,ruff,mypy}.txt`.

### Hardening (r2 named gap)

Three findings closed post-landing; dispositions below supersede the §XSS-audit
entries they overlap (rows 12, the TWINS note, and the dead-call "preserved
byte-verbatim" bullet above — history left in place, this section wins).

- **Y-1 (MED) — `status_class` interpolated RAW into `class="status {…}"`
  (server.py `_serve_note`, was finding 12).** The StrEnum + schema-CHECK
  argument was correct for normal writes (re-pinned by
  `TestDbTamperSinks::test_hostile_status_is_refused_by_schema_even_under_direct_sql`)
  but defense in depth moved the last guard to the sink:
  `status_class = html_mod.escape(row["status"])` before the class
  interpolation — identical treatment to the word_count sink. Legal enum
  values render byte-identically (`class="status evergreen"` pinned).
  Honest test construction: since neither normal nor direct-SQL writes can
  store a hostile status, the regression builds the hostile input AT THE
  SINK BOUNDARY through the seam the code actually exposes — a proxy over
  the handler's cached connection swaps the note-page SELECT's result row
  for a crafted mapping carrying
  `'evergreen" onload="alert(21)"><script>alert(20)</script>'` (equivalent
  to rendering a committed DB whose notes table lacks the CHECK; all other
  columns come from the real row, nav/tags/backlinks still hit the real DB).
  Falsified pre-fix over real HTTP: page contained
  `class="status evergreen" onload="alert(21)"><script>alert(20)</script>`
  live. Post-fix: entities only inside the attribute. Regression:
  `tests/test_serve/test_r2_hardening.py::TestStatusSinkEscape`.
- **Y-2 (FUNCTIONAL, shared inherited) — markdown images never rendered**
  (renderer.py `MD_PATTERNS`): the link pattern ran BEFORE the image
  pattern, so `![alt](url)` was consumed as literal `!` +
  `[alt](url)` → `!<a href="url">alt</a>`. Fixed by running the image
  pattern first (patterns are disjoint on the leading `!`; `[text](url)`
  still renders `<a>`). `_image` already routed src through `_is_safe_url`
  but was unreachable for real markdown; now exercised: `javascript:`,
  case-mixed, leading-whitespace, control-split (`java\tscript:`),
  `data:` and `vbscript:` srcs drop the tag and keep alt as text;
  entity-encoded (`&#106;avascript:`) and control-split forms pinned at the
  img gate directly. Falsified pre-fix ×8 (every safe-image probe produced
  `!<a …>`, incl. end-to-end note-page over HTTP); green post-fix.
  Regressions: `TestImageRendering` (20 tests) + e2e.
- **Y-3 (TRIVIAL) — dead discarded `html.escape(block)` call removed**
  (renderer.py code-block restore loop; the real escape at the f-string's
  `{html.escape(code_content)}` remains). No other change; code-block tests
  unchanged.

New tests: `tests/test_serve/test_r2_hardening.py` — 22 tests (kept out of
the byte-identical upstream copies in `test_xss.py`; stale link-before-image
comment in `test_server.py` updated to the fixed behavior).

#### Stays filed (verified, NOT fixed — recorded dispositions)

- **No CSP / X-Content-Type-Options / Content-Length headers**: stdlib
  BaseHTTPRequestHandler emits none; adding them is a design delta beyond
  port fidelity, and the localhost single-user bind (127.0.0.1, no auth)
  makes them hardening nice-to-haves rather than gap-closers. Filed.
- **`<title>` escaped at callers, not at the `<title>{title}` sink**
  (`_send`): every current caller passes a literal or an escaped value
  (finding 1). This is a caller-discipline invariant — new callers MUST
  escape; a sink-level escape would be redundant-but-safe and stays filed
  for a future hardening wave.
- **Protocol-relative URLs (`//host/img`) allowed by `_is_safe_url`
  design**: documented in-code (no scheme → True); loads remote content,
  executes nothing — upstream's chosen privacy trade-off, unchanged.

Gates after r2: `.venv/bin/python -m pytest` → **1013 passed, 88 skipped,
0 failed** (991p pre-r2 baseline + exactly the 22 new tests);
`.venv/bin/python -m ruff check .` → "All checks passed!";
`.venv/bin/python -m mypy src` → "Success: no issues found in 92 source
files". Falsification (pre-fix, same suite): **9 failed, 13 passed** —
8× image-ordering failures (`!<a href="…">pic</a>` instead of `<img …>`)
+ 1× status breakout failure (raw `" onload="` + live `<script>` in page).

## P2-14 — opencode skill/command renderer + AGENTS.md injection (`core/opencode_skills.py`)

Ports the upstream Claude Code skill installers (hooks.py
`_install_hyperresearch_skill` :4076-4094 + `_install_hyperresearch_step_skills`
:4119-4178) to the S0-4-proven opencode layout
`.opencode/skills/<name>/SKILL.md`, plus the `/hyperresearch` custom command at
`.opencode/commands/hyperresearch.md` and the ops-blurb injection into
`AGENTS.md`. Pipeline per file mirrors upstream `_render_installed` (:42-49):
profile-render → **opencode deltas** (new; upstream has none) → degraded-mode
clause (new) → provenance header after frontmatter. Bodies are otherwise
byte-faithful to the bundled sources, which are byte-identical to the pinned
reference `src/hyperresearch/skills/*.md` (verified by directory diff at piece
close).

### Inventory reconciliation (plan said "exactly 18")

Upstream ships **19** skill markdowns = the entry ROUTER `hyperresearch` +
**18 step files** (16 integer steps + hyphenated half-steps
`hyperresearch-1-5-chapter-partition` and `hyperresearch-14-5-cite-check`).
The plan's 18 matches the STEP count with the router counted separately; this
renderer ships all 19 rather than inventing an exclusion. Names all satisfy
`^[a-z0-9]+(-[a-z0-9]+)*$`; render order is hooks.py :4097-4116 verbatim
(router first). PARITY.md §12 records the same 19-file split.

### Frontmatter delta: NONE (count = 0)

Upstream skills already emit exactly `name` + `description` — precisely the
fields opencode recognizes as meaningful for skills (S0-4 probe +
opencode's own customize skill captured in
`evidence/spikes/S0-4-debug-skill-project-and-global.txt`: name required and
must match its folder; description effectively required; optional
license/compatibility/metadata; unknown fields ignored). Tests pin
`set(meta) ⊆ {name, description, license, compatibility, metadata}` on all 19,
falsifying any future frontmatter "enrichment".

### Body deltas — every changed line (58 − / 58 + across 19 files)

(Countersign R-2 correction: the header previously said "57 across 18
files". The 18 was the step-file count with the ROUTER excluded out of
habit — mechanically all 19 rendered skills carry ≥1 delta, the router's
15 pairs included, the same split as the inventory reconciliation above.
Pair total refreshed for the countersign R-1 fix below: the new :31 pair,
and the :87 pair's + side gained the invoke conversion within the same
changed line.)

Mechanical rules (exact-string replacements + one regex), applied AFTER the
profile render. An independent replay of just these rules over the rendered
sources reproduces the renderer's output byte-for-byte for all 19 skills
(audit run at piece close) — i.e. **no undocumented mutation exists**.
Occurrence census:

| Rule | Old → New | Files hit (×count) |
|---|---|---|
| D1 regex | ``Skill(skill: "X")`` → ``skill({ name: "X" })`` | 18 files ×25 total (router×5, 10-triple-draft×3, 2-width-sweep×2, rest ×1; none in 16-readability-audit) — post-R1-fix census (was ×23, router×3) |
| D1b | `Skill tool` → `skill tool` | 16 step files ×1 each (every step except hyperresearch-3-contradiction-graph and hyperresearch-12-critics) |
| D1c | `` `Skill` tool `` → `` `skill` tool `` | router ×3 |
| D1d | `invoke a Skill,` → `invoke a skill,` | router ×1 |
| D2a | `every Task call` → `every task tool call` | router ×1 |
| D2b | `a Task prompt` → `a task prompt` | router ×1 |
| D2c | `Task result` → `task result` | 14-patcher ×2 |
| D2d | `both Task calls` → `both task tool calls` | 4-loci-analysis ×1 |
| D2e | `all Task calls` → `all task tool calls` | 5-depth-investigation ×1 |
| D3 | `TodoWrite` → `todowrite` | router ×2 |
| D4a | `-p` mode / `end_turn` sentence | 2-width-sweep ×1 |
| D4b | long-form `-p`/`end_turn` sentence | router ×1 |
| D4c | `non-interactive (`-p`) runs` | 2-width-sweep ×1 |
| D5 | `.claude/skills/hyperresearch-1-decompose/SKILL.md` → `.opencode/...` | router ×1 |
| D6a | Claude-in-Chrome unavailability note → deferred-lane statement | 2-width-sweep ×1 |
| D6b | "you drive ... Chrome" → would-drive + NOT-installed clause | 2-width-sweep ×1 |
| D6c | Step 2.8 drain sentence → queue-accumulates reality | router ×1 |

The complete machine-generated line-level diff (every −/+ pair with source
line numbers, 57 pairs) is reproduced below verbatim from the audit run:

<details><summary>hyperresearch</summary>

```text
    19 - `3. Invoke each step skill in sequence via the `Skill` tool.`
    19 + `3. Invoke each step skill in sequence via the `skill` tool.`
    31 - `Skill(skill: "hyperresearch-N-stepname")`
    31 + `skill({ name: "hyperresearch-N-stepname" })`
    34 - `When you invoke a Skill, that skill's full procedure is loaded into your context **fresh**. You then execute that step's procedure, hit its exit criterion, and return to the entry skill (this file) to invoke the next step.`
    34 + `When you invoke a skill, that skill's full procedure is loaded into your context **fresh**. You then execute that step's procedure, hit its exit criterion, and return to the entry skill (this file) to invoke the next step.`
    87 - `   - **Step-skills check.** If `.claude/skills/hyperresearch-1-decompose/SKILL.md` doesn't exist relative to the working directory, run `hyperresearch install --steps-only . --json`. Installs the 16 step skill files needed by `Skill(skill: "hyperresearch-N-...")` calls in later steps.`
    87 + `   - **Step-skills check.** If `.opencode/skills/hyperresearch-1-decompose/SKILL.md` doesn't exist relative to the working directory, run `hyperresearch install --steps-only . --json`. Installs the 16 step skill files needed by `skill({ name: "hyperresearch-N-..." })` calls in later steps.`
   133 - `6. **Seed the TodoWrite list.** Create todos for all 16 step skill invocations using the integer step numbers, e.g.:`
   133 + `6. **Seed the todowrite list.** Create todos for all 16 step skill invocations using the integer step numbers, e.g.:`
   140 - `7. **Invoke step 1:** `Skill(skill: "hyperresearch-1-decompose")`.`
   140 + `7. **Invoke step 1:** `skill({ name: "hyperresearch-1-decompose" })`.`
   148 - `1. **NEVER EMIT BARE TEXT WHILE TASKS ARE RUNNING.** In non-interactive (`-p`) mode, a text-only response (no tool call) triggers `end_turn` — the process exits and the pipeline dies. Every response while subagent tasks are in flight MUST include a tool call. The best one is appending analytical thoughts to `research/runs/<vault_tag>/temp/orchestrator-notes.md`. Vault count checks at most once per minute.`
   148 + `1. **NEVER EMIT BARE TEXT WHILE TASKS ARE RUNNING.** In non-interactive (`opencode run`) mode, a text-only response (no tool call) ends the session — the process exits and the pipeline dies. Every response while subagent tasks are in flight MUST include a tool call. The best one is appending analytical thoughts to `research/runs/<vault_tag>/temp/orchestrator-notes.md`. Vault count checks at most once per minute.`
   160 - `Blocked fetches (login walls, bot walls, captchas) are queued, not lost: `$HPR escalation list --status queued --tag <vault_tag> -j`. Step 2.8 drains the queue via ONE `hyperresearch-browser-fetcher` subagent driving the user's real Chrome browser. Two standing rules:`
   160 + `Blocked fetches (login walls, bot walls, captchas) are queued, not lost: `$HPR escalation list --status queued --tag <vault_tag> -j`. Step 2.8 drains the queue via ONE `hyperresearch-browser-fetcher` subagent driving the user's real Chrome browser. In this opencode port that agent is NOT installed (deferred lane): the queue accumulates instead of draining, and the fallback rule below is the standing behavior. Two standing rules:`
   165 - `## Subagent spawn contract (applies to every Task call)`
   165 + `## Subagent spawn contract (applies to every task tool call)`
   177 - `Skipping any of these in a Task prompt is a process violation.`
   177 + `Skipping any of these in a task prompt is a process violation.`
   186 - `1. **Check the TodoWrite list.** It carries integer step numbers and survives compaction.`
   186 + `1. **Check the todowrite list.** It carries integer step numbers and survives compaction.`
   205 - `4. **Re-invoke this entry skill** if you've lost track entirely: `Skill(skill: "hyperresearch")`. It loads fresh.`
   205 + `4. **Re-invoke this entry skill** if you've lost track entirely: `skill({ name: "hyperresearch" })`. It loads fresh.`
   273 - `V8 makes re-reading structural. Each step skill is loaded fresh via the `Skill` tool at the moment it's needed. The procedure is in context exactly when it matters. Compaction can evict an old step's procedure — that's fine, the orchestrator never needs it again because each step is self-contained and reads its inputs from disk.`
   273 + `V8 makes re-reading structural. Each step skill is loaded fresh via the `skill` tool at the moment it's needed. The procedure is in context exactly when it matters. Compaction can evict an old step's procedure — that's fine, the orchestrator never needs it again because each step is self-contained and reads its inputs from disk.`
   275 - `The trade: 16 skill files instead of 1, plus 16 invocations of the `Skill` tool over the run. The cost is negligible; the reliability gain is the difference between Q57 (55.9, full pipeline) and Q9 (52.6, single-draft fallback).`
   275 + `The trade: 16 skill files instead of 1, plus 16 invocations of the `skill` tool over the run. The cost is negligible; the reliability gain is the difference between Q57 (55.9, full pipeline) and Q9 (52.6, single-draft fallback).`
   284 - `Skill(skill: "hyperresearch-1-decompose")`
   284 + `skill({ name: "hyperresearch-1-decompose" })`
```
</details>

<details><summary>hyperresearch-1-decompose</summary>

```text
     9 - `  Skill tool from the entry skill (hyperresearch).`
      9 + `  skill tool from the entry skill (hyperresearch).`
   208 - `Skill(skill: "hyperresearch-2-width-sweep")`
   208 + `skill({ name: "hyperresearch-2-width-sweep" })`
```
</details>

<details><summary>hyperresearch-1-5-chapter-partition</summary>

```text
    10 - `  is (0, 0). Invoked via Skill tool from the entry skill.`
    10 + `  is (0, 0). Invoked via skill tool from the entry skill.`
    93 - `Return to the entry skill and begin the chapter execution loop at step 2 for the first chapter(s): `Skill(skill: "hyperresearch-2-width-sweep")`.`
    93 + `Return to the entry skill and begin the chapter execution loop at step 2 for the first chapter(s): `skill({ name: "hyperresearch-2-width-sweep" })`.`
```
</details>

<details><summary>hyperresearch-2-width-sweep</summary>

```text
     8 - `  and source count gating. Invoked via Skill tool from the entry skill`
     8 + `  and source count gating. Invoked via skill tool from the entry skill`
   159 - `**CRITICAL: never emit bare text while waiting.** In `-p` mode, a text-only response triggers `end_turn`.`
   159 + `**CRITICAL: never emit bare text while waiting.** In non-interactive (`opencode run`) mode, a text-only response ends the run.`
   261 - `  you drive the user's real Chrome browser to fetch them. After you`
   261 + `  you would drive the user's real Chrome browser to fetch them. In this opencode port the browser-fetcher agent is NOT installed (deferred lane), so this spawn never fires — the queue drains per the fallback rule below. After you`
   276 - `2. In non-interactive (`-p`) runs where no user can answer: record `$HPR run block <vault_tag> --on human-challenges -j` and CONTINUE the pipeline with everything else — the queue drains on the next `hpr run resume`.`
   276 + `2. In non-interactive (`opencode run`) sessions where no user can answer: record `$HPR run block <vault_tag> --on human-challenges -j` and CONTINUE the pipeline with everything else — the queue drains on the next `hpr run resume`.`
   279 - `**If the Claude-in-Chrome extension is unavailable**, the queue simply accumulates — report the queued count in your wave summary and move on. Abandoned/queued items are exactly the pre-4.0 status quo (lost sources), never worse.`
   279 + `**If the browser-fetcher lane is unavailable (it always is in this opencode port — the Claude-in-Chrome automation stack was deferred)**, the queue simply accumulates — report the queued count in your wave summary and move on. Abandoned/queued items are exactly the pre-4.0 status quo (lost sources), never worse.`
   343 - `- **light tier:** Skip directly to step 10 — invoke `Skill(skill: "hyperresearch-10-triple-draft")` (light tier writes a single draft, not the ensemble)`
   343 + `- **light tier:** Skip directly to step 10 — invoke `skill({ name: "hyperresearch-10-triple-draft" })` (light tier writes a single draft, not the ensemble)`
   344 - `- **full tier:** Invoke `Skill(skill: "hyperresearch-3-contradiction-graph")``
   344 + `- **full tier:** Invoke `skill({ name: "hyperresearch-3-contradiction-graph" })``
```
</details>

<details><summary>hyperresearch-3-contradiction-graph</summary>

```text
    73 - `- **full tier:** Invoke `Skill(skill: "hyperresearch-4-loci-analysis")``
    73 + `- **full tier:** Invoke `skill({ name: "hyperresearch-4-loci-analysis" })``
```
</details>

<details><summary>hyperresearch-4-loci-analysis</summary>

```text
     8 - `  then allocates source budgets dynamically. Invoked via Skill tool from`
     8 + `  then allocates source budgets dynamically. Invoked via skill tool from`
    34 - `1. **Spawn 2 `hyperresearch-loci-analyst` subagents in parallel** (ONE message, both Task calls). Both read the same width corpus but return independently.`
    34 + `1. **Spawn 2 `hyperresearch-loci-analyst` subagents in parallel** (ONE message, both task tool calls). Both read the same width corpus but return independently.`
   133 - `Skill(skill: "hyperresearch-5-depth-investigation")`
   133 + `skill({ name: "hyperresearch-5-depth-investigation" })`
```
</details>

<details><summary>hyperresearch-5-depth-investigation</summary>

```text
     8 - `  within their source_budget. Invoked via Skill tool from the entry`
     8 + `  within their source_budget. Invoked via skill tool from the entry`
    32 - `1. **Spawn K `hyperresearch-depth-investigator` subagents in parallel** (ONE message, all Task calls). One per locus with `source_budget > 0`, capped at 6.`
    32 + `1. **Spawn K `hyperresearch-depth-investigator` subagents in parallel** (ONE message, all task tool calls). One per locus with `source_budget > 0`, capped at 6.`
   110 - `Skill(skill: "hyperresearch-6-cross-locus-reconcile")`
   110 + `skill({ name: "hyperresearch-6-cross-locus-reconcile" })`
```
</details>

<details><summary>hyperresearch-6-cross-locus-reconcile</summary>

```text
     8 - `  Invoked via Skill tool from the entry skill (full tier only).`
     8 + `  Invoked via skill tool from the entry skill (full tier only).`
    81 - `Skill(skill: "hyperresearch-7-source-tensions")`
    81 + `skill({ name: "hyperresearch-7-source-tensions" })`
```
</details>

<details><summary>hyperresearch-7-source-tensions</summary>

```text
     9 - `  highest-leverage move for insight scores. Invoked via Skill tool from`
     9 + `  highest-leverage move for insight scores. Invoked via skill tool from`
   100 - `Skill(skill: "hyperresearch-8-corpus-critic")`
   100 + `skill({ name: "hyperresearch-8-corpus-critic" })`
```
</details>

<details><summary>hyperresearch-8-corpus-critic</summary>

```text
     9 - `  Invoked via Skill tool from the entry skill (full tier only).`
     9 + `  Invoked via skill tool from the entry skill (full tier only).`
   139 - `Skill(skill: "hyperresearch-9-evidence-digest")`
   139 + `skill({ name: "hyperresearch-9-evidence-digest" })`
```
</details>

<details><summary>hyperresearch-9-evidence-digest</summary>

```text
     8 - `  fidelity than fetcher summaries). Invoked via Skill tool from the`
     8 + `  fidelity than fetcher summaries). Invoked via skill tool from the`
    80 - `Skill(skill: "hyperresearch-10-triple-draft")`
    80 + `skill({ name: "hyperresearch-10-triple-draft" })`
```
</details>

<details><summary>hyperresearch-10-triple-draft</summary>

```text
    11 - `  skips ahead to step 15 (polish). Invoked via Skill tool.`
    11 + `  skips ahead to step 15 (polish). Invoked via skill tool.`
    76 - `5. **Exit and route.** Once `research/notes/final_report_<vault_tag>.md` is written, return to the entry skill and invoke `Skill(skill: "hyperresearch-15-polish")`. Light tier skips steps 11–14 entirely.`
    76 + `5. **Exit and route.** Once `research/notes/final_report_<vault_tag>.md` is written, return to the entry skill and invoke `skill({ name: "hyperresearch-15-polish" })`. Light tier skips steps 11–14 entirely.`
   225 - `- **light tier:** You already wrote `research/notes/final_report_<vault_tag>.md` directly. Skip steps 11-14 (no synthesis, no critics, no patcher) and invoke `Skill(skill: "hyperresearch-15-polish")`.`
   225 + `- **light tier:** You already wrote `research/notes/final_report_<vault_tag>.md` directly. Skip steps 11-14 (no synthesis, no critics, no patcher) and invoke `skill({ name: "hyperresearch-15-polish" })`.`
   226 - `- **full tier:** Invoke `Skill(skill: "hyperresearch-11-synthesize")`.`
   226 + `- **full tier:** Invoke `skill({ name: "hyperresearch-11-synthesize" })`.`
```
</details>

<details><summary>hyperresearch-11-synthesize</summary>

```text
    10 - `  via Skill tool from the entry skill (full tier).`
    10 + `  via skill tool from the entry skill (full tier).`
   260 - `Skill(skill: "hyperresearch-12-critics")`
   260 + `skill({ name: "hyperresearch-12-critics" })`
```
</details>

<details><summary>hyperresearch-12-critics</summary>

```text
    78 - `Skill(skill: "hyperresearch-13-gap-fetch")`
    78 + `skill({ name: "hyperresearch-13-gap-fetch" })`
```
</details>

<details><summary>hyperresearch-13-gap-fetch</summary>

```text
     8 - `  patcher has ammunition. Capped at 5 gaps. Invoked via Skill tool from`
     8 + `  patcher has ammunition. Capped at 5 gaps. Invoked via skill tool from`
    93 - `Skill(skill: "hyperresearch-14-patcher")`
    93 + `skill({ name: "hyperresearch-14-patcher" })`
```
</details>

<details><summary>hyperresearch-14-patcher</summary>

```text
     9 - `  via Skill tool from the entry skill (full tier).`
     9 + `  via skill tool from the entry skill (full tier).`
   118 - `- **Is the patch log still the empty stub?** If yes, the patcher failed to log — its Task result will contain the real log inline. Read the Task result, parse out the JSON, and write it to `research/runs/<vault_tag>/patch-log.json` yourself via Bash so downstream lint rules see it.`
   118 + `- **Is the patch log still the empty stub?** If yes, the patcher failed to log — its task result will contain the real log inline. Read the task result, parse out the JSON, and write it to `research/runs/<vault_tag>/patch-log.json` yourself via Bash so downstream lint rules see it.`
   157 - `Skill(skill: "hyperresearch-14-5-cite-check")`
   157 + `skill({ name: "hyperresearch-14-5-cite-check" })`
```
</details>

<details><summary>hyperresearch-14-5-cite-check</summary>

```text
    10 - `  15 (polish sees the corrected text). Invoked via Skill tool.`
    10 + `  15 (polish sees the corrected text). Invoked via skill tool.`
    97 - `Return to the entry skill and invoke `Skill(skill: "hyperresearch-15-polish")`.`
    97 + `Return to the entry skill and invoke `skill({ name: "hyperresearch-15-polish" })`.`
```
</details>

<details><summary>hyperresearch-15-polish</summary>

```text
     9 - `  Invoked via Skill tool from the entry skill. Followed by step 16`
     9 + `  Invoked via skill tool from the entry skill. Followed by step 16`
   163 - `Skill(skill: "hyperresearch-16-readability-audit")`
   163 + `skill({ name: "hyperresearch-16-readability-audit" })`
```
</details>

<details><summary>hyperresearch-16-readability-audit</summary>

```text
    12 - `  Invoked via Skill tool from the entry skill.`
    12 + `  Invoked via skill tool from the entry skill.`
```
</details>

Beyond the delta pass, installed bytes differ from raw upstream bodies ONLY by
the provenance header stamped after frontmatter (same P2-13 mechanic, mirrors
upstream `_render_installed`). Frontmatter passes through untouched.

### Degraded mode (spike S0-1 semantics)

S0-1 REFUTED nested delegation in opencode: a spawned subagent gets NO task
tool, so any second-hop spawn in a spawned role's procedure cannot fire. The
accurate level-1-only semantics are carried by an explicit `## Degraded mode`
clause appended to every skill whose UPSTREAM text instructs spawning
(mechanical detector: source contains `subagent_type:` or `spawn a subagent`;
exactly **13** = router + 12 step files). The clause states: level-1 spawns
into `.opencode/agents/` work as written; the depth-investigator →
fetcher hop degrades to investigators calling `$HPR fetch-batch` directly,
preserving batch economics and honoring per-locus `source_budget`.
Adversarial sweep of the six NON-spawning skills (1-decompose,
1-5-chapter-partition, 3-contradiction-graph, 6-cross-locus-reconcile,
7-source-tensions, 9-evidence-digest) found only DESCRIPTIVE mentions of other
steps' spawns — no clause there, pinned by negative-arm tests.

### Replicated upstream quirks

- Upstream's skill installer never substitutes `{hpr_path}`, so installed
  skills carry the literal string (hyperresearch-8-corpus-critic.md:39).
  Replicated byte-exactly; test pins it.
- Router prose says "the 16 step skills"/"Installs the 16 step skill files"
  while installing 18 (stale docstring, hooks.py :4080/:4120). Replicated
  verbatim.

### Command file

`.opencode/commands/hyperresearch.md` (COMMAND_NAME `hyperresearch`):
frontmatter `description`, body invokes the router via
`skill({ name: "hyperresearch" })` and passes the query through `$ARGUMENTS`.
Format per opencode's documented command loader (markdown named after the
command; body = template with `$ARGUMENTS` replaced by everything typed after
the command) — evidenced in the captured customize-opencode skill inside the
S0-4 transcript.

### AGENTS.md injection

Port of upstream agent_docs.py `inject_agent_docs`/`_inject_into_file`
(CLAUDE.md variant) retargeted at AGENTS.md. The blurb constant is upstream's
HYPERRESEARCH_BLURB **byte-identical** (verified against the reference module
at piece close); markers `<!-- hyperresearch:start -->` /
`<!-- hyperresearch:end -->`. The ONLY prose changes are five exact-string
edits applied at injection time (each raises if its target disappears):

- E1: `.claude/skills/hyperresearch/SKILL.md` → `.opencode/skills/...`
- E2: "via the `Skill` tool" → "via opencode's native `skill` tool"
- E3: browser-fetcher drain sentence → escalation queue waits (lane not
  installed in this port)
- E4: roster enumeration drops browser-fetcher ("the browser-fetcher lane is
  deferred in this port")
- E5: spawn-contract noun "every Task call" → "every task tool call"

Semantics: missing file → created (`# AGENTS.md` header + section); no marker
→ appended preserving all existing bytes; marker present → section replaced in
place; returns True iff bytes changed, so re-running an up-to-date injection
is a no-op diff (False). Unpaired markers raise. All mission-required sections
(untrusted-content policy, OA-substitution disclosure, academic-APIs-first,
curation doctrine) survive verbatim and are pinned by tests.

### API surface for P2-16

`render_skills(target_dir/skills, profile) -> SkillManifest(written, unchanged)`
· `render_command(target_dir/commands) -> Path` ·
`inject_agents_md(path, hpr_path="hyperresearch") -> bool changed`.
Deterministic bytes (proven cross-tree); per-file atomic writes via the shared
P2-13 temp+`os.replace` plumbing; re-runs rewrite nothing when byte-identical.
No CLI wiring here (P2-16 owns the install verb); profiles.py untouched.

### Tests

`tests/test_core/test_opencode_skills.py` (~40 tests): inventory count/order/
name-shape/bundled-set (a); frontmatter allowed-fields matrix ×19 (b); P1-7
raw-render goldens ×8 re-pinned against `golden_prompts/skills/` (c); frozen
installed-file goldens ×19 byte-compared vs `tests/fixtures/skill_goldens/`
(captured ONCE from this renderer over the byte-verbatim bundled sources)
+ inventory guard + `{hpr_path}` quirk pin (d); determinism/idempotence/
atomicity probes (mid-write failure leaves only complete files, no temp
droppings, converges on re-run); degraded set == 13 + presence/absence ×19 +
fallback-name + budget-tail + literal-heading pins (e); command shape +
idempotent no-rewrite tripwire (f); AGENTS.md create/append/replace/preserve/
unpaired-marker/custom-hpr + idempotency (g). Countersign remediation added
group (h) — invoke-syntax conversion ×22 (unit + chain-wide + census); see
"### Countersign remediation" below.

Falsification record (fresh probes at piece close, module perturbed then
byte-restored each time):

- Golden fixture perturbed (+1 trailing line) →
  `test_installed_file_byte_matches_frozen_skill_golden[hyperresearch]` FAILS
  (byte-compare bites).
- Undocumented mutation injected into the delta pass (regex replacement
  extended) → 17 parametrized golden tests FAIL (no room for undocumented
  edits).
- `$HPR fetch-batch` removed from the clause → degraded-clause tests FAIL
  across all 13 spawning skills.
- Clause heading renamed (`## Degraded mode` → `## Degraded fallback`) →
  originally GREEN — a real hole (test compared against the imported constant
  itself); CLOSED by adding a literal `"## Degraded mode"` pin, after which
  the same perturbation FAILS. This was the one falsification-found defect of
  the piece, fixed test-side.
- Historical: the suite was written before the module existed; first run died
  at collection (ImportError), recorded in the test-module docstring.

### Gates at close of piece

- pytest (full suite): **1114 passed, 106 skipped, 0 failed**
- ruff check .: All checks passed!
- mypy --strict src: Success, no issues found in 94 source files

### Countersign remediation (three LOW findings closed)

**R-1 — `_SKILL_INVOKE_RE` left the router's placeholder references as
literal Claude syntax.** The frozen charclass
`Skill\(skill: "([a-z0-9-]+)"\)` converted all 23 concrete invocations but
NOT the two uppercase-`N` placeholder forms in the ROUTER: hyphens were
never the problem — the uppercase `N` and the dots of `...` fall outside
`[a-z0-9-]`. Falsified pre-fix by rendering the whole chain through the real
pipeline (`render_prompt` → `_apply_deltas`): sources carry 25
`Skill(skill:` occurrences; exactly 2 survived unconverted, both in
`hyperresearch.md` —

```text
hyperresearch.md L31: Skill(skill: "hyperresearch-N-stepname")
hyperresearch.md L87: ... needed by `Skill(skill: "hyperresearch-N-...")` calls in later steps.
```

Fix: payload widened to `([^"]+)` — every well-formed quoted reference
converts regardless of shape; `[^"]+` ends at the closing quote and
requires the trailing `")`, so it cannot over-match. Post-fix census:
0 Claude-syntax occurrences across all 19 rendered skills; 25 conversions
(router ×5). Regression tests added to `test_opencode_skills.py` group (h):
unit arm enumerating placeholder + concrete + future-shaped refs against
`_apply_deltas`; ×19 parametrized no-Claude-syntax-survives +
target-is-chain-member check; exact verbatim pins for both router
placeholders; whole-chain census pinned at 25 with the terminal
16-readability-audit pinned invoke-free.

Golden regeneration: `tests/fixtures/skill_goldens/hyperresearch.md` ONLY —
two lines (:31 and :87 above) now carry opencode syntax. Regeneration
reason: renderer output changed by design via the widened D1 rule; all 18
other goldens verified byte-identical under the new pattern before
regenerating (mechanical diff), and the regeneration itself is
byte-idempotent on re-render.

**R-2 — delta-table header undercounted files ("across 18 files").**
Corrected to **19**: mechanically every one of the 19 rendered skills
carries ≥1 body delta — the details blocks in this section already showed
19 summaries; "18" was the step-file count habitually excluding the ROUTER,
the same split as the inventory reconciliation above. Header pair total
refreshed for R-1 while there: 57 → 58 line-pairs (router 14 → 15 — the new
:31 pair; :87's existing pair absorbed the conversion on its + side); D1
occurrence census 23 → 25.

**R-3 — skip reason named a half that already landed.** `test_prompt_golden.py`'s
module skip said "until core.hooks + the skills package land", but the
skills half HAS landed — its goldens are re-pinned active by
`test_opencode_skills.py` items (c)/(d). Reworded to name only the genuinely
missing half: core.hooks is the Claude installer superseded wholesale by
this opencode renderer; the module stays staged until the P2-16 install
verb wires these goldens into end-to-end rendering. Skip STATE unchanged
(still gated on the `core.hooks` import probe); wording only.

Remediation gates (post-fix, full suite):

- pytest (full suite): **1153 passed, 106 skipped, 0 failed** (= this tree's
  pre-wave baseline 1131 + exactly the 22 new group-(h) tests; skip count
  unchanged — no skip state flipped)
- ruff check .: All checks passed!
- mypy --strict src: Success, no issues found

Post-close addendum (two countersign micro-findings):

- Z-1: `cli/run_cmd.py` printed the dead Claude invocation form as `run
  resume` guidance; converted to the opencode form (`skill({ name: ... })`),
  and the zero-Claude-syntax boundary is EXTENDED repo-wide — enforced by
  `test_no_claude_invoke_syntax_anywhere_outside_the_converter` over all of
  `src/hyperresearch`, with only the `skills/` source templates (converted at
  render time) and the converter module itself sanctioned to carry it.
- Z-2: injected AGENTS.md lands world-readable (0644) via an opt-in `mode=`
  parameter on `_atomic_write` (chmod-before-rename); every other atomic
  write keeps the historical owner-only 0600.

## P2-17 — Smoke gear profile overlay (mechanics-proving E2E runs, ~10 min)

Port-only addition to `core/profiles.py`; no CLI/installer changes. Mission:
a first-class "smoke" GEAR whose numbers make one full pass over the pipeline
mechanics in ~10 minutes — source_target (8, 12), planned_searches (6, 12),
loci_max 2, draft_count 3, word envelope (800, 1500).

### Upstream reconciliation

Upstream v0.10.0 ships NO smoke-like profile (grep across upstream
`core/profiles.py` + tests: nothing). Its lightest built-in, `light`, is a
run-time TIER — upstream's own `GEAR_PROFILES` comment excludes it from gear
duty because installing it would bake tier numbers into the flat pipeline.
So there was no upstream naming to preserve; `smoke` follows the pipeline's
plain-English scale vocabulary. Construction is upstream's own built-in
pattern applied exactly:

1. `_SMOKE = {**_FULL, ...}` spread-and-override, identical mechanics to
   upstream's `_LIGHT`/`_PREMIER` definitions.
2. Registered in `BUILTIN_PROFILES` in ascending scale order (first entry),
   so `list_profiles()` → ["smoke", "light", "full", "premier",
   "dissertation"] and `hpr profile list` ordering stays scale-ascending.
3. Added to `GEAR_PROFILES = ("smoke", "full", "premier")`: smoke IS a gear —
   its entire job is baking toy numbers into rendered prompts. This makes it
   legal for `hpr profile use smoke` with zero CLI edits (profile_cmd only
   hard-rejects the two tiers by name) and selectable via
   `hpr run --profile smoke`.
4. Merge/validation semantics are untouched upstream machinery: built-in name
   resolves base := BUILTIN_PROFILES[name], then user `[profile.smoke]` keys
   win per key; user profiles may `extends = "smoke"` (extends accepts any
   BUILTIN_PROFILES member); every value passes the same Profile validators
   (`_range_ordered`, `_dict_ranges_ordered`, `_knobs_non_negative`,
   `_steps_valid`) that gate overlays.

### Values (pinned by mission; rest scaled coherently)

Pinned exactly: source_target (8, 12), planned_searches (6, 12), loci_max 2,
draft_count 3, word_targets {short/structured/argumentative: all (800, 1500)}.
Everything else follows premier's coherence rule inverted (shrinking only the
fetch targets would strand candidates, claims, and word counts at full scale):
width funnel (source_min 5, candidate_urls (12, 18), deduped_urls (10, 15),
batch_size (4, 6), batch_count (1, 2), waves (1, 2), wave1_fetchers (2, 3),
wave2/3 (1, 2), adversarial_searches_min 2, fetcher_chase (1, 2)/cap 2,
source_analyst_cap 3); depth (loci_analysts 1, depth_budget_total 6, brackets
((30,3),(20,2),(10,1),(0,1)), investigator_max 2, depth_default_budget 2);
tensions/critic (all (1,2)-ish, tension_survey (4, 6)); evidence funnel
(claims_cap (12, 20), claims_min 5, single_draft_reads (3, 5), must_read
(3–5)/(4–6)/(5–8), citation_totals uniform (16, 30) — consistent with the
inherited citation_density_min 2.0 at 800–1500 words; char_targets_no_word_
boundary uniform (2400, 4500), keeping _FULL's ~3x CJK editorial ratio);
critics/gap-fetch/readability (caps 4/4/3/5, gap_fetch_cap 2,
readability_rec_cap 10); pacing (vault_check_interval_s 30,
time_estimate "~10 min").

Deliberate non-deltas vs the light tier (documented in-source): steps stay
1–16 (E2E means every mechanic runs once; light routes (1, 2, 10, 15, 16));
utility_scoring stays ON (light turns it off only because its tier never
reaches score-consuming steps; smoke reaches all of them). chapters stays
(0, 0) unchaptered; models stays empty-inherit.

### Selection plumbing, proven end-to-end

The chain exercised by
`TestSmokeGear.test_selection_plumbing_end_to_end` (offline, tmp vault):

    config.toml ([profile.smoke] overlay) ─┐
    "smoke" as selected name ──────────────┴→ runs.init_run(profile="smoke")
      → resolve_profile(name, vault.config_path) → manifest{profile,
        profile_steps=1..16} + validated knobs (user overlay wins per key)
    AND build_render_context(config_path, primary="smoke")
      → render_prompt(RESEARCHER_AGENT)  [the REAL bundled agent template]
      → "select the **1-2 most" / "**2 additional primary sources**" baked
        into the prompt body; full's "select the **3-8 most" absent; the same
        template under primary="full" renders full's numbers.

So one test proves both consumption paths from the module docstring: run-time
resolution (init_run/manifest) and install-time prompt templating.

### Tests

`tests/test_core/test_profiles.py`: new `TestSmokeGear` (7 tests): exact
overlay values; raw-table validation through the same Profile model;
inverted-range rejection on a smoke overlay (validators not vacuous at toy
scale); merge precedence (user keys beat smoke defaults, untouched keys keep
smoke values); `extends = "smoke"` micro-profiles; lighter-than-light scale
comparison (with the two honest overlaps: pinned planned_searches (6, 12)
overlaps light's (8, 20) ceiling-wise, wave1_fetchers high equals light's low
— assertions pin ceilings/lows accordingly); plus the integration test above.
Two registry pins updated for the new builtin: `test_list_builtins` and
`test_gear_profiles_are_valid_builtins` (now ("smoke", "full", "premier")).

Falsification record (fresh probes at piece close; module perturbed then
byte-restored each time, sha256 re-verified):

- `_SMOKE["source_target"]` perturbed (8, 12) → (8, 13) → 4 TestSmokeGear
  tests FAIL (exact-values, raw-validation, merge-precedence untouched-key
  assert, integration leg) — exact-value pins bite.
- `"smoke"` removed from `GEAR_PROFILES` →
  `test_gear_profiles_are_valid_builtins` FAILS — gear registration pin bites.
- `_SMOKE["fetcher_chase"]` perturbed (1, 2) → (3, 8) → integration test
  FAILS on `assert "select the **1-2 most" in smoke_prompt` — the render leg
  genuinely tracks profile content, not template text.

Known-stale prose left for later pieces (out of P2-17 scope, no functional
effect): `core/agent_docs.py` gear prose and the `hpr profile use` help text
still say "<full|premier>" — they predate smoke and live outside this piece's
file scope; the skipped `TestProfileCli` block restores verbatim with PARITY
§15 and needs no edit for smoke (its assertions check membership, not
exhaustiveness).

### Gates at close of piece

- pytest (full suite): **1121 passed, 106 skipped, 0 failed** (baseline 1114
  passed + the 7 new TestSmokeGear tests)
- ruff check .: All checks passed!
- mypy --strict src: Success, no issues found in 94 source files

## P2-15 — opencode lockdown plugin, layer 2 of the tool-lock belt-and-braces (`core/opencode_plugin.py`)

Ships the canonical JavaScript opencode plugin that HARD-denies (throws in
`tool.execute.before`) the tools each locked roster agent must never reach,
even when layer 1 (the P2-13 frontmatter locks) is absent or regressed.
S0-3 proved both mechanisms produce real denials on this opencode (1.18.21);
this piece productizes the second belt as a data-driven template in the
Python package so P2-16's installer can materialize it.

### Deny matrix (single source: `PLUGIN_DENY_MATRIX`, mirrored into the JS as strict JSON)

| Agent | Denied tools | Open by design |
|---|---|---|
| hyperresearch-patcher | write | edit + bash (they run `hpr` commands; edit hunks are the job) |
| hyperresearch-polish-auditor | write | edit + bash |
| hyperresearch-synthesizer | edit + bash | write (fresh-write mandate) |

Exactly `AGENT_SPECS[*].tools_deny` (P2-13, F-CS2-amended S0-3 verdict).
Unknown agents are untouched by design — targeted backstop, not a sandbox.
The Python mirror is pinned against AGENT_SPECS-derived expectations AND
against the emitted JS table parsed back out of `PLUGIN_SOURCE`
(json.loads over the `Object.freeze({...})` literal) — string-grep pins rot,
parse pins don't.

### Mechanism (the hook input has NO agent field)

The bundled type package (`@opencode-ai/plugin/dist/index.d.ts`) gives
`tool.execute.before` only `{tool, sessionID, callID}`. The plugin therefore
records every `chat.params` input (`{sessionID, agent, ...}` — fired for each
LLM request) into a sessionID→agent map and consults it at deny time. This
works for primary sessions AND task-spawned child sessions — proven live:
all matrix denials below fired inside CHILD sessions spawned via the task
tool from a relay driver, with the error naming the child agent.

### Directory spelling — BOTH load; installer standardizes on PLURAL

Probed live with two sibling scratch projects identical except for the
plugin dir (agent files at the S0-2-proven `.opencode/agents/` in both):

- `.opencode/plugins/hyperresearch-lockdown.js` → denial FIRED
  (`evidence/p2-15/p215-dirspell-plural.txt`: `✗ Write out.txt failed`,
  `DENIED_BY_PLUGIN …`, file absent);
- `.opencode/plugin/hyperresearch-lockdown.js` → denial ALSO FIRED
  (`evidence/p2-15/p215-dirspell-singular.txt`, same shape; each tree held
  ONLY its own copy).

Verdict: on 1.18.21 dropped files load from EITHER spelling. The installer
(P2-16) uses `.opencode/plugins/` (plural): consistent with the S0-2 roster
standardization and the S0-3b precedent; `PLUGIN_SUBDIR = "plugins"` records
it. Side observation: opencode materialized `.opencode/node_modules/` in the
probe project when loading the dropped plugin (harmless; not replicated).

### LIVE matrix probe — acceptance standard met (8/8 cells)

Production-real path per cell: `opencode run --agent p215-driver` → task-tool
spawn → `mode: subagent`+`hidden: true` stand-in named exactly like the roster
agent, carrying NO frontmatter locks (the plugin is the only belt under test)
— one file per probe under `evidence/p2-15/`, each with command, exit,
stdout/stderr, filesystem ground truth, mechanical verdict line:

| Cell (transcript `p215-matrix-<cell>.txt`) | Attempt | Verdict |
|---|---|---|
| patcher-write | write → out.txt | **DENIED** — `✗ Write out.txt failed`, DENIED_BY_PLUGIN, file absent |
| patcher-edit | edit alpha→bravo | **ALLOWED** — pre.txt == bravo |
| patcher-bash | bash echo sentinel | **ALLOWED** — sentinel contains BASH_RAN |
| polish-write | write → out.txt | **DENIED** — DENIED_BY_PLUGIN, file absent |
| polish-edit | edit alpha→bravo | **ALLOWED** — pre.txt == bravo |
| synth-edit | edit alpha→bravo | **DENIED** — DENIED_BY_PLUGIN tool 'edit', pre.txt unchanged |
| synth-bash | bash echo sentinel | **DENIED** — DENIED_BY_PLUGIN tool 'bash', sentinel absent |
| synth-write | write → out.txt | **ALLOWED** — out.txt == hello |

Every DENIED cell's throw names agent + tool (`DENIED_BY_PLUGIN: tool '<t>'
is hard-denied for agent '<a>' by hyperresearch-lockdown.js (layer 2)`), so
layer-2 evidence greps uniquely vs layer-1 structural absences. Harness +
runner archived at `evidence/p2-15/harness/`. Honest flakes encountered and
resolved (both were HARNESS bugs / model flakes, never plugin failures):
(1) runner v1 checked wrong fs paths and pre-created no run dirs — one bash
cell "failed" because shell redirection hit a missing dir (which itself
proves patcher's bash EXECUTED); (2) an empty pre.txt from a `tee >a >b`
redirect mistake made polish-edit fail honestly ("Could not find oldString");
(3) one driver flake answered without invoking the task tool — caught by fs
ground truth (file untouched), retried with a MANDATORY-task-first prompt and
denied correctly. Falsification record for tests: suite run before the module
existed fails at collection with ModuleNotFoundError
(`evidence/p2-15/falsification-pre-module.txt`).

### API (for P2-16)

`write_plugin(plugins_dir: Path) -> PluginManifest` installs
`PLUGIN_FILENAME = "hyperresearch-lockdown.js"` atomically (temp + os.replace,
reusing `_atomic_write`), skipping byte-identical files (written/unchanged
manifest). `render_plugin() -> str` returns the deterministic bytes;
`PLUGIN_SOURCE` is the frozen constant; `PLUGIN_SUBDIR = "plugins"` records
the proven spelling. No timestamps, no environment reads.

### Residual risk

- Mechanism depends on `chat.params` carrying the active agent name — pinned
  by observation on 1.18.21; re-probe after any opencode major bump (same
  caveat as S0-3's hook-shape pin).
- A session that somehow issues a tool call before its first chat.params
  would bypass the map lookup (no known path: params precede every LLM
  request, and tools are only callable after one).
- Plugin throws surface to the model as errors it could narrate around; that
  is exactly the layer-1 gap layer 2 closes for MISCONFIGURED agents, while
  correct installs never reach these tools at all (S0-3 a1/c1 shape).

### Gates at close of piece

- pytest (full suite): **1131 passed, 106 skipped, 0 failed** (baseline 1121
  passed + the 10 new test_opencode_plugin tests)
- ruff check .: All checks passed!
- mypy --strict src: Success, no issues found in 95 source files
  (94 + this module)

## P2-16 addendum — `profile use` retargeted to opencode renderers; hooks dependency retired from CLI paths

Live E2E caught `hpr profile use <gear>` crashing
`ModuleNotFoundError: No module named 'hyperresearch.core.hooks'`
(`src/hyperresearch/cli/profile_cmd.py:160`, inside `profile_use`): the verb
still invoked upstream's Claude installer (`core/hooks.py` `install_hooks`,
pinned reference 15010c5) even though that module never landed and never will
— its job was absorbed by the opencode renderers (§P2-13 /
`core/opencode_install.py`, §P2-14 / `core/opencode_skills.py`).

Retargeted behavior (`cli/profile_cmd.py` only):

- Agents: `core.opencode_install.render_agents` into
  `<vault.root>/.opencode/agents`, called exactly like `hpr install` does —
  resolved profile + its ModelMap (`profile.models`) + `_resolve_executable()`.
- Skills: `core.opencode_skills.render_skills` into `.opencode/skills`.
- Plugin: gear-independent by construction (no baked knobs), deliberately NOT
  re-rendered — proven byte+mtime-stable across a gear switch in tests.
- Output contract preserved: same envelope keys
  (gear/description/sources/time_estimate/rerendered), where `rerendered` now
  carries manifest-style counts
  `{"agents": {"written": N, "unchanged": M}, "skills": {...}}`; human output
  keeps the "Gear switched:" line ("re-rendered <N+M> skill/agent file(s)").
  A render failure exits cleanly via an INSTALL_ERROR envelope instead of a
  traceback. Stale delta comment about the pyproject mypy override removed.

Sweep of the remaining CLI hooks references:

- `cli/setup.py:124` — the import was function-level lazy, but the
  *interactive TTY* execute path still called `install_hooks` unguarded (the
  non-TTY / `--json` path delegates to `hpr install`, which is why E2E never
  hit it). Guarded degrade applied: import+call wrapped, missing-module path
  prints a dim pointer to `hpr install`. `hpr setup --help` verified rc=0.
- `cli/lint.py:25` — already try/except-guarded; left alone.

Falsification record (pinned in `tests/test_cli/test_install.py::TestProfileUseVerb`):
pre-fix, `from hyperresearch.core.hooks import install_hooks` raises
ModuleNotFoundError (the falsifier test executes that exact statement and pins
its message) while the post-fix verb completes end-to-end on a real install;
integration test proves full→smoke re-bakes knob strings ("At most 12
findings." → "At most 4 findings.", "~10 min"), keeps skill bytes stable +
mtime-frozen on a same-gear re-render (all-unchanged manifest), persists
`profile = "smoke"` in config.toml, and `profile use does-not-exist` still
fails UNKNOWN_PROFILE with zero mutation. Gates at close:
pytest **1179 passed, 106 skipped, 0 failed**; ruff check .: All checks
passed!; mypy --strict src: Success, no issues found in 96 source files.

Residual cosmetics (outside this wave's file allowlist): the
`hyperresearch.core.hooks` mypy override in `pyproject.toml` is now dead
config, and the `tests/test_core/test_verification.py` skip reason still says
the hooks installer "lands with the Phase-2 agent renderer piece" — both can
be pruned in a hygiene pass.

## Phase 3 evidence notes (verifier-dossier caveats closed)
- Spend $0.00 of $5.00 cap in BOTH live E2Es is NON-INSTRUMENTATION, not budget enforcement:
  fetcher/drafter agents never invoked `hpr run spend`, so estimated_usd stayed at its
  initial value. On subscription billing upstream documents --budget as a value measure,
  not a bill; the ceiling mechanism itself is gate-tested (crossing flips run to blocked).
- Smoke-tier per-DRAFT word counts (~5.2k–6k words each) exceeded the 800–1500
  word_targets envelope; word_targets bind the FINAL report format on this tier, and the
  ship-gate length-in-range check passed on both E2E finals. Per-draft targets were
  therefore advisory under the smoke gear in practice — recorded here so nobody reads
  them as enforced.

## P4-A — `parallel` named web provider (api.parallel.ai) (2026-08-24)

New EXTRA web source; nothing replaced or demoted — builtin stays the
default floor provider, tavily/exa/crawl4ai keep their get_provider branches
verbatim, crawl4ai stays optional. `src/hyperresearch/web/parallel_provider.py`
implements the WebProvider protocol (`web/base.py`): fetch -> POST /v1/extract
as a single-URL batch with `advanced_settings.full_content` (chunked <=20 URLs
for fetch_many, per-result ExtractError partial failures recorded on
`last_extract_errors` without failing the batch); search -> POST /v1/search
(objective=query, search_queries=[query], mode from config, excerpt sizing to
fit WebResult). Auth is spec-literal `x-api-key` from PARALLEL_API_KEY env
(ctor override allowed); missing key raises ParallelAuthError at CALL time,
never at import/construction. Responses map faithfully into WebResult
(url/title/content; publish_date -> metadata["published_date"]; provider
stamped "parallel"). SSRF guard runs before any request. The Parallel error
envelope parses into ParallelApiError(status_code); malformed-200 becomes
ParallelApiError(200). Deltas vs sibling providers, documented in-file:
no pip-extra ImportError hint (httpx is already a core dep), typed
auth/error exceptions shared with the P4-B chain. Blind gauntlet r1 ACCEPT;
5 low dispositions fixed same session (spec-literal header, malformed-200
guard, fetch_many dedupe, ref_id in envelope message, negative
authorization-header assert). Tests: tests/test_web/test_parallel_provider.py,
zero network via httpx MockTransport + factory seams.

## P4-B — ordered provider fallback chain (2026-08-24)

`[web] provider` now accepts a single name OR an ordered list, e.g.
`provider = ["parallel", "builtin"]`: try in order; fall through ONLY on
transport errors, HTTP 5xx/429, missing-auth config errors, and junk/empty
results — 4xx schema errors and plain RuntimeErrors SURFACE (no masking).
ONE shared helper `resolve_web_provider` (web/base.py) resolves every call
site — cli/fetch.py, cli/fetch_batch.py (both waves), cli/research.py,
core/fetcher.py, and later cli/search_web.py — so behavior cannot drift;
whichever candidate serves is recorded in the sources table `provider`
column exactly as before. Typed signals: ProviderAuthError base (P4-A's
ParallelAuthError subclasses it); construction-time failures always fall
through while an all-fail chain re-raises the identical last error.
Documented limitation: SDK-wrapped 5xx (tavily/exa) surfaces rather than
falls through — fail-visible, never guessed. Backward compat: plain string
behaves identically to the old get_provider path; default stays "builtin".
Config: coerce_web_provider validates str|list[str] incl. JSON-quoted-scalar
rejection; parse/serialize round-trips byte-stably through _toml_value;
config show/set verbs know the key. Blind gauntlet r1 ACCEPT (fresh-context
judge); linchpin ParallelAuthError<ProviderAuthError verified post-verdict
at parallel_provider.py:55 with pin test test_provider_chain.py:373.
Tests: tests/test_web/test_provider_chain.py +
tests/test_core/test_config_chain.py; fetch-batch seam retargeted to
resolve_web_provider with assertions byte-identical.

## P4-C — agent-visible Parallel search lane (`hpr search-web` + gated template sentence) (2026-08-24)

Opt-in lane that makes the Parallel search visible to pipeline AGENTS without
letting a search write to the vault. Three surfaces, one flag:

- **Flag** — `[web] parallel_search_lane` (default `false`) in
  `.hyperresearch/config.toml`, field `web_parallel_search_lane` on
  `VaultConfig` (parse: `web.get("parallel_search_lane")`; serialize:
  `_toml_value` bool branch, so save->load round-trips). `config set/get/show`
  know the key; `set` is STRICT for this key (true/1/yes, false/0/no) — any
  other spelling exits 1 with no partial write. Deliberate delta vs the
  legacy bool keys (`web.magic`, `sync.auto_sync`, ...), which silently map
  unrecognized spellings to False: a typo'd lane flag must fail loudly,
  because a silently-disabled lane looks identical to no lane at all.

- **Verb** — `hpr search-web <query...> [--provider NAME] [-n MAX] [-j]`
  (new module `cli/search_web.py`, registered after `fetch-batch`). Joins the
  positional words, resolves ONE provider through the shared P4-B helper
  `resolve_web_provider` (`--provider` overrides `[web] provider` as a single
  string; chains flow through unmolested), calls
  `prov.search(query, max_results=n)` (default n=5), and prints an ok
  envelope whose `data` is a list of `{url, title, content, provider}` rows —
  `provider` from the result's own metadata stamp (chain-aware post-call
  name as fallback), plus `metadata` ONLY when non-empty. NO note writes, NO
  sources rows, not even `auto_sync()`. Flag off => LANE_DISABLED envelope,
  exit 1, with the exact enable text (`hpr config set
  web.parallel_search_lane true` + re-run `hpr install`). Provider failures
  surface as SEARCH_ERROR exit 1; unknown provider names fail up front
  inside the resolver (P4-B semantics), before any network. The verb takes
  `[--profile NAME]` following install's resolution convention (explicit >
  `[pipeline] profile` gear > "full"); an unknown name exits UNKNOWN_PROFILE
  and any other ProfileError (e.g. invalid overlay type) exits PROFILE_ERROR,
  discriminated by list-membership, never message-sniffing. EMPTY_QUERY is
  evaluated AFTER the lane gate — deliberate, documented trade-off so the
  disabled-lane message always wins in an off-vault.

- **Conditional template sentences** — TWO role-scoped constants (skill:
  `_WIDTH_SWEEP_LANE_SENTENCE` in `core/opencode_skills.py`; agent:
  `PARALLEL_SEARCH_LANE_SENTENCE` in `core/opencode_install.py`), injected
  into their gated render targets only when the installer derives
  `parallel_lane=true` from the EFFECTIVE flag (see the per-profile bullet
  below). Final wording after blind-gauntlet rounds r1-r4 (see history
  below) — width-sweep (orchestrator context, `$HPR` literal per its own
  file's convention — NOT the corpus-critic `{hpr_path}` accident, which is
  byte-replication of bundled sources only and licenses no new prose):

  > **Parallel search lane:** when `[web] parallel_search_lane` (or your
  > profile) is enabled, ALSO run one additional `$HPR search-web <atomic
  > item keywords> --provider parallel -j` query per atomic item alongside
  > native search and academic APIs; treat hits as extra URL candidates and
  > fetch them through the normal fetch path.

  fetcher agent (scout-and-report; `{hpr_path}` substituted via the existing
  prep path; exclusivity scoped to candidate-discovery so Phase-2 WebSearch
  for assigned targets stays outside the clause):

  > **Parallel search lane:** when `[web] parallel_search_lane` (or your
  > profile) enables it, ALSO run one `PYTHONIOENCODING=utf-8 {hpr_path}
  > search-web <keywords from your assignment> --provider parallel -j` query
  > up front, then LIST any newly surfaced candidate URLs in your report
  > WITHOUT fetching them — the orchestrator dedups, scores, and assigns
  > them under the normal wave contract — and using this lane to discover
  > new candidate URLs beyond your assigned URL list is the ONLY sanctioned
  > exception to the stay-within-your-assignment constraint of the wave
  > contract you were spawned with.

  Targets + anchors (unique static strings): width-sweep skill Step 2.2 item
  2 tail ("before deduplication for `full` tier.") — sentence appended as a
  3-space-indented continuation paragraph; fetcher agent template before
  "## Untrusted content policy — read before summarizing any fetched page". A missing anchor raises
   `OpencodeInstallError` instead of silently dropping the sentence.
   Threading is keyword-only with default False on
   `_render_skill`/`render_skills`/`render_agents`; the `install` verb
   computes the effective flag as `[web] parallel_search_lane` OR the
   resolved profile's `parallel_search_lane` (`prof.parallel_search_lane`,
   resolved with the same config path as the gear, so `[profile.*]`
   overlays apply; global installs carry no vault config -> both inputs
   False -> lane off).

- **Per-profile override (coordinator-adjudicated MUST-FIX; supersedes the
  build-time decision recorded in the progress ledger)** — the lane is now
  settable PER PROFILE, not config-only. `Profile` gains
  `parallel_search_lane: bool = False` (core/profiles.py, next to
  `utility_scoring`; default False keeps every shipped profile and all frozen
  goldens byte-identical), legal as a `[profile.<name>]` overlay key through
  the existing `_load_user_overlays` path — so `hpr config set` (vault-global
  `[web] parallel_search_lane`) AND per-profile TOML both work, per the
  dispatch. EFFECTIVE-FLAG SEMANTICS: the lane is enabled iff the vault-global
  `[web] parallel_search_lane` flag is true OR the operation's resolved
  profile enables its own key. Profile resolution follows each surface's
  existing convention: `install` already resolves explicit `--profile` >
  persisted gear > "full" with the target's config path before rendering, so
  the OR rides that resolved object; `hpr search-web` gains a `--profile`
  option following the same verb convention (explicit `--profile` >
  `[pipeline] profile`, i.e. the gear persisted by `hpr profile use`,
  defaulting to "full") via `resolve_profile(<name>, vault.config_path)`.
  The OR short-circuits on the config flag, so the profile — and any broken
  overlay in it — is only consulted when the global flag alone doesn't
  already enable the lane; an unknown/invalid `--profile` fails cleanly
  (UNKNOWN_PROFILE exit 1) before any provider work. Both inputs default
  False, so default-off behavior and rendered bytes are unchanged.

- **Golden regeneration (the one deliberate pass)** — default-state goldens
  are UNTOUCHED: `git diff tests/fixtures/skill_goldens
  tests/fixtures/agent_goldens_opencode` is empty at close, and the frozen
  golden suites (19 skill files byte-compared, 15 agent files byte-compared)
  pass unchanged, proving off-state renders are byte-identical to pre-P4-C.
  NEW fixtures captured once from this renderer over the full gear
  (determinism re-checked byte-for-byte):
  `tests/fixtures/skill_goldens_lane_on/hyperresearch-2-width-sweep.md` and
  `tests/fixtures/agent_goldens_opencode_lane_on/hyperresearch-fetcher.md`.
  Separate directories ON PURPOSE: both golden inventory tests pin their dirs
  to exactly the chain/roster file sets, so extra files inside them would
  fail inventory. Lane-on renders also assert zero collateral drift: every
  OTHER skill/agent file stays byte-identical to its default golden with the
  lane enabled.

- **README** — the intro feature list gains ONE bullet (after the
  academic-APIs line) covering the provider protocol surface: builtin /
  tavily / exa / crawl4ai / parallel, the ordered `[web] provider` fallback
  chain, and the opt-in `hpr search-web` lane. (Build-time note that README
  had no providers line was true then; the adjudicated closure added it.)

Gates at close: pytest exit 0 (**1371 passed, 107 skipped** — all skips
pre-existing), ruff clean, mypy --strict clean (98 files).

Blind-gauntlet record for this piece: r1 REJECT (shipped skill golden carried
a literal `{hpr_path}` against that file's `$HPR` convention); r2 REJECT
(fetcher sentence licensed searching while its own template forbade it);
r3 REJECT (sentence cited a no-searcher rule that exists nowhere in its
rendered file; skill side lacked the profile clause); r4 ACCEPT with zero
high findings — all remaining dispositions accepted/bundle-limitation and
recorded on the progress page. Adjacent consistency fixes folded in during
the waves: `--json` error envelopes extended to config set bad-value /
unknown-key and config get unknown-key paths. Zero network in
new tests (provider seam monkeypatched at
`hyperresearch.web.base.resolve_web_provider`, the test_fetch_batch.py seam).

## F-B1 — opencode permission-model correction (2026-09-02)

**Failure that exposed it, live mid-run:** the step-11 synthesizer spawn
could not Write its pass-1/pass-2 files — the subagent had NO local Write
tool and fell through to the Home Assistant MCP write tool. Root cause
chain, verified against opencode 1.18.26's published docs, its config JSON
schema, and the installed binary's own permission-mapping code
(`["edit","write","apply_patch"]` grouped under one permission key):

1. opencode's `edit` permission covers **edit + write + patch as ONE unit**.
   There is no separate `write` permission key. The synthesizer's ported
   Claude Code frontmatter (`permission: {edit: deny}`, intended as "Read +
   Write only") therefore blocked Write too — exactly the observed failure.
2. The patcher/polish-auditor frontmatter (`permission: {write: deny}` +
   legacy `tools: {write: false}`) was worse in silence: `write` is an
   **unknown permission key** (a no-op), and the legacy `tools:` block is
   deprecated and merged into the same coarse edit-permission group — a
   `write: false` entry would deny the entire edit+write+patch group,
   blocking the Edit tool the patcher's whole role depends on.
3. The S0-3 spike had "proven" `tools.X: false` structurally removes a tool
   — but on an opencode version whose legacy-tools handling differed (and
   with the layer-2 lockdown plugin absent from the failing install, since
   `install --steps-only` skips plugins).

**Fix (upstream source, not just installed files):**

- `opencode_install.py`: `AgentSpec.tools_deny` emptied for patcher,
  polish-auditor, and synthesizer; `permission_denies` now carry only REAL
  opencode permission keys — synthesizer denies `bash` only; patcher and
  polish-auditor carry no frontmatter lock at all. Module docstring
  rewritten to document the model.
- `opencode_plugin.py`: docstring corrected — the lockdown plugin is now
  the ONLY layer enforcing the granular edit-vs-write split (it denies by
  granular tool NAME, which opencode's coarse permission keys cannot
  express). The deny matrix itself is unchanged: patcher/polish `write`;
  synthesizer `edit + bash` (Write open).
- Tests: `test_opencode_install.py` EXPECTED_TOOLS_DENY now empty,
  EXPECTED_PERMISSION carries only synthesizer `bash: deny` + the
  investigator task allowlist; `test_opencode_plugin.py` now pins the
  granular intent as a frozen literal AND asserts the specs stay clean of
  frontmatter edit/write locks (a belt-and-braces anti-regression pin).
- Goldens regenerated for the three affected files.

Gates: pytest — the four affected test files all pass; the only failures in
the full suite are pre-existing network-dependent SSRF tests that also
fail on a clean tree (verified via git stash).

**Operational note:** opencode loads config at startup and does not
hot-reload agent files — a running session keeps the old (broken)
definitions until restart. The ha-linux-agent vault now carries the fixed
roster in `.opencode/agents/` plus the lockdown plugin in
`.opencode/plugins/` (a full `hpr install`, not `--steps-only`).
