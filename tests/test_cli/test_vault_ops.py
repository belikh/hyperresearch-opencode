"""Smoke coverage for the P1-9 vault-ops CLI groups upstream leaves untested.

Upstream tests/test_cli/ covers only init/status/sync, note CRUD/tags,
graph broken, index build/list, export json (test_commands.py), note
mv/rm/edit (test_note_ops.py), archive-run and vault-tag. The remaining
groups ported in this piece — topic verbs, the rest of graph, tag
alias/suggest, note update, batch ops, export vault, git views, template
show, dedup/link/assets/repair wiring — ship with no upstream CLI tests.

This file pins that wiring through the typer app, mirroring the established
practice of covering upstream-untested surface at landing (P1-2 similarity
guard battery, P1-7 indexgen smoke). All offline: git lanes use a throwaway
repo; every other lane touches only tmp files.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app

runner = CliRunner()

NOTE_FM = "---\ntitle: {title}\nid: {nid}\nstatus: draft\ntype: note\ntags: {tags}\nparent: {parent}\n---\n\n{body}"


def _write_note(root: Path, nid: str, title: str, *, body: str = "body", tags: list[str] | None = None, parent: str | None = None) -> Path:
    """Write a markdown note straight into research/notes/ (caller syncs)."""
    tags_yaml = "[" + ", ".join(tags or []) + "]"
    text = NOTE_FM.format(title=title, nid=nid, tags=tags_yaml, parent=parent or "", body=body)
    if parent is None:
        # Keep frontmatter parseable: drop the empty parent line.
        text = "\n".join(line for line in text.splitlines() if not line.startswith("parent:") or parent) + "\n"
    path = root / "research" / "notes" / f"{nid}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def ops_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Init a vault via the app, chdir into it, return its root."""
    result = runner.invoke(app, ["init", str(tmp_path / "kb"), "--name", "Ops Test"])
    assert result.exit_code == 0, result.output
    root = tmp_path / "kb"
    monkeypatch.chdir(root)
    return root


def _sync() -> None:
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0, result.output


# --- topic ---


