"""Regression tests for schema migrations.

Upstream has no test_migrations.py (see PORTING-NOTES §P1-1); this file was
added by the opencode port for the P1-1 gauntlet-r2 fixes:
  - CRITICAL: DROP TABLE notes under foreign_keys=ON fired ON DELETE CASCADE,
    wiping tags/note_content/embeddings/claims/assets and SET NULL'ing
    sources.note_id on legacy-vault auto-migration.
  - brick-state recovery from interrupted table rebuilds.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hyperresearch.core.db import SCHEMA_VERSION
from hyperresearch.core.migrations import get_schema_version, migrate

# A faithful legacy vault: stamped v5, notes table WITHOUT tier/content_type
# (added by v6) and with the pre-v7 type CHECK that rejects 'interim', plus
# every child table that references notes(id).
_LEGACY_SCHEMA = """
CREATE TABLE _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE notes (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    path         TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','review','evergreen','stale','deprecated','archive')),
    type         TEXT NOT NULL DEFAULT 'note'
                     CHECK (type IN ('note','raw','index','moc')),
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

CREATE TABLE note_content (
    note_id    TEXT PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    body_plain TEXT NOT NULL
);

CREATE TABLE tags (
    note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    PRIMARY KEY (note_id, tag)
);

CREATE TABLE embeddings (
    note_id    TEXT PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
    model      TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector     BLOB NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE assets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id    TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    type       TEXT NOT NULL CHECK (type IN ('image','screenshot','pdf','other')),
    filename   TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE sources (
    url     TEXT PRIMARY KEY,
    note_id TEXT REFERENCES notes(id) ON DELETE SET NULL
);
"""


def _legacy_connection(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "legacy.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript(_LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO notes (id, title, path, type, created) "
        "VALUES ('n1', 'Legacy Note', 'notes/legacy.md', 'note', '2024-01-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO note_content VALUES ('n1', 'body text', 'body text')")
    conn.execute("INSERT INTO tags VALUES ('n1', 'legacy')")
    conn.execute("INSERT INTO embeddings VALUES ('n1', 'test-model', 8, x'0011', '2024-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO assets (note_id, type, filename, created_at) "
        "VALUES ('n1', 'pdf', 'n1.pdf', '2024-01-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO sources (url, note_id) VALUES ('https://example.com/a', 'n1')")
    conn.execute("INSERT INTO _meta (key, value) VALUES ('schema_version', '5')")
    conn.commit()
    # Mimic db.get_connection(): EVERY vault open enforces foreign keys.
    # This is the exact condition under which the pre-fix DROP cascaded.
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class TestMigrationPreservesChildData:
    """P1-1 gauntlet r2 finding 1 (CRITICAL): the v7/v8 rebuilds DROP TABLE
    notes; with FK enforcement on, that implicit-DELETEs every row and fires
    ON DELETE CASCADE against child tables. Child rows must survive."""

    def test_legacy_vault_migration_preserves_child_rows(self, tmp_path: Path):
        conn = _legacy_connection(tmp_path)

        applied = migrate(conn, SCHEMA_VERSION)

        assert applied == list(range(6, SCHEMA_VERSION + 1))
        # The regression itself: all cascade children survived the two
        # table-rebuild migrations (v7 + v8 each DROP the notes table).
        assert _count(conn, "notes") == 1
        assert _count(conn, "tags") == 1
        assert _count(conn, "note_content") == 1
        assert _count(conn, "embeddings") == 1
        assert _count(conn, "assets") == 1

    def test_sources_note_id_not_nulled_by_rebuild(self, tmp_path: Path):
        conn = _legacy_connection(tmp_path)
        migrate(conn, SCHEMA_VERSION)
        row = conn.execute("SELECT note_id FROM sources").fetchone()
        # Pre-fix, ON DELETE SET NULL silently detached the source URL.
        assert row[0] == "n1"

    def test_migrated_notes_data_and_new_columns_intact(self, tmp_path: Path):
        conn = _legacy_connection(tmp_path)
        migrate(conn, SCHEMA_VERSION)

        cols = {r[1] for r in conn.execute("PRAGMA table_info(notes)")}
        for added in ("tier", "content_type", "doi", "quality_score", "oa_url", "oa_recovery_kind"):
            assert added in cols

        note = conn.execute("SELECT title, path, type FROM notes WHERE id = 'n1'").fetchone()
        assert note["title"] == "Legacy Note"
        assert note["path"] == "notes/legacy.md"

        # The whole point of v7/v8: rebuilt CHECK accepts the new types...
        conn.execute(
            "INSERT INTO notes (id, title, path, type, created) "
            "VALUES ('i1', 'Interim', 'notes/i.md', 'interim', '2024-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO notes (id, title, path, type, created) "
            "VALUES ('sa1', 'SA', 'notes/sa.md', 'source-analysis', '2024-01-01T00:00:00Z')"
        )

    def test_foreign_keys_re_enabled_after_migration(self, tmp_path: Path):
        """The fix must restore enforcement — db.py relies on it after open."""
        conn = _legacy_connection(tmp_path)
        migrate(conn, SCHEMA_VERSION)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        # And the restored constraint actually bites.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO tags VALUES ('missing-note', 'x')")

    def test_final_schema_version_stamped(self, tmp_path: Path):
        conn = _legacy_connection(tmp_path)
        migrate(conn, SCHEMA_VERSION)
        assert get_schema_version(conn) == SCHEMA_VERSION

    def test_migrate_is_idempotent_when_already_current(self, tmp_path: Path):
        conn = _legacy_connection(tmp_path)
        migrate(conn, SCHEMA_VERSION)
        assert migrate(conn, SCHEMA_VERSION) == []


class TestInterruptedRebuildRecovery:
    """P1-1 gauntlet r2 finding 2 (HIGH fragility): a crash mid-rebuild leaves
    notes_v7/notes_v8 committed; re-running used to die on
    "table notes_v7 already exists" forever."""

    @staticmethod
    def _with_leftover_scratch(conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE notes_v7 (id TEXT PRIMARY KEY, title TEXT NOT NULL)"
        )
        conn.commit()

    def test_leftover_scratch_table_does_not_brick_migration(self, tmp_path: Path):
        conn = _legacy_connection(tmp_path)
        self._with_leftover_scratch(conn)

        migrate(conn, SCHEMA_VERSION)  # used to raise OperationalError

        assert get_schema_version(conn) == SCHEMA_VERSION
        assert _count(conn, "tags") == 1  # data still intact
        leftover = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notes_v7'"
        ).fetchone()
        assert leftover is None

    def test_leftover_promoted_when_notes_lost_mid_rebuild(self, tmp_path: Path):
        """Crash window between DROP TABLE notes and the RENAME: the scratch
        holds the only copy of the data and must be restored, not dropped."""
        conn = _legacy_connection(tmp_path)
        # A real interrupted v7 rebuild leaves a FULL-schema scratch table;
        # model that (subset of columns suffices — all NOT NULL ones present).
        conn.execute(
            """
            CREATE TABLE notes_v7 (
                id           TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                path         TEXT NOT NULL UNIQUE,
                status       TEXT NOT NULL DEFAULT 'draft',
                type         TEXT NOT NULL DEFAULT 'note'
                                 CHECK (type IN ('note','raw','index','moc','interim')),
                created      TEXT NOT NULL,
                file_mtime   REAL NOT NULL DEFAULT 0,
                content_hash TEXT NOT NULL DEFAULT '',
                synced_at    TEXT NOT NULL DEFAULT ''
            )
        """
        )
        conn.execute("INSERT INTO notes_v7 (id, title, path, created) "
                     "VALUES ('saved', 'Rescued Data', 'notes/saved.md', '2024-01-01T00:00:00Z')")
        conn.execute("ALTER TABLE notes RENAME TO notes_doomed")
        conn.execute("DROP TABLE notes_doomed")
        conn.commit()

        migrate(conn, SCHEMA_VERSION)

        titles = [r[0] for r in conn.execute("SELECT title FROM notes")]
        assert "Rescued Data" in titles

    def test_gap_versions_are_not_stamped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A version missing from MIGRATIONS runs nothing, so stamps nothing —
        but later versions still run and stamp past it."""
        import hyperresearch.core.migrations as mig

        conn = _legacy_connection(tmp_path)
        reduced = dict(mig.MIGRATIONS)
        del reduced[7]  # simulate a dict gap
        monkeypatch.setattr(mig, "MIGRATIONS", reduced)

        applied = migrate(conn, SCHEMA_VERSION)

        assert 7 not in applied
        assert 6 in applied and SCHEMA_VERSION in applied
