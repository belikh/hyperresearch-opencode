"""Tests for `hyperresearch archive-run`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app

runner = CliRunner()


@pytest.fixture
def vault_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Init a vault, chdir into it, and return its root."""
    result = runner.invoke(app, ["init", str(tmp_path / "v"), "--name", "Archive Test"])
    assert result.exit_code == 0, result.output
    root = tmp_path / "v"
    monkeypatch.chdir(root)
    return root


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_prior_run(root: Path, vault_tag: str = "alpha-beta") -> None:
    """Lay down a representative set of prior-run artifacts."""
    research = root / "research"
    # Per-run flat artifacts.
    _write(research / "scaffold.md", f"# Scaffold\n\nRun config: vault_tag: {vault_tag}\n")
    _write(research / "prompt-decomposition.json", '{"vault_tag": "' + vault_tag + '"}')
    _write(research / "loci.json", "[]")
    _write(research / "comparisons.md", "# comparisons")
    _write(research / "patch-log.json", "{}")
    _write(research / "polish-log.json", "{}")
    _write(research / "critic-findings-dialectic.json", "{}")
    # Namespaced — must NOT be archived.
    _write(research / f"query-{vault_tag}.md", "verbatim query")
    _write(research / "notes" / f"final_report_{vault_tag}.md", "---\ntitle: Report\n---\n# Report")
    # Scratch tree.
    _write(research / "temp" / "evidence-digest.md", "scratch")
    _write(research / "temp" / "claims-foo.json", "{}")
    _write(research / "temp" / "draft-a.md", "draft a")


def test_archive_run_no_prior_artifacts_is_noop(vault_root: Path):
    """Fresh vault — archive-run reports archived=False and creates nothing."""
    result = runner.invoke(app, ["archive-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["data"]["archived"] is False
    assert data["data"]["files_moved"] == 0
    assert not (vault_root / "research" / "runs").exists()


def test_archive_run_moves_flat_artifacts_and_temp_tree(vault_root: Path):
    """Prior-run files and the temp/ scratch tree both end up in the archive."""
    _seed_prior_run(vault_root, vault_tag="alpha-beta")
    result = runner.invoke(app, ["archive-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["data"]["archived"] is True
    assert data["data"]["previous_vault_tag"] == "alpha-beta"

    # Originals are gone.
    research = vault_root / "research"
    assert not (research / "scaffold.md").exists()
    assert not (research / "loci.json").exists()
    assert not (research / "comparisons.md").exists()
    assert not (research / "patch-log.json").exists()
    assert not (research / "critic-findings-dialectic.json").exists()
    assert not (research / "temp" / "evidence-digest.md").exists()
    assert not (research / "temp" / "draft-a.md").exists()

    # Namespaced files stay put.
    assert (research / "query-alpha-beta.md").exists()
    assert (research / "notes" / "final_report_alpha-beta.md").exists()

    # Archive dir holds them. Use the path the command reported.
    archive_dir = vault_root / data["data"]["archive_dir"]
    assert archive_dir.is_dir()
    assert (archive_dir / "scaffold.md").read_text(encoding="utf-8").startswith("# Scaffold")
    assert (archive_dir / "loci.json").exists()
    assert (archive_dir / "temp" / "evidence-digest.md").exists()
    assert (archive_dir / "temp" / "draft-a.md").exists()

    # research/temp/ is recreated empty so the next run can write into it
    # without an extra mkdir.
    temp = research / "temp"
    assert temp.is_dir()
    assert list(temp.iterdir()) == []

    # Archive dir name includes the inferred tag.
    assert "alpha-beta" in archive_dir.name


def test_archive_run_falls_back_to_timestamp_when_no_tag(vault_root: Path):
    """If no query-*.md exists and scaffold.md has no recoverable vault_tag,
    the archive dir is still created (timestamp-only suffix)."""
    research = vault_root / "research"
    _write(research / "loci.json", "[]")
    _write(research / "scaffold.md", "# Scaffold\n\nno tag in here\n")
    result = runner.invoke(app, ["archive-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["data"]["archived"] is True
    assert data["data"]["previous_vault_tag"] is None
    archive_dir = vault_root / data["data"]["archive_dir"]
    assert archive_dir.is_dir()
    assert (archive_dir / "loci.json").exists()
    # Dir name is just `archive-<timestamp>`, no slug.
    assert archive_dir.name.startswith("archive-")


def test_archive_run_handles_repeat_invocations_in_same_second(vault_root: Path):
    """Two archive-runs back to back must not collide on the timestamp suffix."""
    _seed_prior_run(vault_root, vault_tag="run-one")
    r1 = runner.invoke(app, ["archive-run", "--json"])
    assert r1.exit_code == 0, r1.output

    # Re-seed and archive again immediately.
    _seed_prior_run(vault_root, vault_tag="run-one")
    r2 = runner.invoke(app, ["archive-run", "--json"])
    assert r2.exit_code == 0, r2.output

    d1 = json.loads(r1.output)["data"]["archive_dir"]
    d2 = json.loads(r2.output)["data"]["archive_dir"]
    assert d1 != d2
    assert (vault_root / d1).is_dir()
    assert (vault_root / d2).is_dir()


def test_archive_run_prefers_most_recent_query_file(vault_root: Path):
    """If multiple query-*.md exist, the most recently modified one wins
    as the inferred previous_vault_tag.
    """
    import os
    import time

    research = vault_root / "research"
    _write(research / "scaffold.md", "# Scaffold\n")
    old_query = research / "query-old-tag.md"
    new_query = research / "query-new-tag.md"
    _write(old_query, "old")
    time.sleep(0.05)
    _write(new_query, "new")
    # Make the mtime ordering unambiguous (Windows mtime resolution can blur).
    now = time.time()
    os.utime(old_query, (now - 60, now - 60))
    os.utime(new_query, (now, now))

    result = runner.invoke(app, ["archive-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["data"]["previous_vault_tag"] == "new-tag"
