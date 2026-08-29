"""P5 closure: explicit --repo-lane / --parallel-lane install flags.

Global installs carry no vault config, so before these flags the lane
inputs were unreachable there — `install --global` could never bake the
Lens-E paragraph or render the 16th agent (discovered live on the
callisto rig 2026-08-29: a --global re-render wrote 15 agents and left
width-sweep byte-unchanged). The flags OR with the config-derived inputs
on project installs and are the ONLY input on global installs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.core.opencode_skills import _WIDTH_SWEEP_REPO_PARAGRAPH

runner = CliRunner()

_REPO_ANALYST_FILE = "hyperresearch-repo-analyst.md"
_LANE_PARAGRAPH_MARK = "Repository source lane (Lens E)"


def _install_global(xdg: Path, *extra: str) -> object:
    result = runner.invoke(app, ["install", "--global", *extra, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@pytest.fixture()
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated global config root — nothing touches the real rig."""
    root = tmp_path / "xdg"
    root.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return root / "opencode"


# ---------------------------------------------------------------------------
# Global installs
# ---------------------------------------------------------------------------


def test_global_default_renders_lane_off(xdg: Path) -> None:
    """No flag, no vault: the global default stays the pre-P5 15-agent set."""
    _install_global(xdg)
    agents = {p.name for p in (xdg / "agents").iterdir()}
    assert _REPO_ANALYST_FILE not in agents
    assert len([n for n in agents if n.startswith("hyperresearch-")]) == 15
    skill = (xdg / "skills" / "hyperresearch-2-width-sweep" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert _LANE_PARAGRAPH_MARK not in skill


def test_global_repo_lane_flag_renders_lane_on(xdg: Path) -> None:
    """--repo-lane is the ONLY lane input a global install has."""
    _install_global(xdg, "--repo-lane")
    agents = {p.name for p in (xdg / "agents").iterdir()}
    assert _REPO_ANALYST_FILE in agents
    skill = (xdg / "skills" / "hyperresearch-2-width-sweep" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert _LANE_PARAGRAPH_MARK in skill


def test_global_repo_lane_flag_turning_off_prunes(xdg: Path) -> None:
    """A follow-up --global render WITHOUT the flag prunes the 16th agent —
    the manifest-derived keep-set works on global installs too."""
    _install_global(xdg, "--repo-lane")
    assert _REPO_ANALYST_FILE in {p.name for p in (xdg / "agents").iterdir()}

    data = _install_global(xdg)
    agents = {p.name for p in (xdg / "agents").iterdir()}
    assert _REPO_ANALYST_FILE not in agents
    pruned = [Path(p).name for p in data.get("data", data).get("pruned_paths", [])]
    assert _REPO_ANALYST_FILE in pruned


def test_global_flags_independent(xdg: Path) -> None:
    """--parallel-lane alone must NOT bake the repo paragraph (and vice
    versa) — the two lanes inject only their own text."""
    _install_global(xdg, "--parallel-lane")
    skill = (xdg / "skills" / "hyperresearch-2-width-sweep" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Parallel search lane" in skill
    assert _LANE_PARAGRAPH_MARK not in skill
    agents = {p.name for p in (xdg / "agents").iterdir()}
    assert _REPO_ANALYST_FILE not in agents


def test_global_both_flags_bake_both(xdg: Path) -> None:
    _install_global(xdg, "--parallel-lane", "--repo-lane")
    skill = (xdg / "skills" / "hyperresearch-2-width-sweep" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Parallel search lane" in skill
    assert skill.count(_WIDTH_SWEEP_REPO_PARAGRAPH) == 1
    agents = {p.name for p in (xdg / "agents").iterdir()}
    assert _REPO_ANALYST_FILE in agents


# ---------------------------------------------------------------------------
# Project installs — flag ORs with the config input
# ---------------------------------------------------------------------------


def test_project_flag_or_overrides_off_config(tmp_path: Path) -> None:
    """Config off + --repo-lane = lane on (flag ORs in, never subtracts)."""
    from hyperresearch.core.vault import Vault

    proj = tmp_path / "proj"
    proj.mkdir()
    Vault.init(proj, name="t")
    result = runner.invoke(app, ["install", str(proj), "--repo-lane", "--json"])
    assert result.exit_code == 0, result.output
    agents = {p.name for p in (proj / ".opencode" / "agents").iterdir()}
    assert _REPO_ANALYST_FILE in agents
    skill = (
        proj / ".opencode" / "skills" / "hyperresearch-2-width-sweep" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert _LANE_PARAGRAPH_MARK in skill


def test_project_config_on_flag_absent_still_on(tmp_path: Path) -> None:
    """Config on + no flag = lane on — the flag never gate-keeps the config."""
    from hyperresearch.core.vault import Vault

    proj = tmp_path / "proj"
    proj.mkdir()
    vault = Vault.init(proj, name="t")
    vault.config.web_repo_source_lane = True
    vault.config.save(vault.config_path)
    result = runner.invoke(app, ["install", str(proj), "--json"])
    assert result.exit_code == 0, result.output
    agents = {p.name for p in (proj / ".opencode" / "agents").iterdir()}
    assert _REPO_ANALYST_FILE in agents
