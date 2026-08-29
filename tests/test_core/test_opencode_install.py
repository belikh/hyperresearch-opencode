"""Behavioral tests for the opencode agent-file renderer (P2-13).

Covers the piece's acceptance criteria:

(a) exactly 15 agent files rendered, names ``hyperresearch-*.md`` matching
    ``^[a-z0-9]+(-[a-z0-9]+)*$``;
(b) frontmatter matrix per agent class — mode/hidden/model-omission-on-unset,
    tools deny-sets and permission denies exactly as decided in S0-3 (as
    amended by countersign F-CS2) plus the task allowlist for the one
    upstream-delegating role (S0-1);
(c) determinism — same inputs produce byte-identical files, and a second
    render into an already-rendered tree rewrites nothing;
(d) atomicity — an injected mid-render failure leaves no partial files;
(e) prompt-body goldens — rendered bodies match the frozen P1-7 fixtures for
    representative agents, per the P1-7 golden contract;
(f) installed-file goldens — every one of the 15 rendered files
    byte-matches frozen fixtures derived from LIVE upstream-installed output
    (upstream installer run into a scratch vault, countersign remediation
    X-2), closing the "fidelity could silently rot" hole; includes the X-1
    polish-auditor quirk pin (upstream's doubled ``- - `` scaffold bullets).

Falsification record: this module was written before
``src/hyperresearch/core/opencode_install.py`` existed; running it at that
point fails at collection with ImportError (see PORTING-NOTES.md §P2-13).
Countersign X-1 falsification: before the fix, the (f) goldens failed on
hyperresearch-polish-auditor.md only (14/15 matched) — the renderer
normalized upstream's doubled ``- - `` bullets to single bullets.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from hyperresearch.core.opencode_install import (
    AGENT_SPECS,
    SCAFFOLD_ONLY_SECTION_HEADERS,
    render_agents,
)
from hyperresearch.core.profiles import ModelMap, resolve_profile
from hyperresearch.core.render import build_render_context, render_prompt

GOLDEN_AGENTS_DIR = Path(__file__).parent.parent / "fixtures" / "golden_prompts" / "agents"
AGENT_GOLDENS_DIR = Path(__file__).parent.parent / "fixtures" / "agent_goldens_opencode"

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# P5: the DEFAULT render is the 15-file roster (repo lane OFF). The
# conditional 16th member (hyperresearch-repo-analyst) is pinned by
# tests/test_cli/test_install_repo_lane.py in both lane states — here the
# matrix covers exactly what a default install ships.
_REPO_ANALYST_STEM = "hyperresearch-repo-analyst"
EXPECTED_STEMS: frozenset[str] = frozenset(
    spec.filename.removesuffix(".md")
    for spec in AGENT_SPECS
    if spec.filename.removesuffix(".md") != _REPO_ANALYST_STEM
)

# S0-3 (as amended by countersign F-CS2): patcher/polish-auditor keep Edit
# (write denied); synthesizer denies {edit, bash}. Mission amendment P2-13:
# the tools deny-set for patcher/polish-auditor is EXACTLY {write: false}.
EXPECTED_TOOLS_DENY: dict[str, dict[str, bool]] = {
    "hyperresearch-patcher": {"write": False},
    "hyperresearch-polish-auditor": {"write": False},
    "hyperresearch-synthesizer": {"edit": False, "bash": False},
}

# Permission denies mirror the same sets; depth-investigator additionally
# carries the only upstream task delegation edge (investigator -> fetcher,
# S0-1). opencode evaluates the LAST matching rule, so "*" is emitted first.
EXPECTED_PERMISSION: dict[str, dict[str, Any]] = {
    "hyperresearch-patcher": {"write": "deny"},
    "hyperresearch-polish-auditor": {"write": "deny"},
    "hyperresearch-synthesizer": {"edit": "deny", "bash": "deny"},
    "hyperresearch-depth-investigator": {
        "task": {"*": "deny", "hyperresearch-fetcher": "allow"}
    },
}

PROFILE = resolve_profile("full")


def _render(tmp_path: Path) -> Path:
    agents_dir = tmp_path / ".opencode" / "agents"
    render_agents(agents_dir, PROFILE, ModelMap())
    return agents_dir


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} does not open with frontmatter"
    end = text.index("\n---\n", 3)
    meta = yaml.safe_load(text[len("---\n") : end])
    assert isinstance(meta, dict), f"{path.name} frontmatter did not parse to a mapping"
    return meta


# ---------------------------------------------------------------------------
# (a) roster shape
# ---------------------------------------------------------------------------


def test_renders_exactly_15_agents_with_canonical_names(tmp_path: Path) -> None:
    agents_dir = _render(tmp_path)
    files = sorted(agents_dir.glob("*.md"))
    assert len(files) == 15, f"expected exactly 15 agent files, got {len(files)}"
    for path in files:
        assert path.name.startswith("hyperresearch-"), path.name
        stem = path.name.removesuffix(".md")
        assert NAME_PATTERN.fullmatch(stem), f"{stem} violates the name pattern"
    assert {p.name.removesuffix(".md") for p in files} == set(EXPECTED_STEMS)


# ---------------------------------------------------------------------------
# (b) frontmatter matrix — parametrized over the whole roster
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stem", sorted(EXPECTED_STEMS))
class TestFrontmatterMatrix:
    def test_mode_subagent_and_hidden(self, tmp_path: Path, stem: str) -> None:
        meta = _frontmatter(_render(tmp_path) / f"{stem}.md")
        assert meta["mode"] == "subagent", stem
        assert meta["hidden"] is True, (
            f"{stem}: every roster member is pipeline-internal (S0-1: "
            "subagent-mode files are not user-invokable); hidden must be true"
        )
        assert meta["name"] == stem, stem

    def test_model_key_omitted_when_alias_unset(self, tmp_path: Path, stem: str) -> None:
        meta = _frontmatter(_render(tmp_path) / f"{stem}.md")
        assert "model" not in meta, (
            f"{stem}: default ModelMap is empty-inherit, so model: must be OMITTED"
        )

    def test_tools_deny_set_exact(self, tmp_path: Path, stem: str) -> None:
        meta = _frontmatter(_render(tmp_path) / f"{stem}.md")
        expected = EXPECTED_TOOLS_DENY.get(stem)
        if expected is None:
            assert "tools" not in meta, f"{stem} must carry no tools lock"
        else:
            assert meta["tools"] == expected, (
                f"{stem}: tools deny-set must be exactly {expected}"
            )
            # S0-3 amendment: edit stays ENABLED for patcher/polish-auditor.
            if stem in ("hyperresearch-patcher", "hyperresearch-polish-auditor"):
                assert "edit" not in meta["tools"], "edit must NOT be denied"

    def test_permission_denies_and_task_allowlist(self, tmp_path: Path, stem: str) -> None:
        meta = _frontmatter(_render(tmp_path) / f"{stem}.md")
        expected = EXPECTED_PERMISSION.get(stem)
        if expected is None:
            assert "permission" not in meta, f"{stem} must carry no permission block"
        else:
            assert meta["permission"] == expected, (
                f"{stem}: permission must be exactly {expected}"
            )


# ---------------------------------------------------------------------------
# (b2) [models] alias table resolution
# ---------------------------------------------------------------------------


def test_model_alias_set_flows_unset_roles_still_omit(tmp_path: Path) -> None:
    agents_dir = tmp_path / ".opencode" / "agents"
    model_map = ModelMap(fetcher="haiku", critics="qwen3-max")
    render_agents(agents_dir, PROFILE, model_map)

    fetcher_fm = _frontmatter(agents_dir / "hyperresearch-fetcher.md")
    assert fetcher_fm["model"] == "haiku"

    for critic in ("dialectic-critic", "depth-critic", "width-critic", "instruction-critic"):
        fm = _frontmatter(agents_dir / f"hyperresearch-{critic}.md")
        assert fm["model"] == "qwen3-max", critic

    critic_stems = {
        "hyperresearch-dialectic-critic",
        "hyperresearch-depth-critic",
        "hyperresearch-width-critic",
        "hyperresearch-instruction-critic",
    }
    others = [
        p
        for p in agents_dir.glob("*.md")
        if p.stem not in critic_stems and p.stem != "hyperresearch-fetcher"
    ]
    assert len(others) == 10
    for path in others:
        assert "model" not in _frontmatter(path), f"{path.name} must omit unset model"


# ---------------------------------------------------------------------------
# (c) determinism + idempotence
# ---------------------------------------------------------------------------


def test_render_is_deterministic_byte_for_byte(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    manifest_a = render_agents(dir_a, PROFILE, ModelMap())
    manifest_b = render_agents(dir_b, PROFILE, ModelMap())
    files_a = sorted(p.name for p in dir_a.glob("*.md"))
    files_b = sorted(p.name for p in dir_b.glob("*.md"))
    assert files_a == files_b and len(files_a) == 15
    for name in files_a:
        assert (dir_a / name).read_bytes() == (dir_b / name).read_bytes(), name
    assert sorted(p.name for p in manifest_a.files) == files_a == sorted(
        p.name for p in manifest_b.files
    )


def test_second_render_into_same_tree_rewrites_nothing(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    first = render_agents(agents_dir, PROFILE, ModelMap())
    before = {p.name: p.read_bytes() for p in agents_dir.glob("*.md")}
    second = render_agents(agents_dir, PROFILE, ModelMap())
    after = {p.name: p.read_bytes() for p in agents_dir.glob("*.md")}
    assert before == after, "re-render must be byte-stable"
    assert len(first.written) == 15 and first.unchanged == ()
    assert len(second.unchanged) == 15 and second.written == (), (
        "idempotent renderer must report zero rewrites when nothing changed"
    )


# ---------------------------------------------------------------------------
# (d) atomicity probe — injected failure mid-write-loop
# ---------------------------------------------------------------------------


def test_injected_failure_leaves_no_partial_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hyperresearch.core.opencode_install as mod

    target = tmp_path / "agents"
    real_write = mod._atomic_write
    state = {"n": 0}

    def flaky(path: Path, content: str) -> None:
        state["n"] += 1
        if state["n"] == 8:
            raise RuntimeError("injected mid-render failure")
        real_write(path, content)

    monkeypatch.setattr(mod, "_atomic_write", flaky)
    with pytest.raises(RuntimeError, match="injected"):
        render_agents(target, PROFILE, ModelMap())

    partial = sorted(target.glob("*.md"))
    assert 0 < len(partial) < 15, "failure must land mid-render for the probe to bite"
    # Every file on disk is COMPLETE: byte-equal to its planned content.
    clean = tmp_path / "clean"
    render_agents(clean, PROFILE, ModelMap())
    for path in partial:
        planned = (clean / path.name).read_text(encoding="utf-8")
        assert path.read_text(encoding="utf-8") == planned, (
            f"{path.name} was left partially written"
        )
        assert path.read_text(encoding="utf-8").endswith("\n")
    # No temp droppings left behind.
    assert [p.name for p in target.iterdir() if not p.name.endswith(".md")] == []
    # And the tree converges on the next run.
    monkeypatch.undo()
    final = render_agents(target, PROFILE, ModelMap())
    assert len(final.written) == 15 - len(partial)
    assert sorted(p.name for p in target.glob("*.md")) == sorted(p.name for p in clean.glob("*.md"))


# ---------------------------------------------------------------------------
# (e) prompt-body goldens vs the frozen P1-7 fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("const_name", "fixture_name"),
    [
        ("RESEARCHER_AGENT", "researcher_agent.md"),
        ("LOCI_ANALYST_AGENT", "loci_analyst_agent.md"),
        ("CITE_CHECKER_AGENT", "cite_checker_agent.md"),
    ],
)
def test_rendered_template_matches_frozen_golden(const_name: str, fixture_name: str) -> None:
    """P1-7 contract: render_prompt(constant, full-profile ctx) == fixture."""
    template = getattr(__import__(
        "hyperresearch.core.opencode_install", fromlist=[const_name]
    ), const_name)
    ctx = build_render_context(None, primary="full")
    rendered = render_prompt(template, ctx)
    golden = (GOLDEN_AGENTS_DIR / fixture_name).read_text(encoding="utf-8")
    assert rendered == golden, (
        f"render(full) of {const_name} deviates from the frozen P1-7 golden"
    )


def test_installed_cite_checker_body_is_golden_plus_substitution(tmp_path: Path) -> None:
    """Written body == frozen golden body after {hpr_path} substitution.

    cite-checker is substituted via literal string replace upstream (no brace
    collapsing), so the equality holds exactly. .format-substituted agents
    (fetcher etc.) additionally collapse doubled braces, so they are pinned by
    the P1-7-contract test above plus determinism, not by byte equality here.
    """
    from hyperresearch import __version__
    from hyperresearch.core.render import render_header

    agents_dir = _render(tmp_path)
    cite = agents_dir / "hyperresearch-cite-checker.md"
    text = cite.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---\n", 3)
    rest = text[end + len("\n---\n") :]

    golden_text = (GOLDEN_AGENTS_DIR / "cite_checker_agent.md").read_text(encoding="utf-8")
    golden_end = golden_text.index("\n---\n", 3)
    expected_body = golden_text[golden_end + len("\n---\n") :].replace(
        "{hpr_path}", "hyperresearch"
    )
    assert "{hpr_path}" not in rest, "placeholder leaked into the installed file"
    assert rest == f"{render_header('full', __version__)}\n{expected_body}", (
        "cite-checker installed file drifted from header+golden+substitution"
    )


def test_installed_patcher_body_matches_its_own_render(tmp_path: Path) -> None:
    """Agents without placeholders install their rendered prompt verbatim."""
    import hyperresearch.core.opencode_install as mod
    from hyperresearch import __version__
    from hyperresearch.core.render import render_header

    agents_dir = _render(tmp_path)
    path = agents_dir / "hyperresearch-patcher.md"
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---\n", 3)
    rest = text[end + len("\n---\n") :]

    ctx = build_render_context(None, primary="full")
    rendered = render_prompt(mod.PATCHER_AGENT, ctx)
    rendered_end = rendered.index("\n---\n", 3)
    expected_body = rendered[rendered_end + len("\n---\n") :]
    assert rest == f"{render_header('full', __version__)}\n{expected_body}"


# ---------------------------------------------------------------------------
# (f) installed-file goldens — byte-compare ALL 15 against live-upstream-
#     derived fixtures (countersign remediation X-2)
# ---------------------------------------------------------------------------


def test_agent_golden_fixtures_inventory_is_exactly_the_roster() -> None:
    """The frozen goldens pin every roster file and nothing else."""
    expected = {spec.filename for spec in AGENT_SPECS}
    actual = {p.name for p in AGENT_GOLDENS_DIR.glob("*.md")}
    assert actual == expected, (
        f"golden inventory drift: missing={expected - actual} "
        f"extra={actual - expected}"
    )


def _render_repo_lane(tmp_path: Path) -> Path:
    """Lane-ON render — used only by the P5 repo-analyst golden pin."""
    agents_dir = tmp_path / ".opencode" / "agents"
    render_agents(agents_dir, PROFILE, ModelMap(), repo_lane=True)
    return agents_dir


@pytest.mark.parametrize(
    "filename", sorted(spec.filename for spec in AGENT_SPECS), ids=lambda n: n
)
def test_installed_file_byte_matches_frozen_agent_golden(tmp_path: Path, filename: str) -> None:
    """Every rendered roster file byte-equals its frozen golden.

    Fixtures were captured ONCE by running the upstream installer live
    (hyperresearch 0.10.0, pinned reference 15010c5) into a scratch vault and
    applying ONLY the documented opencode-frontmatter deltas on top of the
    upstream-installed body bytes. Any silent fidelity rot — substitution
    mechanics, scaffold-bullet quirks, header placement, frontmatter shape —
    fails here.

    P5 delta: hyperresearch-repo-analyst.md has no upstream counterpart —
    it renders with ``repo_lane=True`` and byte-equals its own P5-frozen
    golden (captured with the install-resolved hpr_path, the same contract
    as every other golden). The other 15 files are checked through the
    default lane-off render, which must never emit the 16th file.
    """
    if filename == "hyperresearch-repo-analyst.md":
        agents_dir = _render_repo_lane(tmp_path)
    else:
        agents_dir = _render(tmp_path)
    rendered = (agents_dir / filename).read_bytes()
    golden = (AGENT_GOLDENS_DIR / filename).read_bytes()
    assert rendered == golden, f"{filename} drifted from the frozen upstream-derived golden"


def test_polish_auditor_keeps_upstream_doubled_scaffold_bullets(tmp_path: Path) -> None:
    """X-1 quirk pin: upstream's installer prepends ``indent="- "`` to already-
    bulleted scaffold lines (hooks.py:3864 + :79-83), so installed output
    carries DOUBLED ``- - `` bullets. Replicated verbatim — never normalized.
    """
    agents_dir = _render(tmp_path)
    text = (agents_dir / "hyperresearch-polish-auditor.md").read_text(encoding="utf-8")
    doubled = [
        line for line in text.splitlines() if line.startswith("- - `## ")
    ]
    assert len(doubled) == len(SCAFFOLD_ONLY_SECTION_HEADERS), doubled
    assert "- - `## User Prompt (VERBATIM ...`" in doubled


# ---------------------------------------------------------------------------
# spec-table integrity
# ---------------------------------------------------------------------------


def test_spec_table_covers_roster_without_browser_fetcher() -> None:
    names = [spec.filename for spec in AGENT_SPECS]
    # P5: the static spec table holds 16 (15 default + the conditional
    # repo-analyst); the DEFAULT RENDER pins 15 — see EXPECTED_STEMS above
    # and tests/test_cli/test_install_repo_lane.py for the 16th's both
    # lane states.
    assert len(names) == len(set(names)) == 16
    assert "hyperresearch-browser-fetcher.md" not in names
    assert "hyperresearch-repo-analyst.md" in names
    assert all(name.startswith("hyperresearch-") and name.endswith(".md") for name in names)
