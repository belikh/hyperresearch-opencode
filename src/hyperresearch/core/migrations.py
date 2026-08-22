"""Schema migration system for hyperresearch SQLite databases."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

# Each migration upgrades from version N-1 to N. May be either:
#   - a SQL string (executed via executescript)
#   - a callable(conn) for migrations that need conditional logic (e.g. ADD COLUMN)
# Migrations MUST be idempotent (safe to re-run).


def _migrate_v6_tier_content_type(conn: sqlite3.Connection) -> None:
    """Add tier and content_type columns to notes (idempotent)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    if "tier" not in existing:
        conn.execute("ALTER TABLE notes ADD COLUMN tier TEXT")
    if "content_type" not in existing:
        conn.execute("ALTER TABLE notes ADD COLUMN content_type TEXT")
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_notes_tier ON notes(tier);
        CREATE INDEX IF NOT EXISTS idx_notes_content_type ON notes(content_type);
    """)


def _migrate_v7_interim_note_type(conn: sqlite3.Connection) -> None:
    """Add 'interim' to the notes.type CHECK constraint.

    SQLite can't alter a CHECK constraint in place — we rebuild the table.
    Hyperresearch step 3 depth-investigator writes type='interim' notes, so
    pre-v7 vaults would reject those on sync.
    """
    # Cheap pre-check: if the table already accepts 'interim', skip.
    try:
        with conn:
            conn.execute("SAVEPOINT check_interim_type")
            try:
                conn.execute(
                    "INSERT INTO notes (id, title, path, type, created) "
                    "VALUES ('__migrate_probe__', 'probe', '__migrate_probe__', 'interim', '1970-01-01T00:00:00Z')"
                )
                conn.execute("DELETE FROM notes WHERE id = '__migrate_probe__'")
                conn.execute("RELEASE check_interim_type")
                return  # already compatible
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK TO check_interim_type")
                conn.execute("RELEASE check_interim_type")
    except sqlite3.OperationalError:
        pass

    # Rebuild the table with the expanded CHECK. Preserve all data.
    conn.executescript("""
        CREATE TABLE notes_v7 (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            path         TEXT NOT NULL UNIQUE,
            status       TEXT NOT NULL DEFAULT 'draft'
                             CHECK (status IN ('draft','review','evergreen','stale','deprecated','archive')),
            type         TEXT NOT NULL DEFAULT 'note'
                             CHECK (type IN ('note','raw','index','moc','interim')),
            tier         TEXT
                             CHECK (tier IS NULL OR tier IN ('ground_truth','institutional','practitioner','commentary','unknown')),
            content_type TEXT
                             CHECK (content_type IS NULL OR content_type IN ('paper','docs','article','blog','forum','dataset','policy','code','book','transcript','review','unknown')),
            source       TEXT,
            parent       TEXT,
            deprecated   INTEGER NOT NULL DEFAULT 0,
            reviewed     TEXT,
            expires      TEXT,
            word_count   INTEGER NOT NULL DEFAULT 0,
            summary      TEXT,
            created      TEXT NOT NULL,
            updated      TEXT,
            file_mtime   REAL NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL DEFAULT '',
            synced_at    TEXT NOT NULL DEFAULT ''
        );
    """)
    # Copy preserving only columns that exist in the old table — defensive
    # against any schema drift between versions.
    old_cols = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    new_cols = {row[1] for row in conn.execute("PRAGMA table_info(notes_v7)")}
    shared = sorted(old_cols & new_cols)
    col_list = ", ".join(shared)
    conn.execute(
        f"INSERT INTO notes_v7 ({col_list}) SELECT {col_list} FROM notes"
    )
    conn.executescript("""
        DROP TABLE notes;
        ALTER TABLE notes_v7 RENAME TO notes;
    """)


def _migrate_v8_source_analysis_note_type(conn: sqlite3.Connection) -> None:
    """Add 'source-analysis' to the notes.type CHECK constraint.

    Same pattern as v7: SQLite can't alter a CHECK in place, so we rebuild
    the table when the existing one rejects the new type. Pre-v8 vaults
    would fail on sync once the source-analyst subagent starts writing
    type='source-analysis' notes.
    """
    try:
        with conn:
            conn.execute("SAVEPOINT check_source_analysis_type")
            try:
                conn.execute(
                    "INSERT INTO notes (id, title, path, type, created) "
                    "VALUES ('__migrate_probe_v8__', 'probe', '__migrate_probe_v8__', "
                    "'source-analysis', '1970-01-01T00:00:00Z')"
                )
                conn.execute("DELETE FROM notes WHERE id = '__migrate_probe_v8__'")
                conn.execute("RELEASE check_source_analysis_type")
                return  # already compatible
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK TO check_source_analysis_type")
                conn.execute("RELEASE check_source_analysis_type")
    except sqlite3.OperationalError:
        pass

    conn.executescript("""
        CREATE TABLE notes_v8 (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            path         TEXT NOT NULL UNIQUE,
            status       TEXT NOT NULL DEFAULT 'draft'
                             CHECK (status IN ('draft','review','evergreen','stale','deprecated','archive')),
            type         TEXT NOT NULL DEFAULT 'note'
                             CHECK (type IN ('note','raw','index','moc','interim','source-analysis')),
            tier         TEXT
                             CHECK (tier IS NULL OR tier IN ('ground_truth','institutional','practitioner','commentary','unknown')),
            content_type TEXT
                             CHECK (content_type IS NULL OR content_type IN ('paper','docs','article','blog','forum','dataset','policy','code','book','transcript','review','unknown')),
            source       TEXT,
            parent       TEXT,
            deprecated   INTEGER NOT NULL DEFAULT 0,
            reviewed     TEXT,
            expires      TEXT,
            word_count   INTEGER NOT NULL DEFAULT 0,
            summary      TEXT,
            created      TEXT NOT NULL,
            updated      TEXT,
            file_mtime   REAL NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL DEFAULT '',
            synced_at    TEXT NOT NULL DEFAULT ''
        );
    """)
    old_cols = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    new_cols = {row[1] for row in conn.execute("PRAGMA table_info(notes_v8)")}
    shared = sorted(old_cols & new_cols)
    col_list = ", ".join(shared)
    conn.execute(
        f"INSERT INTO notes_v8 ({col_list}) SELECT {col_list} FROM notes"
    )
    conn.executescript("""
        DROP TABLE notes;
        ALTER TABLE notes_v8 RENAME TO notes;
    """)


def _migrate_v9_source_ranking(conn: sqlite3.Connection) -> None:
    """Source-ranking schema (2.0 phase 2): note score columns, claims, api_cache.

    Additive only — existing rows keep NULL scores until `hpr sources score` /
    `hpr graph rank` populate them. Idempotent via column/table existence checks.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    new_columns = {
        "doi": "TEXT",
        "utility_score": "REAL",
        "authority_score": "REAL",
        "centrality_score": "REAL",
        "independence": "REAL",
        "citation_count": "INTEGER",
        "venue": "TEXT",
        "is_retracted": "INTEGER NOT NULL DEFAULT 0",
        "quality_score": "REAL",
    }
    for name, decl in new_columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {name} {decl}")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS claims (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id        TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            claim          TEXT NOT NULL,
            claim_hash     TEXT NOT NULL,
            quoted_support TEXT,
            numbers        TEXT,
            confidence     TEXT,
            evidence_type  TEXT,
            stance_target  TEXT,
            stance         TEXT,
            vault_tag      TEXT,
            ingested_at    TEXT NOT NULL,
            UNIQUE (note_id, claim_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_claims_note ON claims(note_id);
        CREATE INDEX IF NOT EXISTS idx_claims_vault_tag ON claims(vault_tag);
        CREATE INDEX IF NOT EXISTS idx_claims_stance_target ON claims(stance_target);

        CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
            claim_id UNINDEXED,
            claim,
            quoted_support,
            tokenize='porter unicode61'
        );

        CREATE TABLE IF NOT EXISTS api_cache (
            url        TEXT PRIMARY KEY,
            body       TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
    """)


_MIGRATE_V10_ESCALATIONS_SQL = """
CREATE TABLE IF NOT EXISTS escalations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT NOT NULL,
    reason        TEXT NOT NULL
                      CHECK (reason IN ('login_wall','bot_block','captcha','fetch_failed','interactive_needed','scholar_search')),
    requested_by  TEXT,
    suggested_by  TEXT,
    utility_score REAL,
    vault_tag     TEXT,
    status        TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','in_progress','fetched','needs_human','abandoned')),
    attempts      INTEGER NOT NULL DEFAULT 0,
    note_id       TEXT,
    claimed_by    TEXT,
    detail        TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (url, vault_tag)
);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_escalations_tag ON escalations(vault_tag);
"""


def _migrate_v11_oa_recovery(conn: sqlite3.Connection) -> None:
    """Open-access recovery columns. Additive, idempotent.

    Existing notes keep NULLs — nothing backfills them, because we cannot know
    after the fact whether an old note's body came from its `source` URL. Only
    fetches made after this migration record a substitution.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    for name in ("oa_url", "oa_source", "oa_version", "oa_license"):
        if name not in existing:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {name} TEXT")


