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
