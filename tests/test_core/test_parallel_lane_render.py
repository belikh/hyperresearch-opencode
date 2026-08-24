"""P4-C conditional template-sentence rendering (tests/test_core/test_parallel_lane_render.py).

Covers the render half of the piece:

(a) DEFAULT-STATE BYTE IDENTITY — rendering with no kwarg, or with
    parallel_lane=False, reproduces the frozen pre-P4-C goldens EXACTLY for
    both affected templates; the other 18 skills + 14 agents match their
    goldens too (the existing golden modules re-prove this chain-wide;
    here it pins the two touched templates explicitly);
(b) LANE ON — width-sweep skill and hyperresearch-fetcher agent each gain
    EXACTLY ONE occurrence of their lane sentence, byte-matching the new
    *lane_on fixtures; every other skill/agent file stays byte-identical to
    its default golden;
(c) SUBSTITUTION CONVENTIONS (FIX-F1) — each target's sentence follows that
    file's OWN convention: the width-sweep skill carries `$HPR` LITERALLY
    (the file spells every command `$HPR`; no `{hpr_path}` anywhere), while
    the agent gets `{hpr_path}` substituted like its own command examples.
    The two sentences are separately worded per role (FIX-F6: orchestrator
    context says "per atomic item"; fetcher context says "keywords from
    your assignment");
(d) GUARDS — a missing anchor is a renderer bug and must raise loudly;
(e) INSTALL THREADING — `hpr install` derives the flag from the vault's
    config.toml: enabled bakes the sentence into both installed templates,
    disabled leaves them clean.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.core.config import VaultConfig
from hyperresearch.core.opencode_install import (
    AGENT_SPECS,
    PARALLEL_SEARCH_LANE_SENTENCE,
    OpencodeInstallError,
    render_agents,
)
from hyperresearch.core.opencode_skills import (
    _WIDTH_SWEEP_LANE_SENTENCE,
    SKILL_SPECS,
    render_skills,
)
from hyperresearch.core.profiles import ModelMap, resolve_profile

runner = CliRunner()

SKILL_GOLDENS_DIR = Path(__file__).parent.parent / "fixtures" / "skill_goldens"
AGENT_GOLDENS_DIR = Path(__file__).parent.parent / "fixtures" / "agent_goldens_opencode"
SKILL_LANE_ON_GOLDEN = (
    Path(__file__).parent.parent
    / "fixtures" / "skill_goldens_lane_on" / "hyperresearch-2-width-sweep.md"
)
AGENT_LANE_ON_GOLDEN = (
    Path(__file__).parent.parent
    / "fixtures" / "agent_goldens_opencode_lane_on" / "hyperresearch-fetcher.md"
)

PROFILE = resolve_profile("full")
AFFECTED_SKILL = "hyperresearch-2-width-sweep"
AFFECTED_AGENT = "hyperresearch-fetcher.md"


def _render_skills(tmp_path: Path, *, lane: bool) -> Path:
    skills_dir = tmp_path / ("skills-lane" if lane else "skills-off")
    render_skills(skills_dir, PROFILE, parallel_lane=lane)
    return skills_dir


def _render_agents(tmp_path: Path, *, lane: bool) -> Path:
    agents_dir = tmp_path / ("agents-lane" if lane else "agents-off")
    render_agents(agents_dir, PROFILE, ModelMap(), parallel_lane=lane)
    return agents_dir


# ---------------------------------------------------------------------------
# (a) default-state byte identity
# ---------------------------------------------------------------------------


class TestDefaultStateByteIdentity:
    def test_width_sweep_default_equals_frozen_golden(self, tmp_path: Path) -> None:
        got = (_render_skills(tmp_path, lane=False) / AFFECTED_SKILL / "SKILL.md").read_bytes()
        assert got == (SKILL_GOLDENS_DIR / f"{AFFECTED_SKILL}.md").read_bytes()

    def test_fetcher_default_equals_frozen_golden(self, tmp_path: Path) -> None:
        got = (_render_agents(tmp_path, lane=False) / AFFECTED_AGENT).read_bytes()
        assert got == (AGENT_GOLDENS_DIR / AFFECTED_AGENT).read_bytes()

    def test_omitting_the_kwarg_equals_passing_false(self, tmp_path: Path) -> None:
        """The kwarg defaults to False AND the default path is the same code
        path — omission and explicit False must be indistinguishable."""
        skills_a = tmp_path / "sa"
        skills_b = tmp_path / "sb"
        render_skills(skills_a, PROFILE)
        render_skills(skills_b, PROFILE, parallel_lane=False)
        for spec in SKILL_SPECS:
            a = (skills_a / spec.name / "SKILL.md").read_bytes()
            b = (skills_b / spec.name / "SKILL.md").read_bytes()
            assert a == b, spec.name

        agents_a = tmp_path / "aa"
        agents_b = tmp_path / "ab"
        render_agents(agents_a, PROFILE, ModelMap())
        render_agents(agents_b, PROFILE, ModelMap(), parallel_lane=False)
        for spec in AGENT_SPECS:
            a = (agents_a / spec.filename).read_bytes()
            b = (agents_b / spec.filename).read_bytes()
            assert a == b, spec.filename


# ---------------------------------------------------------------------------
# (b) lane on — one sentence, frozen bytes, zero collateral drift
# ---------------------------------------------------------------------------


class TestLaneOnRenders:
    def test_width_sweep_matches_lane_on_fixture_exactly(self, tmp_path: Path) -> None:
        got = (_render_skills(tmp_path, lane=True) / AFFECTED_SKILL / "SKILL.md").read_bytes()
        assert got == SKILL_LANE_ON_GOLDEN.read_bytes()

    def test_fetcher_matches_lane_on_fixture_exactly(self, tmp_path: Path) -> None:
        got = (_render_agents(tmp_path, lane=True) / AFFECTED_AGENT).read_bytes()
        assert got == AGENT_LANE_ON_GOLDEN.read_bytes()

    def test_sentence_appears_exactly_once_in_each_target(
        self, tmp_path: Path
    ) -> None:
        skill_text = (
            _render_skills(tmp_path, lane=True) / AFFECTED_SKILL / "SKILL.md"
        ).read_text(encoding="utf-8")
        agent_text = (
            _render_agents(tmp_path, lane=True) / AFFECTED_AGENT
        ).read_text(encoding="utf-8")
        # The bold lead-in is part of the shared constant, so counting it
        # counts the sentence.
        assert skill_text.count("**Parallel search lane:**") == 1
        assert agent_text.count("**Parallel search lane:**") == 1

    def test_other_skills_stay_byte_identical_to_default_goldens(
        self, tmp_path: Path
    ) -> None:
        skills_dir = _render_skills(tmp_path, lane=True)
        for spec in SKILL_SPECS:
            if spec.name == AFFECTED_SKILL:
                continue
            got = (skills_dir / spec.name / "SKILL.md").read_bytes()
            golden = (SKILL_GOLDENS_DIR / f"{spec.name}.md").read_bytes()
            assert got == golden, f"{spec.name} drifted under parallel_lane=True"

    def test_other_agents_stay_byte_identical_to_default_goldens(
        self, tmp_path: Path
    ) -> None:
        agents_dir = _render_agents(tmp_path, lane=True)
        for spec in AGENT_SPECS:
            if spec.filename == AFFECTED_AGENT:
                continue
            got = (agents_dir / spec.filename).read_bytes()
            golden = (AGENT_GOLDENS_DIR / spec.filename).read_bytes()
            assert got == golden, f"{spec.filename} drifted under parallel_lane=True"

    def test_lane_off_vs_on_diff_is_exactly_the_sentence_block(
        self, tmp_path: Path
    ) -> None:
        """The ONLY difference between off/on renders is the injected block —
        nothing else may move."""
        off = (_render_skills(tmp_path, lane=False) / AFFECTED_SKILL / "SKILL.md").read_text(
            encoding="utf-8"
        )
        on = (_render_skills(tmp_path, lane=True) / AFFECTED_SKILL / "SKILL.md").read_text(
            encoding="utf-8"
        )
        block = "\n\n   " + _WIDTH_SWEEP_LANE_SENTENCE
        assert on == off.replace("before deduplication for `full` tier.",
                                 "before deduplication for `full` tier." + block)

        off_a = (_render_agents(tmp_path, lane=False) / AFFECTED_AGENT).read_text(
            encoding="utf-8"
        )
        on_a = (_render_agents(tmp_path, lane=True) / AFFECTED_AGENT).read_text(
            encoding="utf-8"
        )
        anchor = "## Untrusted content policy — read before summarizing any fetched page"
        injected = (
            PARALLEL_SEARCH_LANE_SENTENCE.replace("{hpr_path}", "hyperresearch")
            + "\n\n"
            + anchor
        )
        assert on_a == off_a.replace(anchor, injected)


# ---------------------------------------------------------------------------
# (c) substitution conventions
# ---------------------------------------------------------------------------


class TestSubstitutionConventions:
    def test_skill_uses_dollar_hpr_per_its_own_file_convention(
        self, tmp_path: Path
    ) -> None:
        """FIX-F1: the width-sweep file spells its CLI `$HPR` everywhere
        (12x in the bundled source, 13x rendered by default once the
        degraded-mode clause adds its `$HPR fetch-batch`, 14x with the lane
        sentence — FIX-L3 corrected count), so the injected sentence uses
        `$HPR` LITERALLY — no substitution, no `{hpr_path}` anywhere in the
        rendered bytes."""
        text = (
            _render_skills(tmp_path, lane=True) / AFFECTED_SKILL / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert "$HPR search-web <atomic item keywords>" in text
        assert "{hpr_path}" not in text

    def test_agent_substitutes_hpr_path_like_its_own_examples(
        self, tmp_path: Path
    ) -> None:
        text = (
            _render_agents(tmp_path, lane=True) / AFFECTED_AGENT
        ).read_text(encoding="utf-8")
        # FIX-L7: the snippet carries the file's standing Windows rule.
        assert (
            "PYTHONIOENCODING=utf-8 hyperresearch search-web "
            "<keywords from your assignment>" in text
        )
        assert "{hpr_path}" not in text.split("**Parallel search lane:**")[1].split("\n")[0]

    def test_agent_sentence_is_scout_and_report_never_fetch(
        self, tmp_path: Path
    ) -> None:
        """FIX-H1 (GAUNTLET r2/r3): the fetcher sentence licenses ONE up-front
        search-web query and ends at REPORTING candidates — it must never
        license fetching them, because that would bypass step 2.2/2.3 dedup
        + utility scoring. Exclusivity is SCOPED to discovering NEW candidate
        URLs beyond the assignment, and the constraint it exceptions out of
        is named as the spawn-time wave contract — not any in-file rule."""
        sentence = PARALLEL_SEARCH_LANE_SENTENCE.replace("{hpr_path}", "hyperresearch")
        assert "WITHOUT fetching them" in sentence
        assert "normal wave contract" in sentence
        assert "ONLY sanctioned exception" in sentence
        # GAUNTLET r3 FIX-H1 scoping pins: constraint source + scoped
        # exclusivity.
        assert (
            "discover new candidate URLs beyond your assigned URL list"
            in sentence
        )
        assert (
            "stay-within-your-assignment constraint of the wave contract "
            "you were spawned with" in sentence
        )
        # And the old fetch-it-yourself wording is gone for good.
        assert "fetch everything through your normal fetch path" not in sentence

    def test_agent_sentence_has_no_dangling_in_file_rule_reference(
        self, tmp_path: Path
    ) -> None:
        """GAUNTLET r3 FIX-H1: the sentence must not cite an in-file rule
        ("above") that isn't there — the no-fetcher-searches rule lives in
        width-sweep's SPAWN template text (a different artifact), and this
        rendered agent file instead licenses Phase 2 WebSearch for locating
        assigned targets. Neither the constant nor the lane-on render may
        carry a dangling reference."""
        sentence = PARALLEL_SEARCH_LANE_SENTENCE.replace("{hpr_path}", "hyperresearch")
        assert "rule above" not in sentence
        assert "no-fetcher-searches" not in sentence
        rendered = (
            _render_agents(tmp_path, lane=True) / AFFECTED_AGENT
        ).read_text(encoding="utf-8")
        assert "rule above" not in rendered
        # The scoping carve-out keeps Phase 2 outside the exclusivity claim.
        assert (
            "use WebSearch to locate it" in rendered
            and rendered.index("**Parallel search lane:**")
            < rendered.index("use WebSearch to locate it")
        )

    def test_each_target_embeds_its_own_constant_verbatim(
        self, tmp_path: Path
    ) -> None:
        skill_text = (
            _render_skills(tmp_path, lane=True) / AFFECTED_SKILL / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert _WIDTH_SWEEP_LANE_SENTENCE in skill_text
        agent_text = (
            _render_agents(tmp_path, lane=True) / AFFECTED_AGENT
        ).read_text(encoding="utf-8")
        assert PARALLEL_SEARCH_LANE_SENTENCE.replace("{hpr_path}", "hyperresearch") in (
            agent_text
        )


# ---------------------------------------------------------------------------
# (d) guards
# ---------------------------------------------------------------------------


def test_missing_skill_anchor_raises_instead_of_dropping() -> None:
    from hyperresearch.core.opencode_skills import _inject_lane_sentence_after

    with pytest.raises(OpencodeInstallError, match="anchor not found"):
        _inject_lane_sentence_after("no anchor here", "MISSING")


def test_missing_agent_anchor_raises_instead_of_dropping() -> None:
    from hyperresearch.core.opencode_install import (
        _FETCHER_LANE_ANCHOR,
        _inject_lane_sentence_before,
    )

    with pytest.raises(OpencodeInstallError, match="anchor not found"):
        _inject_lane_sentence_before("no anchor here", _FETCHER_LANE_ANCHOR, "hpr")


# ---------------------------------------------------------------------------
# (e) install threading
# ---------------------------------------------------------------------------


class TestInstallThreading:
    def _project_with_flag(self, tmp_path: Path, enabled: bool) -> Path:
        proj = tmp_path / ("on" if enabled else "off")
        result = runner.invoke(app, ["init", str(proj), "--name", "Lane Proj"])
        assert result.exit_code == 0, result.output
        cfg_path = proj / ".hyperresearch" / "config.toml"
        cfg = VaultConfig.load(cfg_path)
        cfg.web_parallel_search_lane = enabled
        cfg.save(cfg_path)
        return proj

    @pytest.mark.parametrize("enabled", [True, False], ids=["lane-on", "lane-off"])
    def test_install_bakes_sentence_iff_flag_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: bool
    ) -> None:
        # Pin the executable seam so the installed bytes are comparable to the
        # machine-independent fixtures (which bake the "hyperresearch"
        # default); the flag threading under test is orthogonal to path
        # resolution.
        monkeypatch.setattr(
            "hyperresearch.core.agent_docs._resolve_executable",
            lambda: "hyperresearch",
        )
        proj = self._project_with_flag(tmp_path, enabled)

        result = runner.invoke(app, ["install", str(proj), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["ok"] is True

        skill_text = (
            proj / ".opencode" / "skills" / AFFECTED_SKILL / "SKILL.md"
        ).read_text(encoding="utf-8")
        agent_text = (
            proj / ".opencode" / "agents" / AFFECTED_AGENT
        ).read_text(encoding="utf-8")

        if enabled:
            assert skill_text.count("**Parallel search lane:**") == 1
            assert agent_text.count("**Parallel search lane:**") == 1
            # The installed bytes are exactly the frozen goldens.
            assert (
                proj / ".opencode" / "skills" / AFFECTED_SKILL / "SKILL.md"
            ).read_bytes() == SKILL_LANE_ON_GOLDEN.read_bytes()
            assert (
                proj / ".opencode" / "agents" / AFFECTED_AGENT
            ).read_bytes() == AGENT_LANE_ON_GOLDEN.read_bytes()
        else:
            assert "**Parallel search lane:**" not in skill_text
            assert "**Parallel search lane:**" not in agent_text

    def test_install_bakes_sentence_when_profile_overlay_enables_with_config_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P4-C closure: `[profile.<gear>] parallel_search_lane = true` alone —
        the vault-global [web] flag still false — bakes the sentence, and the
        installed bytes are exactly the frozen lane-on goldens (the profile
        input ORs into the same render path, so on-by-profile is byte-equal to
        on-by-config)."""
        monkeypatch.setattr(
            "hyperresearch.core.agent_docs._resolve_executable",
            lambda: "hyperresearch",
        )
        proj = self._project_with_flag(tmp_path, False)
        cfg_path = proj / ".hyperresearch" / "config.toml"
        cfg_path.write_text(
            cfg_path.read_text(encoding="utf-8")
            + "\n[profile.full]\nparallel_search_lane = true\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["install", str(proj), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["ok"] is True

        skill_path = proj / ".opencode" / "skills" / AFFECTED_SKILL / "SKILL.md"
        agent_path = proj / ".opencode" / "agents" / AFFECTED_AGENT
        assert skill_path.read_text(encoding="utf-8").count(
            "**Parallel search lane:**"
        ) == 1
        assert agent_path.read_text(encoding="utf-8").count(
            "**Parallel search lane:**"
        ) == 1
        assert skill_path.read_bytes() == SKILL_LANE_ON_GOLDEN.read_bytes()
        assert agent_path.read_bytes() == AGENT_LANE_ON_GOLDEN.read_bytes()