def _migrate_v12_oa_recovery_kind(conn: sqlite3.Connection) -> None:
    """Distinguish a substitution from a rescue. Additive, idempotent.

    A separate version rather than a fifth column folded into v11: the v11
    migration is idempotent by column name, so a database already stamped v11
    would skip the new column entirely and never gain it.

    Notes written by v11 keep NULL. They are all substitutions — rescue did not
    exist yet — but they are left unstamped rather than backfilled, because the
    frontmatter on disk is the record and a migration cannot rewrite that.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    if "oa_recovery_kind" not in existing:
        conn.execute("ALTER TABLE notes ADD COLUMN oa_recovery_kind TEXT")


MIGRATIONS: dict[int, str | Callable[[sqlite3.Connection], None]] = {
    2: """
CREATE TABLE IF NOT EXISTS tag_aliases (
    alias     TEXT PRIMARY KEY,
    canonical TEXT NOT NULL
);
""",
    3: """
CREATE TABLE IF NOT EXISTS sources (
    url          TEXT PRIMARY KEY,
    note_id      TEXT REFERENCES notes(id) ON DELETE SET NULL,
    domain       TEXT,
    fetched_at   TEXT,
    provider     TEXT,
    content_hash TEXT,
    status       TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'dead', 'redirected'))
);
CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources(domain);
CREATE INDEX IF NOT EXISTS idx_sources_note ON sources(note_id);
""",
    4: """
