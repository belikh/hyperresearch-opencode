"""P5 install-side tests: the conditional 16th agent + repo-lane threading.

Covers the install half of the P5 piece for the AGENT roster:

(a) DEFAULT — a fresh install (repo lane off) renders exactly the 15-file
    pre-P5 roster; hyperresearch-repo-analyst.md is absent;
(b) LANE ON — `[web] repo_source_lane = true` bakes the 16th agent file
    in, byte-identical to the frozen agent golden; the other 15 files are
    byte-identical to a lane-off render;
(c) LANE OFF AGAIN — turning the flag off after a lane-on install PRUNES
    the repo-analyst file (the keep-set derives from the rendered manifest,
    not the static spec list);
(d) PROFILE OVERLAY — a `[profile.<name>] repo_source_lane = true` overlay
    alone (global flag off) enables the 16th file when that profile is
    the installed gear;
(e) GOLDEN — the lane-on repo-analyst bytes match the frozen golden.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hyperresearch.cli import app

runner = CliRunner()

_REPO_ANALYST_FILE = "hyperresearch-repo-analyst.md"
_GOLDEN = (
    Path(__file__).parent.parent
    / "fixtures"
    / "agent_goldens_opencode"
    / _REPO_ANALYST_FILE
)


def _install(target: str) -> object:
    result = runner.invoke(app, ["install", target, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _agent_files(root: Path) -> set[str]:
    return {p.name for p in (root / ".opencode" / "agents").iterdir()}


# ---------------------------------------------------------------------------
# (a) Default: 15 files, no repo-analyst
# ---------------------------------------------------------------------------


def test_default_install_has_no_repo_analyst(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    _install(str(proj))
    files = _agent_files(proj)
    assert _REPO_ANALYST_FILE not in files
    assert len(files) == 15


# ---------------------------------------------------------------------------
# (b) Lane on: 16th file appears, others untouched
# ---------------------------------------------------------------------------


def _init_vault_with_flag(root: Path, *, flag: bool) -> None:
    from hyperresearch.core.vault import Vault

    vault = Vault.init(root, name="t")
    vault.config.web_repo_source_lane = flag
    vault.config.save(vault.config_path)


def test_lane_on_installs_repo_analyst(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    _init_vault_with_flag(proj, flag=True)
    _install(str(proj))
    files = _agent_files(proj)
    assert _REPO_ANALYST_FILE in files
    assert len(files) == 16


def test_lane_on_other_agents_byte_identical(tmp_path: Path) -> None:
    """The 15 shared agent files render identically either way."""
    on = tmp_path / "on"
    off = tmp_path / "off"
    on.mkdir()
    off.mkdir()
    _init_vault_with_flag(on, flag=True)
    _install(str(on))
    _install(str(off))

    on_dir = on / ".opencode" / "agents"
    off_dir = off / ".opencode" / "agents"
    for name in _agent_files(off):
        assert (
            (on_dir / name).read_text(encoding="utf-8")
            == (off_dir / name).read_text(encoding="utf-8")
        ), f"shared agent drifted: {name}"


def test_lane_on_matches_frozen_golden(tmp_path: Path) -> None:
    """The installed repo-analyst body matches the frozen golden modulo the
    hpr_path substitution (install resolves the real executable path; the
    frozen golden carries the default bare name — the same two-contract
    split as every other agent file). The test substitutes install's
    resolved path back to the golden's form and byte-compares.
    """
    from hyperresearch.core.agent_docs import _resolve_executable

    proj = tmp_path / "proj"
    proj.mkdir()
    _init_vault_with_flag(proj, flag=True)
    _install(str(proj))
    rendered = (proj / ".opencode" / "agents" / _REPO_ANALYST_FILE).read_text(
        encoding="utf-8"
    )
    golden = _GOLDEN.read_text(encoding="utf-8")
    resolved = _resolve_executable().replace("\\", "/")
    normalised = rendered.replace(resolved, "hyperresearch")
    assert normalised == golden


# ---------------------------------------------------------------------------
# (c) Lane on then off: the file is pruned
# ---------------------------------------------------------------------------


def test_lane_off_prunes_repo_analyst(tmp_path: Path) -> None:
    from hyperresearch.core.config import VaultConfig
    from hyperresearch.core.vault import Vault

    proj = tmp_path / "proj"
    proj.mkdir()
    vault = Vault.init(proj, name="t")

    # on
    vault.config.web_repo_source_lane = True
    vault.config.save(vault.config_path)
    _install(str(proj))
    assert _REPO_ANALYST_FILE in _agent_files(proj)

    # off
    cfg = VaultConfig.load(vault.config_path)
    cfg.web_repo_source_lane = False
    cfg.save(vault.config_path)
    data = _install(str(proj))
    assert _REPO_ANALYST_FILE not in _agent_files(proj)
    # and the prune is reported under data.pruned_paths
    inner = data.get("data", data)
    pruned_names = [str(p).rsplit("/", 1)[-1] for p in inner.get("pruned_paths", [])]
    assert _REPO_ANALYST_FILE in pruned_names


# ---------------------------------------------------------------------------
# (d) Profile overlay alone enables the lane
# ---------------------------------------------------------------------------


def test_profile_overlay_alone_enables_repo_analyst(tmp_path: Path) -> None:
    from hyperresearch.core.vault import Vault

    proj = tmp_path / "proj"
    proj.mkdir()
    vault = Vault.init(proj, name="t")
    vault.config_path.write_text(
        vault.config_path.read_text()
        + '\n[profile.repoheavy]\nextends = "full"\nrepo_source_lane = true\n'
    )
    vault.config.pipeline_profile = "repoheavy"
    vault.config.save(vault.config_path)

    _install(str(proj))
    assert _REPO_ANALYST_FILE in _agent_files(proj)


def test_profile_overlay_off_keeps_fifteen(tmp_path: Path) -> None:
    from hyperresearch.core.vault import Vault

    proj = tmp_path / "proj"
    proj.mkdir()
    vault = Vault.init(proj, name="t")
    vault.config_path.write_text(
        vault.config_path.read_text()
        + '\n[profile.repoheavy]\nextends = "full"\nrepo_source_lane = false\n'
    )
    vault.config.pipeline_profile = "repoheavy"
    vault.config.save(vault.config_path)

    _install(str(proj))
    assert _REPO_ANALYST_FILE not in _agent_files(proj)
