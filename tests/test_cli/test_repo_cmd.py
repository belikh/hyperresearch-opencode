"""Tests for the `hpr repo` command group (P5).

Zero network: the wiki/ask verbs' DeepWiki exchange is stubbed by
monkeypatching DeepwikiProvider to a mock-transport instance (the
provider's own test battery covers the wire protocol); the map verb is
inherently local (regex lane forced by default — no tree-sitter pack in
the test env assertion, or the pack if installed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from hyperresearch.cli.repo import app as repo_app
from hyperresearch.web import deepwiki_provider

runner = CliRunner()

WIKI_DUMP = (
    "# Page: Overview\n\nThe overview page. Real content.\n\n"
    "# Page: Architecture\n\nHow it hangs together.\n"
)


def _sse_tool_text(text: str) -> httpx.Response:
    envelope = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"content": [{"type": "text", "text": text}]},
    }
    return httpx.Response(
        200,
        text=f"event: message\ndata: {json.dumps(envelope)}\n\n",
        headers={"Content-Type": "text/event-stream"},
    )


def _mock_provider_class(tool_texts: dict[str, str]) -> Any:
    """Build a DeepwikiProvider subclass whose every RPC answers from a
    fixed {tool_name: text} table — zero network, correct wire shape."""

    class _MockProvider(deepwiki_provider.DeepwikiProvider):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            def handler(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content.decode("utf-8"))
                if body.get("method") == "initialize":
                    return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})
                if body.get("method") == "tools/call":
                    name = body["params"]["name"]
                    return _sse_tool_text(tool_texts.get(name, ""))
                return httpx.Response(202)

            super().__init__(*args, _transport=httpx.MockTransport(handler), **kwargs)

    return _MockProvider


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from hyperresearch.core.vault import Vault

    monkeypatch.chdir(tmp_path)
    v = Vault.init(tmp_path, name="test")
    v.config.web_repo_source_lane = True
    v.config.save(v.config_path)
    return Vault.discover()


# ---------------------------------------------------------------------------
# Lane gate
# ---------------------------------------------------------------------------


def test_gate_disabled_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.core.vault import Vault

    monkeypatch.chdir(tmp_path)
    Vault.init(tmp_path, name="t")

    result = runner.invoke(repo_app, ["wiki", "owner/repo"])
    assert result.exit_code == 1
    assert "LANE_DISABLED" in result.output or "disabled" in result.output


def test_gate_unknown_profile_fails_clean(vault: Any) -> None:
    result = runner.invoke(repo_app, ["wiki", "owner/repo", "--profile", "nope"])
    assert result.exit_code == 1
    assert "UNKNOWN_PROFILE" in result.output or "unknown profile" in result.output


def test_gate_enabled_via_profile_overlay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.core.vault import Vault

    monkeypatch.chdir(tmp_path)
    v = Vault.init(tmp_path, name="t")
    v.config_path.write_text(
        v.config_path.read_text()
        + '\n[profile.repolane]\nextends = "full"\nrepo_source_lane = true\n'
    )
    # Hermetic: stub the provider so the only thing under test is the gate.
    monkeypatch.setattr(
        "hyperresearch.web.deepwiki_provider.DeepwikiProvider",
        _mock_provider_class({"read_wiki_contents": WIKI_DUMP}),
    )
    # global flag stays false; the profile overlay alone enables the lane.
    result = runner.invoke(
        repo_app, ["wiki", "owner/repo", "--profile", "repolane", "--no-save-pages", "--json"]
    )
    assert result.exit_code == 0, result.output  # gate PASSED + full verb ran
    assert "LANE_DISABLED" not in result.output


def test_bad_slug_rejected(vault: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(repo_app, ["wiki", "not-a-slug"])
    assert result.exit_code == 1
    assert "owner/repo" in result.output


# ---------------------------------------------------------------------------
# repo wiki — note creation, page splitting, provenance
# ---------------------------------------------------------------------------


def test_wiki_creates_monolithic_and_page_notes(
    vault: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "hyperresearch.web.deepwiki_provider.DeepwikiProvider", _mock_provider_class(
            {"read_wiki_contents": WIKI_DUMP}
        )
    )

    result = runner.invoke(repo_app, ["wiki", "owner/repo", "--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    # 1 wiki note + 2 page notes
    assert data["total_notes"] == 3
    kinds = sorted(n["kind"] for n in data["notes_created"])
    assert kinds == ["page", "page", "wiki"]

    conn = vault.db
    # sources-table row records deepwiki provenance
    row = conn.execute(
        "SELECT note_id, provider, domain FROM sources WHERE url = ?",
        ("https://deepwiki.com/owner/repo",),
    ).fetchone()
    assert row is not None
    assert row["provider"] == "deepwiki"
    assert row["domain"] == "deepwiki.com"

    # wiki note carries code/repo frontmatter
    wiki_note_id = next(n["note_id"] for n in data["notes_created"] if n["kind"] == "wiki")
    note_row = conn.execute(
        "SELECT id, type, source FROM notes WHERE id = ?", (wiki_note_id,)
    ).fetchone()
    assert note_row["source"] == "https://deepwiki.com/owner/repo"

    # page notes are parented to the wiki note
    page_ids = [n["note_id"] for n in data["notes_created"] if n["kind"] == "page"]
    for pid in page_ids:
        row = conn.execute("SELECT parent FROM notes WHERE id = ?", (pid,)).fetchone()
        assert row["parent"] == wiki_note_id


def test_wiki_no_pages_flag(vault: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hyperresearch.web.deepwiki_provider.DeepwikiProvider", _mock_provider_class(
            {"read_wiki_contents": WIKI_DUMP}
        )
    )

    result = runner.invoke(repo_app, ["wiki", "owner/repo", "--no-save-pages", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    assert data["total_notes"] == 1


def test_wiki_empty_contents_reports_not_indexed(
    vault: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "hyperresearch.web.deepwiki_provider.DeepwikiProvider", _mock_provider_class({})
    )
    result = runner.invoke(repo_app, ["wiki", "owner/repo", "--json"])
    assert result.exit_code == 1
    assert "not be indexed" in result.output or "REPO_NOT_INDEXED" in result.output


def test_wiki_refetch_existing_source_url(
    vault: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Second pull of the same repo URL still succeeds (sources dedup
    ignores duplicates); the vault just gains another note."""
    monkeypatch.setattr(
        "hyperresearch.web.deepwiki_provider.DeepwikiProvider", _mock_provider_class(
            {"read_wiki_contents": WIKI_DUMP}
        )
    )
    r1 = runner.invoke(repo_app, ["wiki", "owner/repo", "--json"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(repo_app, ["wiki", "owner/repo", "--json"])
    assert r2.exit_code == 0, r2.output


# ---------------------------------------------------------------------------
# repo map — local analysis, note write, lane provenance
# ---------------------------------------------------------------------------


def _write_sample_repo(base: Path) -> Path:
    repo = base / "sample-repo"
    (repo / "core").mkdir(parents=True)
    (repo / "app").mkdir(parents=True)
    (repo / "core").joinpath("defs.py").write_text(
        "class Engine:\n"
        "    def start(self):\n"
        "        pass\n"
        "\n"
        "def helper():\n"
        "    return Engine()\n",
        encoding="utf-8",
    )
    (repo / "app").joinpath("main.py").write_text(
        "from core.defs import Engine, helper\n"
        "\n"
        "def run():\n"
        "    e = Engine()\n"
        "    h = helper()\n"
        "    return e, h\n",
        encoding="utf-8",
    )
    (repo / "node_modules").mkdir()
    (repo / "node_modules").joinpath("junk.js").write_text(
        "function junk() {}\n", encoding="utf-8"
    )
    return repo


def test_map_creates_note_with_ranked_content(
    vault: Any, tmp_path: Path
) -> None:
    repo = _write_sample_repo(vault.root)

    result = runner.invoke(repo_app, ["map", str(repo), "--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    assert data["files"] == 2  # node_modules skipped
    assert data["lane"] in ("regex", "tree-sitter")
    assert data["note_id"]

    # The note exists, is a repo-source, and mentions both files.
    note_path = vault.notes_dir / f"{data['note_id']}.md"
    text = note_path.read_text(encoding="utf-8")
    assert "Repository map" in text
    assert "core/defs.py" in text
    assert "app/main.py" in text
    assert "node_modules" not in text.split("Remaining files")[0]

    # Frontmatter records the lane + file/edge counts.
    assert "repo_map_lane:" in text
    assert "repo-source" in text

    conn = vault.db
    row = conn.execute(
        "SELECT id, source FROM notes WHERE id = ?", (data["note_id"],)
    ).fetchone()
    assert row["source"].startswith("file://")


def test_map_no_save_prints_map(
    vault: Any, tmp_path: Path
) -> None:
    repo = _write_sample_repo(vault.root)
    result = runner.invoke(repo_app, ["map", str(repo), "--no-save"])
    assert result.exit_code == 0, result.output
    assert "Repository map" in result.output


def test_map_missing_path(vault: Any) -> None:
    result = runner.invoke(repo_app, ["map", "/nonexistent/xyz", "--json"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_map_empty_repo(vault: Any, tmp_path: Path) -> None:
    empty = tmp_path / "empty-repo"
    empty.mkdir()
    result = runner.invoke(repo_app, ["map", str(empty), "--json"])
    assert result.exit_code == 1
    assert "no source files" in result.output


# ---------------------------------------------------------------------------
# repo ask — zero persistence
# ---------------------------------------------------------------------------


def test_ask_returns_answer_saves_nothing(
    vault: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = vault.db.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]

    monkeypatch.setattr(
        "hyperresearch.web.deepwiki_provider.DeepwikiProvider", _mock_provider_class(
            {"ask_question": "The grounded answer."}
        )
    )
    result = runner.invoke(
        repo_app,
        ["ask", "owner/repo", "--question", "How does auth work?", "--json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    assert data["answer"] == "The grounded answer."

    after = vault.db.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]
    assert before == after  # zero persistence by design


def test_ask_rejects_bad_slug(vault: Any) -> None:
    result = runner.invoke(repo_app, ["ask", "bad-slug", "--question", "q", "--json"])
    assert result.exit_code == 1
    assert "owner/repo" in result.output


def test_ask_gate_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hyperresearch.core.vault import Vault

    monkeypatch.chdir(tmp_path)
    Vault.init(tmp_path, name="t")
    result = runner.invoke(repo_app, ["ask", "a/b", "--question", "q"])
    assert result.exit_code == 1
    assert "disabled" in result.output