CREATE TABLE IF NOT EXISTS assets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id      TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    type         TEXT NOT NULL CHECK (type IN ('image', 'screenshot', 'pdf', 'other')),
    filename     TEXT NOT NULL,
    url          TEXT,
    alt_text     TEXT,
    content_type TEXT,
    size_bytes   INTEGER,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_note ON assets(note_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type);
""",
    5: """
-- Dead fields (confidence, superseded_by, llm_compiled, llm_model, compile_source)
-- removed from code. Left as vestigial columns in existing DBs for compatibility.
-- New vaults won't have them. No structural changes needed.
""",
    6: _migrate_v6_tier_content_type,
    7: _migrate_v7_interim_note_type,
    8: _migrate_v8_source_analysis_note_type,
    9: _migrate_v9_source_ranking,
    10: _MIGRATE_V10_ESCALATIONS_SQL,
    11: _migrate_v11_oa_recovery,
    12: _migrate_v12_oa_recovery_kind,
}


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'").fetchone()
        return int(row[0] if isinstance(row, tuple) else row["value"]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _clear_rebuild_leftovers(conn: sqlite3.Connection) -> None:
    """Drop scratch tables left behind by an interrupted table rebuild.

    Delta vs upstream (P1-1 gauntlet r2 finding 2, HIGH): the v7/v8 rebuilds
    CREATE a scratch table (notes_v7 / notes_v8) whose DDL is already
    committed by executescript's implicit pre-commit, so a crash mid-rebuild
    leaves it behind and every later run dies on "table notes_v7 already
    exists" — the vault never opens again. The leftover copy is redundant
    whenever `notes` survived — the rebuild only drops the original after
    copying. The one window where it is NOT redundant is a crash between DROP
    TABLE notes and the RENAME; there the scratch holds the only copy of the
    data, so we restore it under the real name instead of dropping it.
    """
    names = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    for scratch in ("notes_v7", "notes_v8"):
        if scratch not in names:
            continue
        if "notes" in names:
            conn.execute(f'DROP TABLE "{scratch}"')
        else:
            # Crash landed between DROP TABLE notes and the RENAME: promote
            # the scratch copy back rather than destroying the last data.
            conn.execute(f'ALTER TABLE "{scratch}" RENAME TO notes')
            names.add("notes")


def migrate(conn: sqlite3.Connection, target_version: int) -> list[int]:
    """Run pending migrations. Returns list of versions applied.

    Delta vs upstream (P1-1 gauntlet r2 finding 1, CRITICAL): db.py opens
    every connection with `PRAGMA foreign_keys=ON`. Under enforcement, a
    `DROP TABLE notes` inside the v7/v8 table rebuilds performs an implicit
    DELETE of every row first — firing ON DELETE CASCADE against tags /
    note_content / embeddings / claims / assets and ON DELETE SET NULL against
    sources.note_id, silently wiping a legacy vault's child data on open.
    Fixed with the standard SQLite table-rebuild procedure
    (https://www.sqlite.org/lang_altertable.html): foreign-key enforcement is
    disabled around the whole migration run (making DROP a pure metadata
    operation), verified with PRAGMA foreign_key_check, then re-enabled.
    """
    current = get_schema_version(conn)
    if current >= target_version:
        return []

    applied: list[int] = []
    violations: list[Any] = []
    # The pragma is a no-op inside an open transaction — flush any pending
    # work first so turning enforcement off actually takes effect.
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        _clear_rebuild_leftovers(conn)
        for version in range(current + 1, target_version + 1):
            migration = MIGRATIONS.get(version)
            if migration is None:
                # Gap in the migration table: nothing ran, so nothing may be
                # stamped. Idempotent later migrations keep re-runs safe.
                continue
            if callable(migration):
                migration(conn)
            else:
                conn.executescript(migration)
            conn.commit()
            # Stamp only AFTER this version's changes are durably committed,
            # so a crash can never leave a stamped-but-unapplied schema.
            conn.execute(
                "INSERT OR REPLACE INTO _meta (key, value) VALUES ('schema_version', ?)",
                (str(version),),
            )
            conn.commit()
            applied.append(version)
        # Verify referential integrity while enforcement is still off;
        # re-enabling would otherwise turn any dangling reference into a
        # deferred landmine on the first later write.
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        try:
            # Success paths are fully committed above, so this commits only
            # trailing partial work on failure paths — and either way clears
            # any open transaction, without which the pragma below would be a
            # silent no-op.
            conn.commit()
        except sqlite3.Error:
            pass
        conn.execute("PRAGMA foreign_keys=ON")
    if violations:
        table, rowid, ref_table, fkid = violations[0]
        raise sqlite3.IntegrityError(
            f"migration left dangling references: {table} row {rowid} -> {ref_table} (fk {fkid})"
        )
    return applied
