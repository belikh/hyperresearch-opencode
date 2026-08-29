"""P5 closure: `config set/get/show` wiring for web.repo_source_lane.

The repo-lane verbs' LANE_DISABLED guidance names
``hpr config set web.repo_source_lane true`` as THE enablement path — this
module pins that the config verbs actually accept the key (the initial P5
landing missed the verb allowlists, discovered live while wiring the
jupiterOS vault on callisto 2026-08-29: the enable command errored
UNKNOWN_KEY).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app

runner = CliRunner()


@pytest.fixture()
def vault_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    result = runner.invoke(app, ["init", str(tmp_path / "kb"), "--name", "Repo Lane"])
    assert result.exit_code == 0, result.output
    root = tmp_path / "kb"
    monkeypatch.chdir(root)
    return root


class TestConfigSetRepoLane:
    def test_set_true_round_trips_through_the_verb(self, vault_dir: Path) -> None:
        result = runner.invoke(
            app, ["config", "set", "web.repo_source_lane", "true", "--json"]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["value"] is True

        # Persisted on disk — reload proves the TOML round-trip.
        result = runner.invoke(app, ["config", "get", "web.repo_source_lane", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["value"] is True

    def test_set_false_round_trips(self, vault_dir: Path) -> None:
        runner.invoke(app, ["config", "set", "web.repo_source_lane", "true"])
        result = runner.invoke(
            app, ["config", "set", "web.repo_source_lane", "false", "--json"]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["value"] is False

    def test_typo_value_fails_loudly_before_any_write(
        self, vault_dir: Path
    ) -> None:
        runner.invoke(app, ["config", "set", "web.repo_source_lane", "true"])
        result = runner.invoke(
            app, ["config", "set", "web.repo_source_lane", "blah", "--json"]
        )
        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "INVALID_VALUE"
        # The failed set left the prior value untouched.
        result = runner.invoke(app, ["config", "get", "web.repo_source_lane", "--json"])
        assert json.loads(result.stdout)["data"]["value"] is True

    def test_show_lists_the_flag(self, vault_dir: Path) -> None:
        result = runner.invoke(app, ["config", "show", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)["data"]
        assert data["web_repo_source_lane"] is False

    def test_get_unknown_lane_key_still_errors(self, vault_dir: Path) -> None:
        result = runner.invoke(app, ["config", "get", "web.nope_lane", "--json"])
        assert result.exit_code == 1
        assert json.loads(result.stdout)["error_code"] == "UNKNOWN_KEY"


class TestRepoVerbsEnableThroughConfig:
    """End-to-end: the enablement incantation the LANE_DISABLED error
    prescribes actually un-gates the `hpr repo` verbs."""

    def test_enable_incantation_opens_the_gate(self, vault_dir: Path) -> None:
        # Before: gate fires with the exact incantation in the message.
        gated = runner.invoke(app, ["repo", "map", ".", "--json"])
        assert gated.exit_code == 1
        assert "web.repo_source_lane" in gated.stdout

        # The prescribed incantation.
        enable = runner.invoke(
            app, ["config", "set", "web.repo_source_lane", "true", "--json"]
        )
        assert enable.exit_code == 0, enable.output

        # After: the gate passes (map proceeds to its own validation).
        opened = runner.invoke(app, ["repo", "map", ".", "--json"])
        assert opened.exit_code in (0, 1)  # empty-dir REPO_MAP_ERROR is fine
        assert "LANE_DISABLED" not in opened.stdout
