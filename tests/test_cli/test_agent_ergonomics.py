"""Agent-ergonomics CLI surface (transcript audit 2026-09-04, R1-R5).

The audit of 445 opencode transcripts found 43% of bash calls were inline
python3 adapters around `-j` output — 398 hard errors, 181 retries. These
tests pin the replacements: the --jq projection, the always-present `data`
key, the uniform note-show envelope, `note read` windowing, --fields/--format
tsv, `escalation count`, `run artefact --summary`, and duplicate-fetch
success semantics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.cli._jq import JqError, evaluate

runner = CliRunner()


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    vault_dir = tmp_path / "kb"
    runner.invoke(app, ["init", str(vault_dir)])
    os.chdir(vault_dir)
    long_body = "GROUND ZERO\n\n" + ("lorem ipsum dolor sit amet " * 400)
    runner.invoke(
        app,
        ["note", "new", "Long Note", "--tag", "erg", "--body", long_body],
    )
    runner.invoke(app, ["note", "new", "Short Note", "--tag", "erg", "--body", "tiny"])
    runner.invoke(app, ["sync"])
    return vault_dir


# ---------------------------------------------------------------------------
# R1 — --jq + stable envelope
# ---------------------------------------------------------------------------


class TestJqEvaluator:
    def test_dot_path(self):
        assert evaluate(".a.b", {"a": {"b": 42}}) == [42]

    def test_identity(self):
        assert evaluate(".", {"x": 1}) == [{"x": 1}]

    def test_iterate_list(self):
        assert evaluate(".items[].id", {"items": [{"id": "a"}, {"id": "b"}]}) == ["a", "b"]

    def test_index(self):
        assert evaluate(".data.notes[0].word_count", {"data": {"notes": [{"word_count": 7}]}}) == [7]

    def test_pipe_length(self):
        assert evaluate(".data | length", {"data": [1, 2, 3]}) == [3]

    def test_missing_field_yields_none(self):
        assert evaluate(".nope", {}) == [None]

    def test_out_of_range_index_yields_nothing(self):
        assert evaluate(".a[5]", {"a": [1]}) == []

    def test_unsupported_syntax_raises(self):
        with pytest.raises(JqError):
            evaluate(".a | select(.x)", {"a": {"x": 1}})

    def test_index_into_scalar_raises(self):
        with pytest.raises(JqError):
            evaluate(".a[0]", {"a": 5})


class TestJqFlag:
    def test_projects_ids(self, vault):
        result = runner.invoke(app, ["--jq", ".data[].id", "note", "list", "--all", "-j"])
        assert result.exit_code == 0
        ids = result.output.strip().split("\n")
        assert "long-note" in ids and "short-note" in ids

    def test_scalar_prints_bare(self, vault):
        result = runner.invoke(app, ["--jq", ".data | length", "note", "list", "--all", "-j"])
        assert result.exit_code == 0
        assert result.output.strip() == "2"

    def test_bad_program_exits_2(self, vault):
        result = runner.invoke(app, ["--jq", ".[] | foo(", "note", "list", "-j"])
        assert result.exit_code == 2

    def test_error_envelope_carries_data_null(self, vault):
        result = runner.invoke(app, ["note", "show", "no-such-note", "-j"])
        assert result.exit_code == 1
        doc = json.loads(result.output)
        assert doc["ok"] is False
        assert doc["error_code"] == "NOT_FOUND"
        assert "data" in doc and doc["data"] is None


class TestNoteShowUniformEnvelope:
    def test_single_note_has_notes_array(self, vault):
        result = runner.invoke(app, ["note", "show", "short-note", "-j"])
        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert isinstance(doc["data"]["notes"], list)
        assert doc["data"]["notes"][0]["id"] == "short-note"
        assert doc["data"]["not_found"] == []

    def test_partial_batch_reports_not_found(self, vault):
        result = runner.invoke(app, ["note", "show", "short-note", "missing-one", "-j"])
        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["data"]["not_found"] == ["missing-one"]
        assert len(doc["data"]["notes"]) == 1

    def test_all_missing_is_error(self, vault):
        result = runner.invoke(app, ["note", "show", "missing-one", "missing-two", "-j"])
        assert result.exit_code == 1
        assert json.loads(result.output)["error_code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# R2 — note read
# ---------------------------------------------------------------------------


class TestNoteRead:
    def test_caps_and_prints_continue_marker(self, vault):
        result = runner.invoke(app, ["note", "read", "long-note", "--max-chars", "500"])
        assert result.exit_code == 0
        assert "GROUND ZERO" in result.output
        assert "continue with --chars 500:4500" in result.output

    def test_chars_window(self, vault):
        result = runner.invoke(
            app, ["note", "read", "long-note", "--chars", "100:200", "--max-chars", "0"]
        )
        assert result.exit_code == 0
        body_line, marker = result.output.strip().split("\n")
        assert len(body_line) == 100
        assert body_line.startswith("ipsum")
        assert "continue with --chars 200:" in marker

    def test_open_ended_window(self, vault):
        result = runner.invoke(app, ["note", "read", "long-note", "--chars", "0:11"])
        assert result.exit_code == 0
        assert result.output.startswith("GROUND ZERO")

    def test_lines_window(self, vault):
        result = runner.invoke(app, ["note", "read", "long-note", "--lines", "0:1"])
        assert result.exit_code == 0
        assert "GROUND ZERO" in result.output
        assert "lorem" not in result.output

    def test_meta_line(self, vault):
        result = runner.invoke(app, ["note", "read", "short-note", "--meta-line"])
        assert result.exit_code == 0
        assert result.output.startswith("# short-note |")

    def test_missing_note_fails(self, vault):
        result = runner.invoke(app, ["note", "read", "nope"])
        assert result.exit_code == 1

    def test_json_mode_reports_windows(self, vault):
        result = runner.invoke(
            app, ["note", "read", "long-note", "--chars", "0:50", "-j"]
        )
        assert result.exit_code == 0
        doc = json.loads(result.output)
        entry = doc["data"]["notes"][0]
        assert entry["window"] == [0, 50]
        assert "continue_with" in entry

    def test_plain_strips_fence(self, vault, monkeypatch):
        # Seed a fetched note whose body carries the untrusted fence.
        from hyperresearch.core.untrusted import wrap_body
        from hyperresearch.core.vault import Vault

        v = Vault.discover()
        fenced = wrap_body("SECRET PAYLOAD TEXT", "https://example.com/x")
        note_path = v.notes_dir / "fenced-note.md"
        note_path.write_text(
            "---\ntitle: Fenced\nsource: https://example.com/x\ntype: note\n---\n\n" + fenced,
            encoding="utf-8",
        )
        runner.invoke(app, ["sync"])
        try:
            fenced_result = runner.invoke(app, ["note", "read", "fenced-note", "--max-chars", "0"])
            assert fenced_result.exit_code == 0
            assert "<untrusted-source" in fenced_result.output
            plain_result = runner.invoke(
                app, ["note", "read", "fenced-note", "--plain", "--max-chars", "0"]
            )
            assert plain_result.exit_code == 0
            assert "<untrusted-source" not in plain_result.output
            assert "SECRET PAYLOAD TEXT" in plain_result.output
        finally:
            note_path.unlink(missing_ok=True)
            runner.invoke(app, ["sync"])


# ---------------------------------------------------------------------------
# R3 — --fields / --format tsv
# ---------------------------------------------------------------------------


class TestFieldsAndTsv:
    def test_note_list_tsv(self, vault):
        result = runner.invoke(
            app, ["note", "list", "--all", "--fields", "id,word_count", "--format", "tsv"]
        )
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "id\tword_count"
        assert any(ln.startswith("long-note\t") for ln in lines[1:])

    def test_search_tsv(self, vault):
        result = runner.invoke(
            app, ["search", "lorem", "--fields", "id,title", "--format", "tsv"]
        )
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "id\ttitle"
        assert any(ln.startswith("long-note\tLong Note") for ln in lines[1:])

    def test_unknown_field_errors_with_available_list(self, vault):
        result = runner.invoke(
            app, ["note", "list", "--all", "--fields", "id,nope", "--format", "tsv"]
        )
        assert result.exit_code == 1
        assert "available:" in result.output

    def test_fields_projection_in_json(self, vault):
        result = runner.invoke(
            app, ["note", "list", "--all", "--fields", "id", "-j"]
        )
        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["data"][0].keys() == {"id"}


# ---------------------------------------------------------------------------
# R4 — escalation count + run artefact
# ---------------------------------------------------------------------------


class TestEscalationCount:
    def test_bare_integer(self, vault):
        from hyperresearch.core.escalation import enqueue
        from hyperresearch.core.vault import Vault

        v = Vault.discover()
        enqueue(v.db, "https://example.com/wall", "login_wall")
        result = runner.invoke(app, ["escalation", "count"])
        assert result.exit_code == 0
        assert result.output.strip().isdigit()

    def test_json(self, vault):
        result = runner.invoke(app, ["escalation", "count", "-j"])
        assert result.exit_code == 0
        assert isinstance(json.loads(result.output)["data"]["count"], int)


class TestRunArtefact:
    def _init_run(self, vault_dir: Path) -> str:
        result = runner.invoke(app, ["run", "init", "erg-test-run", "--profile", "light", "-j"])
        assert result.exit_code == 0
        return "erg-test-run"

    def test_summary_describes_json_shape(self, vault):
        tag = self._init_run(vault)
        run_dir = Path(vault) / "research" / "runs" / tag
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt-decomposition.json").write_text(
            json.dumps({"sub_questions": ["q1", "q2"], "pipeline_tier": "light"}), encoding="utf-8"
        )
        result = runner.invoke(app, ["run", "artefact", "decomposition", "--summary"])
        assert result.exit_code == 0
        assert "sub_questions: list[2]" in result.output
        assert "pipeline_tier: str" in result.output

    def test_dump_json_pretty(self, vault):
        tag = self._init_run(vault)
        run_dir = Path(vault) / "research" / "runs" / tag
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "polish-log.json").write_text('{"applied":[],"escalations":[]}', encoding="utf-8")
        result = runner.invoke(app, ["run", "artefact", "polish-log"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"applied": [], "escalations": []}

    def test_missing_artefact_errors_with_known_names(self, vault):
        self._init_run(vault)
        result = runner.invoke(app, ["run", "artefact", "not-a-thing"])
        assert result.exit_code == 1
        assert "Known names:" in result.output

    def test_traversal_refused(self, vault):
        self._init_run(vault)
        result = runner.invoke(app, ["run", "artefact", "../../secrets"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# R5 — duplicate fetch is a success
# ---------------------------------------------------------------------------


class TestDuplicateFetch:
    def _seed_source(self, url: str) -> str:
        from hyperresearch.core.vault import Vault

        runner.invoke(app, ["note", "new", "Existing Source", "--body", "already here"])
        runner.invoke(app, ["sync"])
        v = Vault.discover()
        v.db.execute(
            "INSERT OR IGNORE INTO sources (url, note_id, domain, fetched_at, provider, content_hash)"
            " VALUES (?, 'existing-source', 'example.com', '2026-01-01T00:00:00', 'test', 'x')",
            (url,),
        )
        v.db.commit()
        return "existing-source"

    def test_duplicate_is_ok_true_exit_zero(self, vault):
        self._seed_source("https://example.com/dup")
        result = runner.invoke(app, ["fetch", "https://example.com/dup", "-j"])
        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["ok"] is True
        assert doc["data"]["duplicate"] is True
        assert doc["data"]["note_id"] == "existing-source"

    def test_force_bypasses_duplicate_check(self, vault, monkeypatch):
        self._seed_source("https://example.com/dup-force")
        import hyperresearch.web.base as web_base

        captured: dict[str, object] = {}

        class FakeProv:
            name = "fake"

            def fetch(self, url, **kw):
                captured["url"] = url
                return web_base.WebResult(
                    url=url,
                    title="Fresh Page",
                    content="A substantial body of genuine article text. " * 40,
                )

        monkeypatch.setattr(web_base, "resolve_web_provider", lambda *a, **kw: FakeProv())
        result = runner.invoke(app, ["fetch", "https://example.com/dup-force", "--force", "-j"])
        assert result.exit_code == 0, result.output
        assert captured["url"] == "https://example.com/dup-force"
        assert json.loads(result.output)["data"].get("duplicate") is not True


class TestStaleSourceRows:
    """note rm must clean the sources row; fetch must not claim a duplicate
    hit on a row whose note no longer exists (found live during the smoke
    test: a deleted note's row made re-fetch return a dangling note_id)."""

    def test_note_rm_removes_sources_row(self, vault):
        self_url = "https://example.com/rm-dup"
        from hyperresearch.core.vault import Vault

        runner.invoke(app, ["note", "new", "Rm Source", "--body", "x", "--source", self_url])
        runner.invoke(app, ["sync"])
        v = Vault.discover()
        row = v.db.execute("SELECT note_id FROM sources WHERE url = ?", (self_url,)).fetchone()
        if row is None:
            # Sync does not seed sources for hand-created notes; seed directly.
            v.db.execute(
                "INSERT INTO sources (url, note_id, domain, fetched_at, provider, content_hash)"
                " VALUES (?, 'rm-source', 'example.com', '2026-01-01T00:00:00', 'test', 'x')",
                (self_url,),
            )
            v.db.commit()

        result = runner.invoke(app, ["note", "rm", "rm-source", "--force", "-j"])
        assert result.exit_code == 0
        payload = json.loads(result.output)["data"]
        assert payload["removed_source_urls"] == [self_url]
        row = v.db.execute("SELECT 1 FROM sources WHERE url = ?", (self_url,)).fetchone()
        assert row is None

    def test_fetch_ignores_dangling_source_row(self, vault, monkeypatch):
        import hyperresearch.web.base as web_base

        captured: dict[str, object] = {}

        class FakeProv:
            name = "fake"

            def fetch(self, url, **kw):
                captured["url"] = url
                return web_base.WebResult(
                    url=url,
                    title="Fresh Page",
                    content="A substantial body of genuine article text. " * 40,
                )

        monkeypatch.setattr(web_base, "resolve_web_provider", lambda *a, **kw: FakeProv())
        result = runner.invoke(app, ["fetch", "https://example.com/gone", "-j"])
        assert result.exit_code == 0, result.output
        assert captured["url"] == "https://example.com/gone"

        # Now delete the note (leaving the sources row via a second vault-less
        # path is covered by rm cleanup; here simulate the dangling state).
        from hyperresearch.core.vault import Vault

        v = Vault.discover()
        note_id = json.loads(result.output)["data"]["note_id"]
        v.db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        v.db.commit()

        result2 = runner.invoke(app, ["fetch", "https://example.com/gone", "-j"])
        assert result2.exit_code == 0, result2.output
        doc = json.loads(result2.output)
        assert doc["data"].get("duplicate") is not True