class TestTopicVerbs:
    def test_topic_list_counts_parents(self, ops_vault: Path):
        _write_note(ops_vault, "a-one", "A One", parent="ml/theory")
        _write_note(ops_vault, "b-two", "B Two", parent="ml/theory")
        _write_note(ops_vault, "c-three", "C Three", parent="ethics")
        _sync()
        result = runner.invoke(app, ["topic", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        counts = {t["topic"]: t["count"] for t in data["data"]}
        assert counts["ml/theory"] == 2
        assert counts["ethics"] == 1

    def test_topic_tree_json_includes_ancestor_paths(self, ops_vault: Path):
        _write_note(ops_vault, "a-one", "A One", parent="ml/deep-learning")
        _sync()
        result = runner.invoke(app, ["topic", "tree", "--json"])
        assert result.exit_code == 0
        topics = [t["topic"] for t in json.loads(result.output)["data"]]
        assert "ml" in topics  # ancestor synthesized with 0 direct notes
        assert "ml/deep-learning" in topics

    def test_topic_show_includes_subtopics(self, ops_vault: Path):
        _write_note(ops_vault, "deep-note", "Deep Note", parent="ml/deep-learning")
        _write_note(ops_vault, "other-note", "Other", parent="ethics")
        _sync()
        result = runner.invoke(app, ["topic", "show", "ml", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        ids = [n["id"] for n in data["data"]["notes"]]
        assert ids == ["deep-note"]


# --- graph ---


@pytest.fixture
def linked_vault(ops_vault: Path) -> Path:
    """Hub <- two inbound links; one outbound; one orphan; one broken link."""
    _write_note(ops_vault, "hub-note", "Hub Note", body="central hub\n")
    _write_note(ops_vault, "in-a", "In A", body="see [[hub-note]]\n")
    _write_note(ops_vault, "in-b", "In B", body="also [[hub-note]]\n")
    _write_note(ops_vault, "out-c", "Out C", body="points at [[missing-ref]]\n")
    _write_note(ops_vault, "lonely", "Lonely Note", body="no links either way\n")
    _sync()
    return ops_vault


class TestGraphVerbs:
    def test_backlinks(self, linked_vault: Path):
        result = runner.invoke(app, ["graph", "backlinks", "hub-note", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        sources = {b["source_id"] for b in data["data"]["backlinks"]}
        assert sources == {"in-a", "in-b"}

    def test_outlinks_marks_unresolved(self, linked_vault: Path):
        result = runner.invoke(app, ["graph", "outlinks", "out-c", "--json"])
        assert result.exit_code == 0
        outlinks = json.loads(result.output)["data"]["outlinks"]
        assert outlinks[0]["target_ref"] == "missing-ref"
        assert outlinks[0]["resolved"] is False

    def test_orphans(self, linked_vault: Path):
        result = runner.invoke(app, ["graph", "orphans", "--json"])
        assert result.exit_code == 0
        ids = {o["id"] for o in json.loads(result.output)["data"]}
        assert "lonely" in ids
        assert "hub-note" not in ids

    def test_hubs_orders_by_inbound(self, linked_vault: Path):
        result = runner.invoke(app, ["graph", "hubs", "--json"])
        assert result.exit_code == 0
        hubs = json.loads(result.output)["data"]
        assert hubs[0]["id"] == "hub-note"
        assert hubs[0]["inbound_links"] == 2

    def test_stub_dry_run_creates_nothing(self, linked_vault: Path):
        result = runner.invoke(app, ["graph", "stub", "--dry-run", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["would_stub"] == ["missing-ref"]
        assert not (linked_vault / "research" / "temp" / "missing-ref.md").exists()

    def test_stub_resolves_the_link(self, linked_vault: Path):
        result = runner.invoke(app, ["graph", "stub", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["data"]["count"] == 1
        assert (linked_vault / "research" / "temp" / "missing-ref.md").exists()
        _sync()
        result = runner.invoke(app, ["graph", "broken", "--json"])
        assert json.loads(result.output)["count"] == 0

    def test_rank_recomputes_scores(self, linked_vault: Path):
        result = runner.invoke(app, ["graph", "rank", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["ranked"] >= 3
        assert data["top"], "centrality scores should be stored"
        assert all("centrality" in n for n in data["top"])


# --- tag sub-app ---


class TestTagManagement:
    def test_alias_inserts_mapping(self, ops_vault: Path):
        result = runner.invoke(app, ["tag", "alias", "Ml", "machine-learning", "--json"])
        assert result.exit_code == 0
        import sqlite3

        conn = sqlite3.connect(ops_vault / ".hyperresearch" / "hyperresearch.db")
        try:
            pairs = conn.execute("SELECT alias, canonical FROM tag_aliases").fetchall()
        finally:
            conn.close()
        assert ("ml", "machine-learning") in pairs

    def test_suggest_catches_simple_plural(self, ops_vault: Path):
        for i in range(3):  # popular canonical tag needs count >= 3
            _write_note(ops_vault, f"m-{i}", f"M{i}", tags=["model"])
        _write_note(ops_vault, "plural", "Plural", tags=["models"])
        _sync()
        result = runner.invoke(app, ["tag", "suggest", "--json"])
        assert result.exit_code == 0
        suggestions = json.loads(result.output)["data"]
        pair = next(s for s in suggestions if s["singleton"] == "models")
        assert pair["suggested_canonical"] == "model"


# --- note update ---


class TestNoteUpdateVerb:
    @pytest.fixture
    def updated(self, ops_vault: Path):
        _write_note(ops_vault, "upd-me", "Upd Me")
        _sync()

    def test_update_fields_and_deprecate(self, ops_vault: Path, updated):
        result = runner.invoke(app, [
            "note", "update", "upd-me", "--status", "evergreen",
            "--add-tag", "fresh", "--summary", "Now summarized",
            "--parent", "ml", "--source", "https://example.com/x",
            "--tier", "institutional", "--content-type", "paper", "--json",
        ])
        assert result.exit_code == 0
        changed = set(json.loads(result.output)["data"]["changed"])
        assert {"status=evergreen", "+tag:fresh", "summary", "parent=ml", "source",
                "tier=institutional", "content_type=paper"} <= changed

        result = runner.invoke(app, ["note", "show", "upd-me", "--meta", "--json"])
        meta = json.loads(result.output)["data"]
        assert meta["status"] == "evergreen"
        assert meta["tier"] == "institutional"

    def test_deprecate_flag_sets_status_and_marker(self, ops_vault: Path, updated):
        result = runner.invoke(app, ["note", "update", "upd-me", "--deprecate", "--json"])
        assert result.exit_code == 0
        assert "deprecated" in json.loads(result.output)["data"]["changed"]
        result = runner.invoke(app, ["note", "show", "upd-me", "--meta", "--json"])
        assert json.loads(result.output)["data"]["status"] == "deprecated"

    def test_invalid_tier_rejected(self, ops_vault: Path, updated):
        result = runner.invoke(app, ["note", "update", "upd-me", "--tier", "bogus", "--json"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error_code"] == "INVALID_TIER"

    def test_nothing_to_change_short_circuits(self, ops_vault: Path, updated):
        result = runner.invoke(app, ["note", "update", "upd-me", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["data"]["changed"] == []


# --- batch ---


class TestBatchOps:
    @pytest.fixture
    def batch_vault(self, ops_vault: Path):
        _write_note(ops_vault, "ba-1", "Ba One", tags=["bulk"])
        _write_note(ops_vault, "ba-2", "Ba Two", tags=["bulk"])
        _write_note(ops_vault, "ba-3", "Ba Three")
        _sync()

    def test_tag_add_dry_run_then_apply(self, ops_vault: Path, batch_vault):
        result = runner.invoke(app, ["batch", "tag-add", "newtag", "--tag", "bulk", "--dry-run", "--json"])
        data = json.loads(result.output)["data"]
        assert data["would_modify"] == ["ba-1", "ba-2"]

        result = runner.invoke(app, ["batch", "tag-add", "newtag", "--tag", "bulk", "--json"])
        assert json.loads(result.output)["data"]["modified"] == ["ba-1", "ba-2"]
        content = (ops_vault / "research" / "notes" / "ba-1.md").read_text(encoding="utf-8")
        assert "newtag" in content

    def test_set_parent_matches_subtree(self, ops_vault: Path, batch_vault):
        result = runner.invoke(app, ["batch", "set-parent", "archived/2024", "--json"])
        assert result.exit_code == 0
        assert len(json.loads(result.output)["data"]["modified"]) == 3

    def test_set_status_rejects_unknown_status(self, ops_vault: Path, batch_vault):
        result = runner.invoke(app, ["batch", "set-status", "chaos", "--json"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error_code"] == "INVALID_STATUS"

    def test_deprecate_marks_files(self, ops_vault: Path, batch_vault):
        result = runner.invoke(app, ["batch", "deprecate", "--tag", "bulk", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["data"]["modified"] == ["ba-1", "ba-2"]
        result = runner.invoke(app, ["note", "list", "--status", "deprecated", "--json"])
        assert {n["id"] for n in json.loads(result.output)["data"]} == {"ba-1", "ba-2"}

    def test_tag_remove(self, ops_vault: Path, batch_vault):
        result = runner.invoke(app, ["batch", "tag-remove", "bulk", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output)["data"]["modified"] == ["ba-1", "ba-2"]
        result = runner.invoke(app, ["tags", "--json"])
        assert "bulk" not in {t["tag"] for t in json.loads(result.output)["data"]}


# --- export vault ---


class TestExportVaultVerb:
    def test_export_subset_by_tag(self, ops_vault: Path):
        _write_note(ops_vault, "keep-1", "Keep One", tags=["keep"])
        _write_note(ops_vault, "drop-1", "Drop One", tags=["skip"])
        _sync()
        out = ops_vault.parent / "exported"
        result = runner.invoke(app, ["export", "vault", str(out), "--tag", "keep", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert [e["id"] for e in data["exported"]] == ["keep-1"]
        assert (out / "research" / "notes" / "keep-1.md").exists()
        assert not (out / "research" / "notes" / "drop-1.md").exists()

    def test_dry_run_writes_nothing(self, ops_vault: Path):
        _write_note(ops_vault, "keep-1", "Keep One")
        _sync()
        out = ops_vault.parent / "exported-dry"
        result = runner.invoke(app, ["export", "vault", str(out), "--dry-run", "--json"])
        data = json.loads(result.output)["data"]
        assert data["would_export"]
        assert not out.exists()


# --- git ---


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    })
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
class TestGitVerbs:
    @pytest.fixture
    def git_vault(self, ops_vault: Path) -> Path:
        assert _git(ops_vault, "init", "-q").returncode == 0
        committed = ops_vault / "research" / "notes" / "old-note.md"
        committed.parent.mkdir(parents=True, exist_ok=True)
        committed.write_text("---\ntitle: Old\n---\n\nv1\n", encoding="utf-8")
        assert _git(ops_vault, "add", ".").returncode == 0
        assert _git(ops_vault, "commit", "-q", "-m", "seed notes").returncode == 0
        # Uncommitted new note for `changed`.
        (ops_vault / "research" / "notes" / "new-note.md").write_text(
            "---\ntitle: New\n---\n\nv1\n", encoding="utf-8"
        )
        return ops_vault

    def test_log_lists_md_commits(self, git_vault: Path):
        result = runner.invoke(app, ["git", "log", "--json"])
        assert result.exit_code == 0
        commits = json.loads(result.output)["data"]
        assert len(commits) == 1
        assert commits[0]["message"] == "seed notes"
        assert any(f.endswith("old-note.md") for f in commits[0]["files"])

    def test_blame_returns_porcelain_text(self, git_vault: Path):
        result = runner.invoke(app, ["git", "blame", "old-note", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["note_id"] == "old-note"
        assert "old-note.md" in data["blame"]

    def test_changed_reports_untracked_md(self, git_vault: Path):
        result = runner.invoke(app, ["git", "changed", "--json"])
        assert result.exit_code == 0
        changes = json.loads(result.output)["data"]
        entry = next(c for c in changes if c["path"].endswith("new-note.md"))
        assert entry["status"] == "untracked"


# --- template ---


class TestTemplateVerbs:
    def test_list_shows_builtins(self, ops_vault: Path):
        result = runner.invoke(app, ["template", "list", "--json"])
        assert result.exit_code == 0
        names = {t["name"] for t in json.loads(result.output)["data"]}
        assert {"note", "concept", "reference", "guide", "comparison", "moc"} <= names

    def test_show_prints_template(self, ops_vault: Path):
        result = runner.invoke(app, ["template", "show", "note"])
        assert result.exit_code == 0
        assert result.output.strip(), "template body expected"

    def test_show_missing_exits_nonzero(self, ops_vault: Path):
        result = runner.invoke(app, ["template", "show", "nope"])
        assert result.exit_code == 1


# --- dedup ---


class TestDedupCli:
    # Near-identical bodies: char-3-shingle Jaccard collapses fast under
    # word-level edits, so B differs from A by exactly one word.
    DUP_A = (
        "Gradient descent iterates over batches of training examples while "
        "adjusting weights to minimize the loss function surface. Learning "
        "rate schedules control step sizes across epochs of optimization. "
        "Momentum accumulates gradients from previous steps and damps "
        "oscillations across ravines of the loss surface."
    )
    DUP_B = DUP_A.replace("schedules", "schedule")

    def test_near_duplicates_found_brute_force(self, ops_vault: Path):
        _write_note(ops_vault, "dup-a", "Dup A", body=self.DUP_A)
        _write_note(ops_vault, "dup-b", "Dup B", body=self.DUP_B)
        _write_note(ops_vault, "unrelated", "Unrelated Topic", body="Quantum entanglement correlates distant particles instantly.")
        _sync()
        result = runner.invoke(app, ["dedup", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["method"] == "brute-force"
        pair_ids = {(p["note_a"]["id"], p["note_b"]["id"]) for p in data["pairs"]}
        assert ("dup-a", "dup-b") in pair_ids

    def test_fewer_than_two_notes_reports_empty(self, ops_vault: Path):
        _write_note(ops_vault, "only", "Only One", body="x")
        _sync()
        result = runner.invoke(app, ["dedup", "--json"])
        assert json.loads(result.output)["data"] == {"pairs": [], "total_compared": 0}


# --- link ---


class TestLinkCli:
    def test_auto_link_inserts_related_section(self, ops_vault: Path):
        target_title = "Transformer Architecture Deep Dive"  # >= MIN_TITLE_LEN (15)
        _write_note(ops_vault, "transformer-architecture-deep-dive", target_title)
        mention = _write_note(ops_vault, "mentioning", "Mentioning", body=f"We build on {target_title} below.\n")
        _sync()
        result = runner.invoke(app, ["link", "--auto", "--json"])
        assert result.exit_code == 0
        report = json.loads(result.output)["data"]["links_added"]
        assert report.get("mentioning") == ["transformer-architecture-deep-dive"]
        assert "[[transformer-architecture-deep-dive]]" in mention.read_text(encoding="utf-8")

    def test_dry_run_skips_db_sync_but_still_writes_files(self, ops_vault: Path):
        """Pins ACTUAL behavior with a filed inherited defect: upstream's
        --dry-run only skips the post-link DB sync — core.linker.auto_link
        has already appended the Related sections to the files by the time
        dry_run is consulted, so 'Show what links would be added' still
        edits files on disk. Fixing it needs a dry-run-aware linker (core/
        linker.py is outside this piece's ownership), so it is FILED in
        PORTING-NOTES §P1-9 and pinned here.
        """
        target_title = "Transformer Architecture Deep Dive"
        _write_note(ops_vault, "transformer-architecture-deep-dive", target_title)
        mention = _write_note(ops_vault, "mentioning", "Mentioning", body=f"We build on {target_title} below.\n")
        _sync()
        result = runner.invoke(app, ["link", "--auto", "--dry-run", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert data["total_links"] == 1  # report is produced...
        # ...the DB was NOT refreshed by the skipped sync...
        from hyperresearch.core.vault import Vault

        vault = Vault.discover()
        assert vault.db.execute(
            "SELECT COUNT(*) AS c FROM links WHERE source_id = 'mentioning'"
        ).fetchone()["c"] == 0
        # ...but the file edit already happened (the FILED defect).
        assert "[[transformer-architecture-deep-dive]]" in mention.read_text(encoding="utf-8")

    def test_no_input_fails_loudly(self, ops_vault: Path):
        result = runner.invoke(app, ["link", "--json"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error_code"] == "NO_INPUT"


# --- assets ---


class TestAssetsCli:
    @pytest.fixture
    def asset_vault(self, ops_vault: Path):
        from hyperresearch.core.vault import Vault

        _write_note(ops_vault, "pic-note", "Pic Note")
        _sync()
        vault = Vault.discover()
        vault.db.execute(
            "INSERT INTO assets (note_id, type, filename, url, alt_text, content_type, size_bytes, created_at) "
            "VALUES (?, 'image', 'research/assets/pic-note/fig1.png', 'https://example.com/f.png', 'fig', 'image/png', 2048, '2026-01-01T00:00:00Z')",
            ("pic-note",),
        )
        vault.db.commit()

    def test_assets_list_filters_by_type(self, ops_vault: Path, asset_vault):
        result = runner.invoke(app, ["assets", "list", "--type", "pdf", "--json"])
        assert json.loads(result.output)["count"] == 0
        result = runner.invoke(app, ["assets", "list", "--note", "pic-note", "--json"])
        data = json.loads(result.output)["data"]
        assert data[0]["filename"] == "research/assets/pic-note/fig1.png"
        assert data[0]["size_bytes"] == 2048

    def test_asset_path_returns_file_location(self, ops_vault: Path, asset_vault):
        result = runner.invoke(app, ["assets", "path", "pic-note", "--type", "image", "--json"])
        paths = json.loads(result.output)["data"]
        assert paths[0]["path"] == "research/assets/pic-note/fig1.png"

    def test_asset_path_missing_exits_nonzero(self, ops_vault: Path, asset_vault):
        result = runner.invoke(app, ["assets", "path", "pic-note", "--type", "screenshot", "--json"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error_code"] == "NOT_FOUND"


# --- repair ---


class TestRepairCli:
    def test_full_pipeline_report_shape(self, ops_vault: Path):
        _write_note(ops_vault, "rep-1", "Rep One", body="Some substantial body content.\n")
        _sync()
        result = runner.invoke(app, ["repair", "--json"])
        assert result.exit_code == 0
        report = json.loads(result.output)["data"]
        assert set(report) >= {"sync", "stubs", "enriched", "promoted", "indexes", "centrality_ranked", "agent_docs", "health"}
        # P1-10: core/agent_docs.py has landed, so repair --docs really
        # injects CLAUDE.md and reports the modified paths (upstream-faithful;
        # replaces the P1-9 no-op pin that expected [] here).
        assert report["agent_docs"] == ["CLAUDE.md (created)"]
        assert report["health"]["total_notes"] >= 1
