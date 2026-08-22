"""Regression tests for auto_link ref_vocab determinism.

Gauntlet side-fix G13-REFVOCAB-ORDER (evidence/gauntlet/P1-3-verdict-r1.md):
ref_vocab was populated from unordered SQL with last-wins assignment, so
duplicate titles/aliases resolved to whichever row SQLite happened to return
last. Population is now ORDER BY stable unique keys — highest note id wins.

Note: on a stock SQLite vault, notes/aliases are inserted in id-ascending
order, which masks the old nondeterminism (last row == highest id by luck).
test_duplicate_aliases_survive_physical_row_reorder forces the physical order
to diverge from id order and is the case that genuinely fails against the
pre-fix code.
"""

from __future__ import annotations

from hyperresearch.core.linker import MIN_TITLE_LEN, auto_link
from hyperresearch.core.note import write_note
from hyperresearch.core.sync import compute_sync_plan, execute_sync


def _sync(vault):
    plan = compute_sync_plan(vault, force=True)
    execute_sync(vault, plan)


class TestRefVocabDeterminism:
    def test_duplicate_titles_resolve_to_highest_note_id(self, tmp_vault):
        title = "Duplicate Title Fixture"
        assert len(title) >= MIN_TITLE_LEN

        # Explicit note_ids keep the duplicates decoupled from filename
        # collision handling; the documented winner is the higher id.
        write_note(tmp_vault.notes_dir, title, body="First.\n", note_id="a-duplicate")
        write_note(tmp_vault.notes_dir, title, body="Second.\n", note_id="m-duplicate")

        write_note(
            tmp_vault.notes_dir,
            "Observer Note Unrelated",
            body="Discussion referencing duplicate title fixture here.\n",
        )
        _sync(tmp_vault)

        report = auto_link(tmp_vault)
        # Deterministic rule: population ORDER BY id, last-wins assignment.
        assert report["observer-note-unrelated"] == ["m-duplicate"]

    def test_target_stable_across_independent_vaults(self, tmp_vault, tmp_path):
        """auto_link mutates files as it links (second runs see existing
        links), so stability is proven by rebuilding the identical scenario
        in a fresh vault: both must pick the same duplicate-title target."""
        def build(root):
            v = type(tmp_vault).init(root, name="T")
            title = "Duplicate Title Fixture"
            write_note(v.notes_dir, title, body="First.\n", note_id="a-duplicate")
            write_note(v.notes_dir, title, body="Second.\n", note_id="m-duplicate")
            write_note(
                v.notes_dir,
                "Observer Note Unrelated",
                body="Discussion referencing duplicate title fixture here.\n",
            )
            _sync(v)
            return v

        first = auto_link(build(tmp_path / "vault-1"))
        second = auto_link(build(tmp_path / "vault-2"))
        expected = {"observer-note-unrelated": ["m-duplicate"]}
        assert first == second == expected

    def test_duplicate_aliases_survive_physical_row_reorder(self, tmp_vault):
        """The bite test: physical order deliberately diverges from id order.

        After sync, b-holder's alias row is deleted and re-inserted so it
        becomes physically LAST. Pre-fix last-wins-over-unordered-rows then
        linked to 'b-holder'; with ORDER BY alias, note_id the target stays
        'z-holder' regardless of storage order.
        """
        alias = "Shared Alias Phrase Fixture"
        assert len(alias) >= MIN_TITLE_LEN

        write_note(
            tmp_vault.notes_dir,
            "Alpha Holder Note Here",
            body="Holds the alias.\n",
            note_id="z-holder",
            extra_frontmatter={"aliases": [alias]},
        )
        write_note(
            tmp_vault.notes_dir,
            "Beta Holder Note Here",
            body="Also holds the alias.\n",
            note_id="b-holder",
            extra_frontmatter={"aliases": [alias]},
        )
        write_note(
            tmp_vault.notes_dir,
            "Observer Note Unrelated",
            body="Mention of shared alias phrase fixture appears.\n",
        )
        _sync(tmp_vault)

        # Force physical order to diverge from id order.
        tmp_vault.db.execute(
            "DELETE FROM aliases WHERE note_id = 'b-holder'"
        )
        tmp_vault.db.execute(
            "INSERT INTO aliases (note_id, alias) VALUES ('b-holder', ?)", (alias,)
        )

        report = auto_link(tmp_vault)
        assert report["observer-note-unrelated"] == ["z-holder"]

    def test_unique_titles_unchanged(self, tmp_vault):
        """Control: without duplicates the winner is the only candidate."""
        write_note(tmp_vault.notes_dir, "Singular Title Fixture", body="Only one.\n")
        write_note(
            tmp_vault.notes_dir,
            "Observer Note Unrelated",
            body="Reference to singular title fixture lives here.\n",
        )
        _sync(tmp_vault)

        report = auto_link(tmp_vault)
        assert report["observer-note-unrelated"] == ["singular-title-fixture"]
