"""P2-16 install-verb acceptance matrix (tests/test_cli/test_install.py).

Covers the piece's mission criteria through the registered root verb:

(a) FRESH-PROJECT — empty dir -> `install` -> exactly 15 agent files,
    19 skill dirs, plugin file, command file, marked AGENTS.md section,
    `.hyperresearch/` vault + SQLite DB; exit 0;
(b) GLOBAL — HOME/XDG redirected -> `--global` lands under the fake config
    root resolved exactly the way opencode resolves it (injectable via env);
    no per-project vault side effects;
(c) STEPS-ONLY — skills + command + AGENTS.md present; NO agents/, NO
    plugins/, NO vault;
(d) REINSTALL = NO-OP DIFF — second run reports all-unchanged counts and the
    managed trees are byte-for-byte AND mtime-for-mtime identical;
(e) PRUNE — stale `hyperresearch-browser-fetcher.md` agent, retired skill
    dir, and an old plugin name are removed; unrelated user files survive;
(f) PROFILE — `--profile smoke` re-renders knob-baked bytes (critic caps,
    time estimate) vs the default full gear and bakes overlay-assigned
    `model:` lines for exactly the assigned roles; unknown profiles fail
    cleanly with an UNKNOWN_PROFILE envelope before any artifact lands;
(g) UPGRADE — steps-only then a full install adds exactly the roster +
    plugin while the already-present steps stay unchanged.

Falsification hooks: each criterion asserts exact counts (not >=), the
idempotency proof compares sha256 + st_mtime_ns over every managed file (a
rewritten-but-identical file would fail on mtime), and the profile proof pins
specific knob strings that differ between gears.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.cli.install import opencode_config_root
from hyperresearch.core.opencode_install import AGENT_SPECS
from hyperresearch.core.opencode_plugin import PLUGIN_FILENAME
from hyperresearch.core.opencode_skills import COMMAND_NAME, SKILL_SPECS

runner = CliRunner()

# P5: the DEFAULT install renders the 15-file roster (repo lane OFF); the
# 16th member (hyperresearch-repo-analyst.md) appears only when the
# effective repo_source_lane is on. BASE_AGENT_FILES pins the default;
# lane-on tests assert the extra file explicitly.
_REPO_ANALYST_FILE = "hyperresearch-repo-analyst.md"
BASE_AGENT_FILES = frozenset(
    spec.filename for spec in AGENT_SPECS if spec.filename != _REPO_ANALYST_FILE
)
EXPECTED_AGENT_FILES = BASE_AGENT_FILES  # default (lane-off) contract
EXPECTED_SKILL_DIRS = frozenset(spec.name for spec in SKILL_SPECS)

MARKER_START = "<!-- hyperresearch:start -->"
MARKER_END = "<!-- hyperresearch:end -->"

DB_HEADER = b"SQLite format 3\x00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _install(*args: str) -> dict[str, Any]:
    """Invoke `hpr install ... -j`; assert rc 0 and return the data payload."""
    result = runner.invoke(app, ["install", *args, "--json"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    return envelope["data"]


def _snapshot(root: Path) -> dict[str, tuple[str, int]]:
    """sha256 + mtime_ns of every file under root, keyed by relative path."""
    snap: dict[str, tuple[str, int]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(root))
            snap[rel] = (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_mtime_ns,
            )
    return snap


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} lost its frontmatter"
    end = text.index("\n---\n", 3)
    meta = yaml.safe_load(text[len("---\n") : end])
    assert isinstance(meta, dict)
    return meta


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    """An empty target directory for a fresh project install."""
    target = tmp_path / "proj"
    target.mkdir()
    return target


# ---------------------------------------------------------------------------
# (a) FRESH-PROJECT matrix
# ---------------------------------------------------------------------------


class TestFreshProject:
    def test_exact_tree(self, proj: Path) -> None:
        _install(str(proj))
        oc = proj / ".opencode"

        agents_dir = oc / "agents"
        assert {p.name for p in agents_dir.iterdir()} == set(EXPECTED_AGENT_FILES)
        assert len(EXPECTED_AGENT_FILES) == 15

        skills_dir = oc / "skills"
        assert {p.name for p in skills_dir.iterdir()} == set(EXPECTED_SKILL_DIRS)
        assert len(EXPECTED_SKILL_DIRS) == 19
        for name in EXPECTED_SKILL_DIRS:
            assert (skills_dir / name / "SKILL.md").is_file(), name

        assert (oc / "plugins" / PLUGIN_FILENAME).is_file()
        assert (oc / "commands" / f"{COMMAND_NAME}.md").is_file()

        agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
        assert MARKER_START in agents_md
        assert MARKER_END in agents_md
        assert MARKER_START.index("<") < agents_md.index(MARKER_END)

    def test_vault_layout_and_sqlite_db(self, proj: Path) -> None:
        _install(str(proj))
        hr = proj / ".hyperresearch"
        assert hr.is_dir()
        assert (hr / "config.toml").is_file()
        assert (hr / "templates").is_dir()
        assert (hr / "exports").is_dir()
        db = hr / "hyperresearch.db"
        assert db.is_file()
        assert db.read_bytes()[:16] == DB_HEADER
        conn = sqlite3.connect(db)
        try:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            conn.close()
        assert "notes" in tables

    def test_envelope_counts_first_run(self, proj: Path) -> None:
        data = _install(str(proj))
        assert data["mode"] == "project"
        assert data["profile"] == "full"
        assert data["vault"] == {"path": str(proj), "state": "created"}
        assert data["agents"] == {"written": 15, "unchanged": 0, "pruned": 0}
        assert data["skills"] == {"written": 19, "unchanged": 0, "pruned": 0}
        assert data["plugin"] == {"written": 1, "unchanged": 0, "pruned": 0}
        assert data["command"] == {"written": 1, "unchanged": 0, "pruned": 0}
        assert data["agents_md"] == {"written": 1, "unchanged": 0, "pruned": 0}
        assert data["pruned_paths"] == []

    def test_existing_vault_is_never_clobbered(self, proj: Path) -> None:
        _install(str(proj))  # creates vault + artifacts
        cfg = proj / ".hyperresearch" / "config.toml"
        cfg.write_text(
            cfg.read_text(encoding="utf-8").replace(
                '[pipeline]\nprofile = "full"', '[pipeline]\nprofile = "smoke"'
            ),
            encoding="utf-8",
        )
        custom = proj / "research" / "notes" / "keep-me.md"
        custom.write_text("user content\n", encoding="utf-8")

        data = _install(str(proj))
        assert data["vault"] == {"path": str(proj), "state": "existing"}
        # The tuned gear survives (config NOT rewritten to defaults)…
        assert 'profile = "smoke"' in cfg.read_text(encoding="utf-8")
        assert custom.read_text(encoding="utf-8") == "user content\n"
        # …and drives the render exactly like `--profile smoke` would.
        router = (
            proj / ".opencode" / "skills" / "hyperresearch" / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert 'rendered from profile "smoke"' in router


# ---------------------------------------------------------------------------
# (b) GLOBAL matrix — injectable config-root resolution
# ---------------------------------------------------------------------------


class TestGlobalInstall:
    def test_config_root_resolution_mirrors_opencode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        assert opencode_config_root() == tmp_path / "xdg" / "opencode"

        monkeypatch.delenv("XDG_CONFIG_HOME")
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        assert opencode_config_root() == tmp_path / "home" / ".config" / "opencode"

    def test_global_lands_under_fake_config_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        xdg = tmp_path / "xdg"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        cwd = tmp_path / "some-project"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

        data = _install("--global")
        root = xdg / "opencode"
        assert data["mode"] == "global"
        assert data["target"] == str(root)
        assert data["vault"] is None

        assert {p.name for p in (root / "agents").iterdir()} == set(EXPECTED_AGENT_FILES)
        assert {p.name for p in (root / "skills").iterdir()} == set(EXPECTED_SKILL_DIRS)
        assert (root / "plugins" / PLUGIN_FILENAME).is_file()
        assert (root / "commands" / f"{COMMAND_NAME}.md").is_file()
        assert MARKER_START in (root / "AGENTS.md").read_text(encoding="utf-8")

        # Global installs create no per-project state.
        assert not (cwd / ".hyperresearch").exists()
        assert not (cwd / ".opencode").exists()
        assert not (tmp_path / "home" / ".hyperresearch").exists()


# ---------------------------------------------------------------------------
# (c) STEPS-ONLY matrix
# ---------------------------------------------------------------------------


class TestStepsOnly:
    def test_skills_command_agentsmd_only(self, proj: Path) -> None:
        data = _install("--steps-only", str(proj))
        oc = proj / ".opencode"

        assert data["mode"] == "steps-only"
        assert {p.name for p in (oc / "skills").iterdir()} == set(EXPECTED_SKILL_DIRS)
        assert (oc / "commands" / f"{COMMAND_NAME}.md").is_file()
        assert MARKER_START in (proj / "AGENTS.md").read_text(encoding="utf-8")

        assert not (oc / "agents").exists()
        assert not (oc / "plugins").exists()
        assert not (proj / ".hyperresearch").exists()

        assert data["agents"] == {"written": 0, "unchanged": 0, "pruned": 0}
        assert data["plugin"] == {"written": 0, "unchanged": 0, "pruned": 0}
        assert data["skills"]["written"] == 19
        assert data["command"]["written"] == 1
        assert data["agents_md"]["written"] == 1


# ---------------------------------------------------------------------------
# (d) REINSTALL = NO-OP DIFF
# ---------------------------------------------------------------------------


class TestReinstallNoOp:
    def test_second_run_writes_nothing_byte_or_mtime_level(self, proj: Path) -> None:
        _install(str(proj))  # first run

        oc = proj / ".opencode"
        before_oc = _snapshot(oc)
        agents_md = proj / "AGENTS.md"
        before_md = (hashlib.sha256(agents_md.read_bytes()).hexdigest(), agents_md.stat().st_mtime_ns)
        assert len(before_oc) == 15 + 19 + 1 + 1  # agents+skills+plugin+command

        data = _install(str(proj))  # second run

        assert data["agents"] == {"written": 0, "unchanged": 15, "pruned": 0}
        assert data["skills"] == {"written": 0, "unchanged": 19, "pruned": 0}
        assert data["plugin"] == {"written": 0, "unchanged": 1, "pruned": 0}
        assert data["command"] == {"written": 0, "unchanged": 1, "pruned": 0}
        assert data["agents_md"] == {"written": 0, "unchanged": 1, "pruned": 0}
        assert data["vault"] == {"path": str(proj), "state": "existing"}

        # Byte-level mtree identity: same hashes AND same mtimes — any
        # rewritten-but-identical file would trip the mtime half.
        assert _snapshot(oc) == before_oc
        after_md = (hashlib.sha256(agents_md.read_bytes()).hexdigest(), agents_md.stat().st_mtime_ns)
        assert after_md == before_md

    def test_drifted_file_is_repaired_not_reported_unchanged(self, proj: Path) -> None:
        _install(str(proj))
        victim = proj / ".opencode" / "agents" / "hyperresearch-fetcher.md"
        pristine = victim.read_bytes()
        victim.write_text("tampered\n", encoding="utf-8")

        data = _install(str(proj))

        # Exactly the tampered file flips to written; everything else stays
        # unchanged — the counts track reality, they are not constants.
        assert data["agents"] == {"written": 1, "unchanged": 14, "pruned": 0}
        assert victim.read_bytes() == pristine


# ---------------------------------------------------------------------------
# (e) PRUNE
# ---------------------------------------------------------------------------


class TestPruneRetiredArtifacts:
    def test_retired_artifacts_pruned_user_files_survive(self, proj: Path) -> None:
        oc = proj / ".opencode"
        # Plant stale hyperresearch artifacts "from an older version".
        stale_agent = oc / "agents" / "hyperresearch-browser-fetcher.md"
        stale_agent.parent.mkdir(parents=True)
        stale_agent.write_text("---\nname: hyperresearch-browser-fetcher\n---\nstale\n")
        retired_skill = oc / "skills" / "hyperresearch-retired"
        retired_skill.mkdir(parents=True)
        (retired_skill / "SKILL.md").write_text("stale\n")
        (retired_skill / "extra.txt").write_text("stale\n")
        old_plugin = oc / "plugins" / "hyperresearch-lockdown-v0.js"
        old_plugin.parent.mkdir(parents=True)
        old_plugin.write_text("// old lockdown\n")
        # Unrelated user files must survive untouched.
        own_agent = oc / "agents" / "my-own-agent.md"
        own_agent.write_text("mine\n")
        user_skill = oc / "skills" / "user-skill"
        user_skill.mkdir()
        (user_skill / "SKILL.md").write_text("user's\n")
        foreign_plugin = oc / "plugins" / "my-tool.js"
        foreign_plugin.write_text("// mine\n")

        data = _install(str(proj))

        assert not stale_agent.exists()
        assert not retired_skill.exists()
        assert not old_plugin.exists()
        assert own_agent.read_text(encoding="utf-8") == "mine\n"
        assert (user_skill / "SKILL.md").read_text(encoding="utf-8") == "user's\n"
        assert foreign_plugin.read_text(encoding="utf-8") == "// mine\n"

        assert data["agents"]["pruned"] == 1
        assert data["skills"]["pruned"] == 1
        assert data["plugin"]["pruned"] == 1
        assert len(data["pruned_paths"]) == 3

        # Final roster shape: exactly the current 15 + the untouched user file.
        agent_names = {p.name for p in (oc / "agents").iterdir()}
        assert agent_names == set(EXPECTED_AGENT_FILES) | {"my-own-agent.md"}

    def test_repeated_install_does_not_resurrect_stale_artifacts(self, proj: Path) -> None:
        oc = proj / ".opencode"
        stale = oc / "agents" / "hyperresearch-browser-fetcher.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale\n")

        _install(str(proj))
        assert not stale.exists()
        # A later run finds nothing left to prune.
        data = _install(str(proj))
        assert data["pruned_paths"] == []


# ---------------------------------------------------------------------------
# (f) PROFILE
# ---------------------------------------------------------------------------


class TestProfileRerender:
    def test_smoke_gear_changes_knob_baked_bytes(self, proj: Path) -> None:
        _install(str(proj))  # default full gear

        skills = proj / ".opencode" / "skills"
        agents = proj / ".opencode" / "agents"
        router_full = (skills / "hyperresearch" / "SKILL.md").read_text(encoding="utf-8")
        critic_full = (agents / "hyperresearch-dialectic-critic.md").read_text(encoding="utf-8")
        investigator_full = (agents / "hyperresearch-depth-investigator.md").read_text(
            encoding="utf-8"
        )
        assert 'rendered from profile "full"' in router_full
        assert "~1.5–2.5 hours" in router_full
        assert "At most 12 findings." in critic_full
        assert "(default 10 if" in investigator_full

        data = _install("--profile", "smoke", str(proj))

        router_smoke = (skills / "hyperresearch" / "SKILL.md").read_text(encoding="utf-8")
        critic_smoke = (agents / "hyperresearch-dialectic-critic.md").read_text(encoding="utf-8")
        investigator_smoke = (agents / "hyperresearch-depth-investigator.md").read_text(
            encoding="utf-8"
        )
        assert 'rendered from profile "smoke"' in router_smoke
        assert "~10 min" in router_smoke
        assert "At most 4 findings." in critic_smoke
        assert "(default 2 if" in investigator_smoke
        assert data["profile"] == "smoke"
        # Every roster/skill file drifted (provenance header carries the gear),
        # so the re-render rewrote them all.
        assert data["agents"] == {"written": 15, "unchanged": 0, "pruned": 0}
        assert data["skills"]["written"] == 19

    def test_profile_overlay_models_bake_into_frontmatter_exactly(self, proj: Path) -> None:
        _install(str(proj))
        cfg = proj / ".hyperresearch" / "config.toml"
        cfg.write_text(
            cfg.read_text(encoding="utf-8")
            + '\n[profile.smoke]\nmodels = { fetcher = "openai/gpt-5-nano" }\n',
            encoding="utf-8",
        )

        _install("--profile", "smoke", str(proj))

        agents = proj / ".opencode" / "agents"
        fetcher_meta = _frontmatter(agents / "hyperresearch-fetcher.md")
        assert fetcher_meta.get("model") == "openai/gpt-5-nano"
        # Roles the overlay leaves unset keep empty-inherit (model omitted).
        for name in ("hyperresearch-patcher.md", "hyperresearch-synthesizer.md"):
            meta = _frontmatter(agents / name)
            assert "model" not in meta, name

    def test_unknown_profile_fails_cleanly_before_rendering(self, proj: Path) -> None:
        result = runner.invoke(app, ["install", "--profile", "does-not-exist", str(proj), "--json"])
        assert result.exit_code == 1
        envelope = json.loads(result.output)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "UNKNOWN_PROFILE"
        assert "unknown profile 'does-not-exist'" in envelope["error"]

        # No artifact was rendered — the failure precedes the render step.
        assert not (proj / ".opencode").exists()
        assert not (proj / "AGENTS.md").exists()

    def test_unknown_profile_rich_mode_also_exits_one(self, proj: Path) -> None:
        result = runner.invoke(app, ["install", "--profile", "does-not-exist", str(proj)])
        assert result.exit_code == 1
        assert "unknown profile" in result.output


# ---------------------------------------------------------------------------
# P2-16 addendum — `hpr profile use <gear>` (opencode re-render, no core.hooks)
# ---------------------------------------------------------------------------


class TestProfileUseVerb:
    """`hpr profile use <gear>` must re-render OUR opencode artifacts.

    Live E2E found the verb crashing `ModuleNotFoundError:
    No module named 'hyperresearch.core.hooks'` — it invoked upstream's Claude
    installer. The retargeted verb renders agents + skills from the resolved
    profile (plugin is gear-independent and stays untouched), keeps the
    envelope keys (gear/description/sources/time_estimate/rerendered) with
    manifest-style counts under ``rerendered``, and keeps the human
    "Gear switched:" line.
    """

    def test_use_smoke_rerenders_opencode_artifacts_and_persists_gear(
        self, proj: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(str(proj))  # default full gear baked into every file
        agents = proj / ".opencode" / "agents"
        skills = proj / ".opencode" / "skills"
        plugin = proj / ".opencode" / "plugins" / PLUGIN_FILENAME

        critic_full = (agents / "hyperresearch-dialectic-critic.md").read_text(encoding="utf-8")
        router_full = (skills / "hyperresearch" / "SKILL.md").read_text(encoding="utf-8")
        assert "At most 12 findings." in critic_full
        assert "~1.5–2.5 hours" in router_full

        plugin_before = (plugin.read_bytes(), plugin.stat().st_mtime_ns)

        monkeypatch.chdir(proj)
        result = runner.invoke(app, ["profile", "use", "smoke", "--json"])
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["ok"] is True
        data = envelope["data"]

        # Output contract preserved: same envelope keys, manifest-style counts.
        assert set(data) == {"gear", "description", "sources", "time_estimate", "rerendered"}
        assert data["gear"] == "smoke"
        assert data["sources"] == [8, 12]
        assert data["time_estimate"] == "~10 min"
        assert data["rerendered"] == {
            "agents": {"written": 15, "unchanged": 0},
            "skills": {"written": 19, "unchanged": 0},
        }

        # Agent files re-baked with smoke numbers (changed vs full).
        critic_smoke = (agents / "hyperresearch-dialectic-critic.md").read_text(encoding="utf-8")
        assert "At most 4 findings." in critic_smoke
        assert "At most 12 findings." not in critic_smoke
        assert "(default 2 if" in (agents / "hyperresearch-depth-investigator.md").read_text(
            encoding="utf-8"
        )

        # Skill files consistently re-rendered from the new gear…
        router_smoke = (skills / "hyperresearch" / "SKILL.md").read_text(encoding="utf-8")
        assert 'rendered from profile "smoke"' in router_smoke
        assert "~10 min" in router_smoke

        # …and the choice persisted into the vault config.
        assert 'profile = "smoke"' in (proj / ".hyperresearch" / "config.toml").read_text(
            encoding="utf-8"
        )

        # Plugin untouched (gear-independent).
        assert (plugin.read_bytes(), plugin.stat().st_mtime_ns) == plugin_before

        # Re-rendering the SAME gear is a full no-op: zero writes, sha256 AND
        # mtime stable over every skill file (byte-stability proof).
        skills_snap = _snapshot(skills)
        result2 = runner.invoke(app, ["profile", "use", "smoke", "--json"])
        assert result2.exit_code == 0, result2.output
        data2 = json.loads(result2.output)["data"]
        assert data2["rerendered"] == {
            "agents": {"written": 0, "unchanged": 15},
            "skills": {"written": 0, "unchanged": 19},
        }
        assert _snapshot(skills) == skills_snap

    def test_falsifier_pre_fix_import_raises_post_fix_verb_works(
        self, proj: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The defect pinned on both sides.

        Pre-fix (live E2E failure recorded before the fix):

            File ".../cli/profile_cmd.py:160 in profile_use
              from hyperresearch.core.hooks import install_hooks
            ModuleNotFoundError: No module named 'hyperresearch.core.hooks'

        First half proves the module really is absent; second half proves the
        verb now completes on a real install. Together they falsify any
        reintroduction of the dependency into this CLI path.
        """
        with pytest.raises(ModuleNotFoundError) as excinfo:
            from hyperresearch.core.hooks import install_hooks  # noqa: F401

        assert str(excinfo.value) == "No module named 'hyperresearch.core.hooks'"

        _install(str(proj))
        monkeypatch.chdir(proj)
        result = runner.invoke(app, ["profile", "use", "premier", "--json"])
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["ok"] is True
        rerendered = envelope["data"]["rerendered"]
        assert rerendered["agents"]["written"] + rerendered["agents"]["unchanged"] == 15
        assert rerendered["skills"]["written"] + rerendered["skills"]["unchanged"] == 19

    def test_unknown_gear_still_fails_cleanly_without_mutating(
        self, proj: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(str(proj))
        cfg = proj / ".hyperresearch" / "config.toml"
        cfg_before = cfg.read_text(encoding="utf-8")
        agents_snap = _snapshot(proj / ".opencode" / "agents")

        monkeypatch.chdir(proj)
        result = runner.invoke(app, ["profile", "use", "does-not-exist", "--json"])
        assert result.exit_code == 1
        envelope = json.loads(result.output)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "UNKNOWN_PROFILE"
        assert "unknown profile 'does-not-exist'" in envelope["error"]

        # No side effects: gear not persisted, artifacts byte+mtime identical.
        assert cfg.read_text(encoding="utf-8") == cfg_before
        assert _snapshot(proj / ".opencode" / "agents") == agents_snap

    def test_human_output_keeps_gear_switched_line(
        self, proj: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(str(proj))
        monkeypatch.chdir(proj)
        result = runner.invoke(app, ["profile", "use", "smoke"])
        assert result.exit_code == 0, result.output
        assert "Gear switched:" in result.output
        assert "re-rendered 34 skill/agent file(s)" in result.output


# ---------------------------------------------------------------------------
# (g) steps-only -> full upgrade
# ---------------------------------------------------------------------------


class TestStepsOnlyToFullUpgrade:
    def test_upgrade_adds_roster_and_plugin_keeps_steps(self, proj: Path) -> None:
        _install("--steps-only", str(proj))
        assert not ((proj / ".opencode") / "agents").exists()

        data = _install(str(proj))
        oc = proj / ".opencode"

        assert {p.name for p in (oc / "agents").iterdir()} == set(EXPECTED_AGENT_FILES)
        assert (oc / "plugins" / PLUGIN_FILENAME).is_file()

        assert data["agents"] == {"written": 15, "unchanged": 0, "pruned": 0}
        assert data["plugin"] == {"written": 1, "unchanged": 0, "pruned": 0}
        # The steps shipped by --steps-only were rendered from the same gear
        # and inputs, so the full install finds them byte-identical.
        assert data["skills"] == {"written": 0, "unchanged": 19, "pruned": 0}
        assert data["command"] == {"written": 0, "unchanged": 1, "pruned": 0}
        assert data["agents_md"] == {"written": 0, "unchanged": 1, "pruned": 0}


# ---------------------------------------------------------------------------
# Rich (non-JSON) mode wiring
# ---------------------------------------------------------------------------


def test_rich_mode_reports_namespaces(proj: Path) -> None:
    result = runner.invoke(app, ["install", str(proj)])
    assert result.exit_code == 0, result.output
    assert "Installed hyperresearch:" in result.output
    assert "Agents: +15 =0 -0 pruned" in result.output
    assert "Skills: +19 =0 -0 pruned" in result.output
    assert "Vault created:" in result.output
    assert "/hyperresearch <query>" in result.output
