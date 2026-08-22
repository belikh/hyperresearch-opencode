"""Tests for `hyperresearch vault-tag`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app

runner = CliRunner()

_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]+-[0-9a-f]{6}$")


@pytest.fixture
def vault_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Init a vault, chdir into it, return its root."""
    result = runner.invoke(app, ["init", str(tmp_path / "v"), "--name", "Tag Test"])
    assert result.exit_code == 0, result.output
    root = tmp_path / "v"
    monkeypatch.chdir(root)
    return root


def _invoke(slug: str) -> dict:
    result = runner.invoke(app, ["vault-tag", slug, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_vault_tag_basic_format(vault_root: Path):
    data = _invoke("efield-dft-sac")["data"]
    assert data["slug"] == "efield-dft-sac"
    assert len(data["suffix"]) == 6
    assert re.fullmatch(r"[0-9a-f]{6}", data["suffix"])
    assert _TAG_RE.match(data["vault_tag"])
    assert data["vault_tag"].startswith("efield-dft-sac-")


def test_vault_tag_repeated_calls_produce_distinct_tags(vault_root: Path):
    """Same slug, two invocations — must yield different suffixes. This is
    the core collision-avoidance property: a user re-running the SAME
    query produces a fresh tag, so their old final report is never
    overwritten.
    """
    tags = set()
    for _ in range(20):
        data = _invoke("topic")["data"]
        tags.add(data["vault_tag"])
    # secrets.token_hex collisions in 20 draws from 16M-name space are
    # astronomically unlikely; if this ever flakes the suffix generator
    # is broken.
    assert len(tags) == 20


def test_vault_tag_avoids_existing_query_file(vault_root: Path):
    """If a prior run already produced research/query-topic-aaaaaa.md, the
    new tag must not collide with it.
    """
    research = vault_root / "research"
    (research / "query-topic-aaaaaa.md").write_text("prior")
    # Bias the test by hammering the same slug 30x; each must dodge the
    # reserved suffix.
    for _ in range(30):
        data = _invoke("topic")["data"]
        assert data["vault_tag"] != "topic-aaaaaa"


def test_vault_tag_avoids_existing_final_report(vault_root: Path):
    """Final reports also lock a suffix even if the corresponding query
    file got moved or deleted.
    """
    notes = vault_root / "research" / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "final_report_topic-cafe42.md").write_text("---\ntitle: x\n---\n")
    for _ in range(30):
        data = _invoke("topic")["data"]
        assert data["vault_tag"] != "topic-cafe42"


def test_vault_tag_ignores_legacy_without_suffix_tag(vault_root: Path):
    """A pre-namespacing vault may have query-topic.md with no hex suffix.
    That format can't collide with the new suffix-style tags (different
    length), so we just need to confirm the command runs cleanly and
    produces a valid suffixed tag.
    """
    research = vault_root / "research"
    (research / "query-topic.md").write_text("legacy")
    data = _invoke("topic")["data"]
    assert _TAG_RE.match(data["vault_tag"])
    assert data["vault_tag"] != "topic"


def test_vault_tag_rejects_invalid_slugs(vault_root: Path):
    # `--` separates options from positional args so typer doesn't try to
    # interpret leading-dash slugs as flags.
    bad = ["Topic", "topic with spaces", "topic_underscore", "-leading-dash", ""]
    for slug in bad:
        result = runner.invoke(app, ["vault-tag", "--json", "--", slug])
        assert result.exit_code == 1, f"slug {slug!r} should have been rejected"
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error_code"] == "INVALID_SLUG"


def test_vault_tag_works_without_vault_only_fails_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """If the user runs vault-tag outside a vault, the command exits
    nonzero with a NO_VAULT error code rather than crashing.
    """
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["vault-tag", "topic", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["error_code"] == "NO_VAULT"
