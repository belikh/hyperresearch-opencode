"""Behavioral tests for the opencode skill/command renderer (P2-14).

Covers the piece's acceptance criteria:

(a) inventory — exactly 19 skills rendered to ``<skills_dir>/<name>/SKILL.md``,
    names ``^[a-z0-9]+(-[a-z0-9]+)*$`` matching their directory (opencode's
    own validation rule), in the exact upstream install order;
    RECONCILIATION: the P2-14 mission contract said "exactly 18", but the
    pinned upstream ships 19 markdowns = entry ROUTER + 18 step files
    (16 steps + half-steps 1-5 and 14-5); PARITY.md §12 records the same
    split. All 19 are rendered; nothing is invented away.
(b) frontmatter — every rendered file carries exactly opencode's recognized
    fields (``name`` + ``description``, spike S0-4), i.e. the upstream
    frontmatter needed ZERO delta bytes;
(c) P1-7 golden contract still holds on the raw render —
    ``render_prompt(source, full ctx)`` byte-matches the frozen
    ``golden_prompts/skills/`` fixtures for all 8 covered skills (this
    re-pins, in-scope, the skill half of the permanently-skipped
    ``test_prompt_golden`` module, whose ``core.hooks`` import target was
    replaced by the opencode renderer architecture);
(d) installed-file goldens — every one of the 19 rendered SKILL.md files
    byte-matches frozen fixtures under ``tests/fixtures/skill_goldens/``
    (captured ONCE from this renderer over the byte-verbatim upstream
    sources), closing the fidelity-rot hole;
(e) degraded-mode clauses — every skill whose UPSTREAM TEXT instructs
    subagent spawning (mechanical detector: ``subagent_type:`` or
    ``spawn a subagent``; exactly 13 incl. the router) carries a
    ``## Degraded mode`` clause naming the S0-1 fallback (``$HPR fetch-batch``
    direct calls); the six merely-descriptive skills carry none;
(f) command-file shape — ``.opencode/commands/hyperresearch.md`` per the
    documented opencode command format: description frontmatter, body
    invoking the router skill, ``$ARGUMENTS`` passthrough;
(g) AGENTS.md injection — creation/append/update semantics, idempotent
    no-op re-run (False), preservation of existing content, marker-pair
    integrity (unpaired marker raises), ``{hpr}`` substitution, and the
    opencode-specific blurb deltas;
(h) invoke-syntax conversion (countersign R-1): no Claude ``Skill(skill: …)``
    syntax survives the delta pass in any of the 19 renders — including the
    router's uppercase-N placeholder references that the original
    ``[a-z0-9-]+`` charclass let through unconverted — with every converted
    target pinned to the chain and the whole-chain census pinned at 25.

Falsification record: this module was written BEFORE
``src/hyperresearch/core/opencode_skills.py`` existed; running it then fails
at collection with ImportError (PORTING-NOTES.md §P2-14). The (e) negative
arm (six skills must NOT contain the clause) falsified an early draft that
appended the clause unconditionally; the (b) recognized-fields assertion
falsifies any future frontmatter "enrichment" that opencode would ignore or
reject. The (h) unit arm reproduces countersign R-1 against the frozen
charclass (placeholder refs left as Claude syntax) and so falsifies any
regression to a closed reference class.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from hyperresearch.core.opencode_install import OpencodeInstallError
from hyperresearch.core.opencode_skills import (
    COMMAND_NAME,
    DEGRADED_MODE_HEADING,
    OPENCODE_COMMAND_MD,
    SKILL_SPECS,
    _apply_deltas,
    inject_agents_md,
    read_skill_source,
    render_command,
    render_skills,
)
from hyperresearch.core.profiles import resolve_profile
from hyperresearch.core.render import build_render_context, render_prompt

SKILL_GOLDENS_DIR = Path(__file__).parent.parent / "fixtures" / "skill_goldens"
P1_SKILL_GOLDENS_DIR = Path(__file__).parent.parent / "fixtures" / "golden_prompts" / "skills"

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

EXPECTED_NAMES: tuple[str, ...] = tuple(spec.name for spec in SKILL_SPECS)

PROFILE = resolve_profile("full")

# Skills whose UPSTREAM text instructs subagent spawning — the degraded-mode
# set. The detector runs on the bundled SOURCE bytes, mirroring the renderer's
# own rule; the count pin makes silent set-growth/shrinkage loud.
SPAWN_MARKER_RE_SOURCE = ("subagent_type:", "spawn a subagent")


def _expected_degraded() -> frozenset[str]:
    out: set[str] = set()
    for spec in SKILL_SPECS:
        src = read_skill_source(f"{spec.name}.md")
        assert src is not None, spec.name
        if any(m in src for m in SPAWN_MARKER_RE_SOURCE):
            out.add(spec.name)
    return frozenset(out)


def _render(tmp_path: Path) -> Path:
    skills_dir = tmp_path / ".opencode" / "skills"
    render_skills(skills_dir, PROFILE)
    return skills_dir


def _frontmatter(text: str, label: str) -> dict[str, Any]:
    assert text.startswith("---\n"), f"{label} does not open with frontmatter"
    end = text.index("\n---\n", 3)
    meta = yaml.safe_load(text[len("---\n") : end])
    assert isinstance(meta, dict), f"{label}: frontmatter did not parse to a mapping"
    return meta


# ---------------------------------------------------------------------------
# (a) inventory shape
# ---------------------------------------------------------------------------


def test_renders_exactly_19_skills_with_canonical_names(tmp_path: Path) -> None:
    skills_dir = _render(tmp_path)
    files = sorted(skills_dir.glob("*/SKILL.md"))
    assert len(files) == 19, f"expected exactly 19 skills, got {len(files)}"
    for path in files:
        dirname = path.parent.name
        assert NAME_PATTERN.fullmatch(dirname), f"{dirname} violates the name pattern"
        assert path.parent.parent == skills_dir
    assert {p.parent.name for p in files} == set(EXPECTED_NAMES)


def test_spec_inventory_is_upstream_install_order() -> None:
    """Router first, then hooks.py:4098-4115 verbatim order."""
    assert EXPECTED_NAMES == (
        "hyperresearch",
        "hyperresearch-1-decompose",
        "hyperresearch-1-5-chapter-partition",
        "hyperresearch-2-width-sweep",
        "hyperresearch-3-contradiction-graph",
        "hyperresearch-4-loci-analysis",
        "hyperresearch-5-depth-investigation",
        "hyperresearch-6-cross-locus-reconcile",
        "hyperresearch-7-source-tensions",
        "hyperresearch-8-corpus-critic",
        "hyperresearch-9-evidence-digest",
        "hyperresearch-10-triple-draft",
        "hyperresearch-11-synthesize",
        "hyperresearch-12-critics",
        "hyperresearch-13-gap-fetch",
        "hyperresearch-14-patcher",
        "hyperresearch-14-5-cite-check",
        "hyperresearch-15-polish",
        "hyperresearch-16-readability-audit",
    )


def test_bundled_sources_are_exactly_the_upstream_set() -> None:
    import hyperresearch.skills as pkg

    md_files = sorted(p.name for p in Path(pkg.__file__).parent.glob("*.md"))
    assert md_files == sorted(f"{n}.md" for n in EXPECTED_NAMES)


# ---------------------------------------------------------------------------
# (b) frontmatter matrix — opencode recognizes name/description (S0-4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", EXPECTED_NAMES)
class TestFrontmatter:
    def test_name_and_description_only(self, tmp_path: Path, name: str) -> None:
        path = _render(tmp_path) / name / "SKILL.md"
        meta = _frontmatter(path.read_text(encoding="utf-8"), name)
        # opencode recognizes name/description/license/compatibility/metadata
        # and IGNORES unknown fields — anything else would be dead weight.
        allowed = {"name", "description", "license", "compatibility", "metadata"}
        assert set(meta) <= allowed, f"{name}: unrecognized frontmatter {set(meta) - allowed}"
        assert meta["name"] == name, f"{name}: name must match its directory"
        assert isinstance(meta["description"], str) and meta["description"].strip()

    def test_no_leftover_profile_placeholders(self, tmp_path: Path, name: str) -> None:
        text = (_render(tmp_path) / name / "SKILL.md").read_text(encoding="utf-8")
        assert "<<" not in text and ">>" not in text, f"{name}: unrendered placeholder"


# ---------------------------------------------------------------------------
# (c) P1-7 golden contract on the raw render (8 covered skills)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    sorted(p.stem for p in P1_SKILL_GOLDENS_DIR.glob("*.md")),
    ids=lambda n: n,
)
def test_raw_render_matches_frozen_p1_golden(name: str) -> None:
    src = read_skill_source(f"{name}.md")
    assert src is not None
    ctx = build_render_context(None, primary="full")
    rendered = render_prompt(src, ctx)
    golden = (P1_SKILL_GOLDENS_DIR / f"{name}.md").read_text(encoding="utf-8")
    assert rendered == golden, f"render(full) of {name}.md deviates from the P1-7 golden"


# ---------------------------------------------------------------------------
# (d) installed-file goldens — all 19 byte-compared to frozen fixtures
# ---------------------------------------------------------------------------


def test_skill_golden_fixtures_inventory_is_exactly_the_chain() -> None:
    expected = {f"{name}.md" for name in EXPECTED_NAMES}
    actual = {p.name for p in SKILL_GOLDENS_DIR.glob("*.md")}
    assert actual == expected, (
        f"golden inventory drift: missing={expected - actual} extra={actual - expected}"
    )


@pytest.mark.parametrize("name", EXPECTED_NAMES, ids=lambda n: n)
def test_installed_file_byte_matches_frozen_skill_golden(tmp_path: Path, name: str) -> None:
    skills_dir = _render(tmp_path)
    rendered = (skills_dir / name / "SKILL.md").read_bytes()
    golden = (SKILL_GOLDENS_DIR / f"{name}.md").read_bytes()
    assert rendered == golden, f"{name}/SKILL.md drifted from the frozen golden"


def test_corpus_critic_keeps_upstream_literal_hpr_path_quirk(tmp_path: Path) -> None:
    """Upstream's skill installer never substitutes {hpr_path}, so installed
    skills carry the literal string (hyperresearch-8-corpus-critic.md:39).
    Replicate-quirks-verbatim: 'fixing' it is an undocumented delta."""
    text = (_render(tmp_path) / "hyperresearch-8-corpus-critic" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "{hpr_path} search" in text


# ---------------------------------------------------------------------------
# determinism + idempotence + atomicity
# ---------------------------------------------------------------------------


def test_render_is_deterministic_byte_for_byte(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    manifest_a = render_skills(dir_a, PROFILE)
    manifest_b = render_skills(dir_b, PROFILE)
    rel_a = sorted(str(p.relative_to(dir_a)) for p in dir_a.glob("*/SKILL.md"))
    rel_b = sorted(str(p.relative_to(dir_b)) for p in dir_b.glob("*/SKILL.md"))
    assert rel_a == rel_b and len(rel_a) == 19
    for rel in rel_a:
        assert (dir_a / rel).read_bytes() == (dir_b / rel).read_bytes(), rel
    assert sorted(p.parent.name for p in manifest_a.files) == sorted(
        p.parent.name for p in manifest_b.files
    )


def test_second_render_into_same_tree_rewrites_nothing(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    first = render_skills(skills_dir, PROFILE)
    before = {p: p.read_bytes() for p in skills_dir.glob("*/SKILL.md")}
    second = render_skills(skills_dir, PROFILE)
    after = {p: p.read_bytes() for p in skills_dir.glob("*/SKILL.md")}
    assert before == after, "re-render must be byte-stable"
    assert len(first.written) == 19 and first.unchanged == ()
    assert len(second.unchanged) == 19 and second.written == ()


def test_injected_failure_leaves_no_partial_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hyperresearch.core.opencode_skills as mod

    target = tmp_path / "skills"
    real_write = mod._atomic_write
    state = {"n": 0}

    def flaky(path: Path, content: str) -> None:
        state["n"] += 1
        if state["n"] == 11:
            raise RuntimeError("injected mid-render failure")
        real_write(path, content)

    monkeypatch.setattr(mod, "_atomic_write", flaky)
    with pytest.raises(RuntimeError, match="injected"):
        render_skills(target, PROFILE)

    partial = sorted(target.glob("*/SKILL.md"))
    assert 0 < len(partial) < 19, "failure must land mid-render for the probe to bite"
    clean = tmp_path / "clean"
    render_skills(clean, PROFILE)
    for path in partial:
        planned = (clean / path.parent.name / "SKILL.md").read_text(encoding="utf-8")
        assert path.read_text(encoding="utf-8") == planned, (
            f"{path.parent.name} was left partially written"
        )
    assert list(target.rglob("*.tmp")) == [], "temp droppings left behind"
    monkeypatch.undo()
    final = render_skills(target, PROFILE)
    assert len(final.written) == 19 - len(partial)


# ---------------------------------------------------------------------------
# (e) degraded-mode clauses
# ---------------------------------------------------------------------------


def test_degraded_detector_yields_exactly_13_spawning_skills() -> None:
    expected = _expected_degraded()
    assert len(expected) == 13, f"detector drifted: {sorted(expected)}"
    actual = {spec.name for spec in SKILL_SPECS if spec.degraded}
    assert actual == expected, "SkillSpec.degraded rotted against the source detector"


@pytest.mark.parametrize("name", EXPECTED_NAMES, ids=lambda n: n)
def test_degraded_mode_clause_presence_matches_spawning_set(
    tmp_path: Path, name: str
) -> None:
    text = (_render(tmp_path) / name / "SKILL.md").read_text(encoding="utf-8")
    if name in _expected_degraded():
        assert DEGRADED_MODE_HEADING in text, f"{name} spawns subagents but lacks the clause"
        # Literal pin: the mission names the clause "## Degraded mode"
        # verbatim. Asserting only the imported constant would let a heading
        # rename keep the suite green (probe-falsified 2026-08-23).
        assert "## Degraded mode" in text, f"{name}: clause heading renamed"
        assert "$HPR fetch-batch" in text, f"{name}: clause must name the fetch-batch fallback"
        assert text.rstrip().endswith("`source_budget`."), (
            f"{name}: clause must preserve the per-locus budget invariant"
        )
    else:
        assert DEGRADED_MODE_HEADING not in text, (
            f"{name} spawns nothing upstream — clause must be absent"
        )


# ---------------------------------------------------------------------------
# (f) command file shape
# ---------------------------------------------------------------------------


def test_command_file_shape_and_arguments_passthrough(tmp_path: Path) -> None:
    commands_dir = tmp_path / ".opencode" / "commands"
    path = render_command(commands_dir)
    assert path == commands_dir / f"{COMMAND_NAME}.md"
    text = path.read_text(encoding="utf-8")
    assert text == OPENCODE_COMMAND_MD
    meta = _frontmatter(text, str(path))
    assert isinstance(meta.get("description"), str) and meta["description"].strip()
    body = text[text.index("\n---\n", 3) + len("\n---\n") :]
    assert "$ARGUMENTS" in body, "command template must pass arguments through"
    assert 'skill({ name: "hyperresearch" })' in body, "must invoke the router skill"


def test_command_render_is_idempotent_no_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hyperresearch.core.opencode_skills as mod

    commands_dir = tmp_path / "commands"
    render_command(commands_dir)
    before = (commands_dir / f"{COMMAND_NAME}.md").read_bytes()

    def boom(path: Path, content: str) -> None:  # pragma: no cover - tripwire
        raise AssertionError(f"second render_command rewrote {path}")

    monkeypatch.setattr(mod, "_atomic_write", boom)
    render_command(commands_dir)
    assert (commands_dir / f"{COMMAND_NAME}.md").read_bytes() == before


# ---------------------------------------------------------------------------
# (g) AGENTS.md injection
# ---------------------------------------------------------------------------

MARKER_START = "<!-- hyperresearch:start -->"
MARKER_END = "<!-- hyperresearch:end -->"


def test_injection_creates_missing_agents_md(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    changed = inject_agents_md(path)
    assert changed is True
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# AGENTS.md\n")
    assert text.count(MARKER_START) == 1 and text.count(MARKER_END) == 1
    assert MARKER_START in text and MARKER_END in text
    # opencode-specific blurb deltas are present...
    assert ".opencode/skills/hyperresearch/SKILL.md" in text
    assert "opencode's native `skill` tool" in text
    assert "every task tool call passes" in text
    assert "not installed in this opencode port" in text
    # ...and the Claude-harness originals they replaced are gone.
    assert ".claude/skills/" not in text
    assert "`Skill` tool" not in text and "Skill tool" not in text
    assert "every Task call passes" not in text
    assert "browser-fetcher agent drains them" not in text
    # untrusted-content policy, OA-substitution disclosure, academic-first,
    # curation doctrine all survive the port (mission-required sections).
    for required in (
        "### Untrusted content policy",
        "### Open-access substitution — check this before quoting a paper",
        "### Academic APIs before web search",
        "### Curate after every session",
    ):
        assert required in text, f"blurb lost required section: {required}"
    assert "{hpr}" not in text, "CLI placeholder must be substituted"


def test_injection_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    assert inject_agents_md(path) is True
    before = path.read_bytes()
    assert inject_agents_md(path) is False, "re-run on up-to-date file must be a no-op"
    assert path.read_bytes() == before


def test_injection_preserves_existing_content_and_updates_stale_section(
    tmp_path: Path,
) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text(
        "# My project\n\nCustom rules that must survive.\n"
        f"\n{MARKER_START}\n## STALE GARBAGE\nold numbers\n{MARKER_END}\n"
        "\nTrailing user note.\n",
        encoding="utf-8",
    )
    changed = inject_agents_md(path)
    assert changed is True
    text = path.read_text(encoding="utf-8")
    assert "# My project\n\nCustom rules that must survive.\n" in text
    assert text.endswith("Trailing user note.\n") or "Trailing user note." in text
    assert "STALE GARBAGE" not in text, "stale section content must be replaced"
    assert "## Research Base (hyperresearch)" in text
    assert text.count(MARKER_START) == 1 and text.count(MARKER_END) == 1


def test_injection_appends_to_plain_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text("Existing instructions, no markers.\n", encoding="utf-8")
    assert inject_agents_md(path) is True
    text = path.read_text(encoding="utf-8")
    assert text.startswith("Existing instructions, no markers.\n")
    assert MARKER_START in text


def test_injection_rejects_unpaired_marker(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text(f"user content\n{MARKER_START}\ndangling\n", encoding="utf-8")
    with pytest.raises(OpencodeInstallError, match="unpaired"):
        inject_agents_md(path)


def test_injection_substitutes_custom_hpr_path(tmp_path: Path) -> None:
    path = tmp_path / "AGENTS.md"
    inject_agents_md(path, hpr_path="/opt/tools/bin/hpr")
    text = path.read_text(encoding="utf-8")
    assert "/opt/tools/bin/hpr escalation list --status queued -j" in text


# ---------------------------------------------------------------------------
# (h) invoke-syntax conversion — countersign R-1 regression
# ---------------------------------------------------------------------------

# Claude-syntax marker that must NEVER survive the delta pass.
CLAUDE_INVOKE = "Skill(skill:"

# The converted opencode form; capture group is the referenced skill name.
OPENCODE_INVOKE_RE = re.compile(r'skill\(\{ name: "([^"]+)" \}\)')

# The router's two TEMPLATE placeholders convert to opencode syntax but are
# deliberately not concrete chain members. Pinned exhaustively so no other
# non-member reference can slip through the conversion path.
PLACEHOLDER_REFS = frozenset({"hyperresearch-N-stepname", "hyperresearch-N-..."})


def test_skill_invoke_pattern_converts_any_quoted_reference() -> None:
    """Unit falsification of countersign R-1. The frozen ``[a-z0-9-]+``
    charclass converted all 23 concrete invocations but left the router's
    uppercase-N placeholder references (``hyperresearch-N-stepname`` :31,
    ``hyperresearch-N-...`` :87) as literal Claude syntax — hyphens were
    never the problem; the uppercase ``N`` and the dots were outside the
    class. The widened ``[^"]+`` payload must convert EVERY well-formed
    quoted reference, whatever its shape."""
    refs = (
        "hyperresearch",
        "hyperresearch-14-5-cite-check",
        "hyperresearch-N-stepname",  # router :31 — missed pre-fix
        "hyperresearch-N-...",  # router :87 — missed pre-fix
        "Future_Placeholder.42",
    )
    for ref in refs:
        out = _apply_deltas(f'prefix {CLAUDE_INVOKE} "{ref}") suffix')
        assert f'skill({{ name: "{ref}" }})' in out, f"{ref!r} was not converted"
        assert CLAUDE_INVOKE not in out, f"{ref!r} left Claude syntax behind"


@pytest.mark.parametrize("name", EXPECTED_NAMES, ids=lambda n: n)
def test_no_claude_skill_invocation_survives_render(tmp_path: Path, name: str) -> None:
    """Chain-wide R-1 arm: every rendered skill is free of Claude invoke
    syntax, and every reference it does carry targets a real chain member."""
    text = (_render(tmp_path) / name / "SKILL.md").read_text(encoding="utf-8")
    assert CLAUDE_INVOKE not in text, f"{name}: unconverted Skill(skill: reference"
    for target in OPENCODE_INVOKE_RE.findall(text):
        assert target in set(EXPECTED_NAMES) or target in PLACEHOLDER_REFS, (
            f"{name}: invokes unknown {target!r}"
        )


def test_router_placeholder_references_convert_verbatim(tmp_path: Path) -> None:
    """Exact pins for the two references that escaped the frozen charclass."""
    text = (_render(tmp_path) / "hyperresearch" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert 'skill({ name: "hyperresearch-N-stepname" })' in text, ":31 placeholder"
    assert 'skill({ name: "hyperresearch-N-..." })' in text, ":87 placeholder"
    assert 'Skill(skill: "hyperresearch-N' not in text


def test_invoke_conversion_census_is_25_across_the_chain(tmp_path: Path) -> None:
    """Pin the whole-chain census: 25 references convert (23 concrete + the
    2 router placeholders); every target is a chain member; the terminal
    16-readability-audit invokes nothing (15-polish routes TO it)."""
    skills_dir = _render(tmp_path)
    total = 0
    targets: set[str] = set()
    for name in EXPECTED_NAMES:
        found = OPENCODE_INVOKE_RE.findall(
            (skills_dir / name / "SKILL.md").read_text(encoding="utf-8")
        )
        total += len(found)
        targets |= set(found)
    assert total == 25, f"conversion census drifted: {total} (expected 25)"
    assert targets - PLACEHOLDER_REFS <= set(EXPECTED_NAMES), (
        "converted a non-chain reference"
    )
    assert OPENCODE_INVOKE_RE.findall(
        (skills_dir / "hyperresearch-16-readability-audit" / "SKILL.md").read_text(
            encoding="utf-8"
        )
    ) == [], "terminal skill must invoke nothing"
