"""opencode skill/command renderer — the hyperresearch V8 skill chain for opencode.

Ports the upstream Claude Code skill installer (``core/hooks.py``
``_install_hyperresearch_skill`` :4076-4094 + ``_install_hyperresearch_step_skills``
:4119-4178, pinned reference 15010c5) to the opencode layout proven by spike
S0-4: ``<target>/.opencode/skills/<name>/SKILL.md``, discovered and loaded by
opencode's native ``skill`` tool, plus the ``/hyperresearch`` custom command at
``.opencode/commands/hyperresearch.md`` and the ops-doc injection into
``AGENTS.md`` (PARITY §12/§15).

**Inventory reconciliation (the P2-14 mission contract said "exactly 18").**
Upstream ships 19 skill markdowns under ``src/hyperresearch/skills/``: the
``hyperresearch`` entry ROUTER + 18 step files (16 numbered steps plus the two
hyphenated half-steps ``hyperresearch-1-5-chapter-partition`` and
``hyperresearch-14-5-cite-check``). PARITY.md §12 records the same split
("plus 19 skill markdowns ... 18 files, 2,619 lines total; the 2,906 figure
sometimes quoted for the directory includes the 287-line entry router").
The plan's "18" therefore matches the STEP-file count excluding the router;
this renderer ships all 19 rather than inventing an exclusion.

Per file, the pipeline is:

1. Read the bundled source (byte-verbatim copies of the pinned upstream
   ``skills/*.md``).
2. Render profile placeholders (``<< p.* >>``) through the shared engine.
   The P1-7 golden contract still holds on the raw render:
   ``render_prompt(source, full-profile ctx)`` must byte-match
   ``tests/fixtures/golden_prompts/skills/``.
3. Apply the documented opencode deltas — surgical exact-string replacements,
   every changed line logged in PORTING-NOTES.md §P2-14:

   - skill-tool invocation form ``Skill(skill: "x")`` -> ``skill({ name: "x" })``
     and the ``Skill tool`` noun -> opencode's native ``skill`` tool;
   - Task-tool nouns -> opencode's lowercase ``task`` tool;
   - ``TodoWrite`` -> opencode's ``todowrite``;
   - Claude headless-mode flags (``-p`` / ``end_turn``) -> ``opencode run``
     semantics;
   - the bootstrap step-skills check path ``.claude/skills/...`` ->
     ``.opencode/skills/...``;
   - browser-lane availability notes (the Claude-side browser-fetcher agent
     is a declared non-goal, PARITY §13/§17);
   - a ``## Degraded mode`` clause appended to every skill whose upstream
     text instructs subagent spawning: opencode delegation is exactly ONE
     level deep (spike S0-1 REFUTED nested spawns), so spawned roles that
     would delegate further degrade to calling ``$HPR fetch-batch`` directly.

   Frontmatter needs NO delta: upstream skills already emit exactly the fields
   opencode recognizes — ``name`` + ``description`` (S0-4 evidence; unknown
   frontmatter fields are ignored by opencode anyway).
4. Stamp the same provenance header as upstream installs (and P2-13), after
   the frontmatter.

Replicated upstream quirks (replicate-quirks-verbatim doctrine):

- Upstream's skill installer does NOT substitute ``{hpr_path}``, so installed
  skills carry the literal string ``{hpr_path}`` in
  ``skills/hyperresearch-8-corpus-critic.md:39``. Replicated byte-exactly.
- Upstream prose says "the 16 step skills"/"Installs the 16 step skill files"
  while installing 18 (stale docstring). Replicated verbatim.

Writes are deterministic (same inputs produce byte-identical outputs), fully
computed before any write lands, and per-file atomic via temp + ``os.replace``
(shared plumbing with the P2-13 agent renderer).

Public API for the P2-16 installer verb:

- ``render_skills(skills_dir, profile) -> SkillManifest``
- ``render_command(commands_dir) -> Path``
- ``inject_agents_md(path) -> bool`` (True iff the file changed)
"""

from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass
from pathlib import Path

from hyperresearch.core.agent_docs import (
    HYPERRESEARCH_BLURB,
    HYPERRESEARCH_SECTION_END,
    HYPERRESEARCH_SECTION_MARKER,
)
from hyperresearch.core.opencode_install import OpencodeInstallError, _atomic_write
from hyperresearch.core.profiles import Profile
from hyperresearch.core.render import insert_after_frontmatter, render_prompt

__all__ = [
    "COMMAND_NAME",
    "DEGRADED_MODE_HEADING",
    "OPENCODE_COMMAND_MD",
    "SKILL_SPECS",
    "SkillManifest",
    "SkillSpec",
    "inject_agents_md",
    "read_skill_source",
    "render_command",
    "render_skills",
]


# ---------------------------------------------------------------------------
# Skill inventory — VERBATIM from upstream hooks.py:4097-4116 (entry skill +
# _HYPERRESEARCH_STEP_SKILLS, pinned 15010c5), in upstream install order.
# ---------------------------------------------------------------------------

_ROUTER = "hyperresearch"

_STEP_SKILLS: tuple[str, ...] = (
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


def read_skill_source(src_name: str) -> str | None:
    """Read a skill file from package resources, falling back to source tree.

    Verbatim port of upstream hooks.py:4059-4075 (``_read_skill_source``).
    """
    try:
        return (
            importlib.resources.files("hyperresearch.skills")
            .joinpath(src_name)
            .read_text(encoding="utf-8")
        )
    except Exception:
        skill_src = Path(__file__).parent.parent / "skills" / src_name
        if skill_src.exists():
            return skill_src.read_text(encoding="utf-8")
        return None


@dataclass(frozen=True)
class SkillSpec:
    """One skill of the chain: its name and whether it carries the degraded-mode clause."""

    name: str
    degraded: bool


# A skill bears the DEGRADED-MODE clause iff its upstream text instructs
# spawning subagents. Mechanical detector (cross-checked by tests): the
# spawn-template marker ``subagent_type:`` (12 step files) or the router's
# spawn-contract phrasing "spawn a subagent". The remaining six files only
# DESCRIBE other steps' spawns and get no clause.
_SPAWNING_MARKERS: tuple[str, ...] = ("subagent_type:", "spawn a subagent")


def _is_spawning(name: str) -> bool:
    src = read_skill_source(f"{name}.md")
    if src is None:
        raise OpencodeInstallError(f"{name}: bundled skill source missing")
    return any(marker in src for marker in _SPAWNING_MARKERS)


def _build_specs() -> tuple[SkillSpec, ...]:
    names = (_ROUTER, *_STEP_SKILLS)
    return tuple(SkillSpec(name=n, degraded=_is_spawning(n)) for n in names)


SKILL_SPECS: tuple[SkillSpec, ...] = _build_specs()


# ---------------------------------------------------------------------------
# Documented opencode deltas — surgical exact-string rules. Every occurrence
# of every rule is enumerated in PORTING-NOTES.md §P2-14; the frozen goldens
# under tests/fixtures/skill_goldens/ pin the exact resulting bytes. Bodies
# are otherwise byte-faithful upstream renders. A rule that matches zero
# times in a given skill is simply a no-op there.
# ---------------------------------------------------------------------------

# D1a converts ANY quoted reference inside the Claude invocation shape:
# ``Skill(skill: "<ref>")`` -> ``skill({ name: "<ref>" })``. The payload is
# deliberately NOT a closed charclass: ``[a-z0-9-]+`` let the router's
# uppercase-N placeholder references (``hyperresearch-N-stepname`` :31 and
# ``hyperresearch-N-...`` :87) survive as literal Claude syntax while all 23
# concrete invocations converted (countersign R-1), and any future placeholder
# spelling would rot the same way. ``[^"]+`` cannot over-match — it stops at
# the closing quote and requires the full trailing ``")``.
_SKILL_INVOKE_RE = re.compile(r'Skill\(skill: "([^"]+)"\)')

_DELTAS: tuple[tuple[str, str], ...] = (
    # D1a: opencode native skill-tool invocation form (docs: skill({ name: "..." }))
    #      handled via _SKILL_INVOKE_RE below.
    # D1b-D1d: the tool noun, plain / backticked / prose forms.
    ("Skill tool", "skill tool"),
    ("`Skill` tool", "`skill` tool"),
    ("invoke a Skill,", "invoke a skill,"),
    # D2: opencode's task tool is lowercase; keep the call shapes accurate.
    ("every Task call", "every task tool call"),
    ("a Task prompt", "a task prompt"),
    ("Task result", "task result"),
    ("both Task calls", "both task tool calls"),
    ("all Task calls", "all task tool calls"),
    # D3: opencode todo tools.
    ("TodoWrite", "todowrite"),
    # D4: Claude headless flags -> `opencode run` semantics.
    (
        "In `-p` mode, a text-only response triggers `end_turn`.",
        "In non-interactive (`opencode run`) mode, a text-only response ends "
        "the run.",
    ),
    (
        "In non-interactive (`-p`) mode, a text-only response (no tool call) "
        "triggers `end_turn` — the process exits and the pipeline dies.",
        "In non-interactive (`opencode run`) mode, a text-only response (no "
        "tool call) ends the session — the process exits and the pipeline dies.",
    ),
    (
        "In non-interactive (`-p`) runs where no user can answer",
        "In non-interactive (`opencode run`) sessions where no user can answer",
    ),
    # D5: bootstrap step-skills check path (S0-4 layout).
    (
        ".claude/skills/hyperresearch-1-decompose/SKILL.md",
        ".opencode/skills/hyperresearch-1-decompose/SKILL.md",
    ),
    # D6: the browser lane is a declared non-goal (PARITY §13/§17) — make all
    # three mentions state the deferral instead of implying a live spawn target.
    (
        "**If the Claude-in-Chrome extension is unavailable**",
        "**If the browser-fetcher lane is unavailable (it always is in this "
        "opencode port — the Claude-in-Chrome automation stack was deferred)**",
    ),
    (
        "you drive the user's real Chrome browser to fetch them.",
        "you would drive the user's real Chrome browser to fetch them. In "
        "this opencode port the browser-fetcher agent is NOT installed "
        "(deferred lane), so this spawn never fires — the queue drains per "
        "the fallback rule below.",
    ),
    (
        "Step 2.8 drains the queue via ONE `hyperresearch-browser-fetcher` "
        "subagent driving the user's real Chrome browser. Two standing rules:",
        "Step 2.8 drains the queue via ONE `hyperresearch-browser-fetcher` "
        "subagent driving the user's real Chrome browser. In this opencode "
        "port that agent is NOT installed (deferred lane): the queue "
        "accumulates instead of draining, and the fallback rule below is the "
        "standing behavior. Two standing rules:",
    ),
)


def _apply_deltas(text: str) -> str:
    text = _SKILL_INVOKE_RE.sub(r'skill({ name: "\1" })', text)
    for old, new in _DELTAS:
        text = text.replace(old, new)
    return text


# ---------------------------------------------------------------------------
# Degraded-mode clause (spike S0-1 adopted fallback)
# ---------------------------------------------------------------------------

DEGRADED_MODE_HEADING = "## Degraded mode"

_DEGRADED_MODE_CLAUSE = f"""

{DEGRADED_MODE_HEADING}

opencode allows exactly one delegation level (spike S0-1): this skill runs in
the primary session, so its task calls are level-1 spawns into the roster at
`.opencode/agents/` and work as written above. A spawned subagent gets NO task
tool and cannot re-spawn anything. Where a spawned role's own procedure would
delegate further — depth investigators chaining `hyperresearch-fetcher` — that
hop does not exist here: investigators call `$HPR fetch-batch` directly with
their batched URLs (one invocation preserves the batch economics the Task hop
had), still honoring their per-locus `source_budget`.
"""


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillManifest:
    """Result of one :func:`render_skills` pass (same shape as AgentManifest)."""

    written: tuple[Path, ...]
    unchanged: tuple[Path, ...]

    @property
    def files(self) -> tuple[Path, ...]:
        """Every skill file the target tree now contains, in render order."""
        return self.written + self.unchanged


def _render_skill(spec: SkillSpec, profile: Profile) -> str:
    """Full SKILL.md bytes for one skill: render -> deltas -> clause -> header."""
    from hyperresearch import __version__
    from hyperresearch.core.opencode_install import _render_context
    from hyperresearch.core.render import render_header

    src = read_skill_source(f"{spec.name}.md")
    if src is None:
        raise OpencodeInstallError(f"{spec.name}: bundled skill source missing")
    rendered = render_prompt(src, _render_context(profile))
    rendered = _apply_deltas(rendered)
    if spec.degraded and DEGRADED_MODE_HEADING not in rendered:
        rendered += _DEGRADED_MODE_CLAUSE
    header = render_header(profile.name, __version__)
    return insert_after_frontmatter(rendered, header)


def render_skills(skills_dir: Path, profile: Profile) -> SkillManifest:
    """Render the 19-skill chain into ``skills_dir`` as ``<name>/SKILL.md``.

    Deterministic and idempotent: identical inputs produce byte-identical
    files; already-byte-identical files are left untouched and reported under
    ``unchanged``. Atomicity is per-file (temp + rename), matching
    :func:`hyperresearch.core.opencode_install.render_agents`. There is no
    whole-set transaction: an injected failure mid-render leaves complete
    files behind and the next run converges the set.
    """
    plan: list[tuple[Path, str]] = []
    for spec in SKILL_SPECS:
        content = _render_skill(spec, profile)
        plan.append((skills_dir / spec.name / "SKILL.md", content))

    skills_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    unchanged: list[Path] = []
    for path, content in plan:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            unchanged.append(path)
            continue
        _atomic_write(path, content)
        written.append(path)
    return SkillManifest(written=tuple(written), unchanged=tuple(unchanged))


# ---------------------------------------------------------------------------
# /hyperresearch command file (.opencode/commands/hyperresearch.md)
# ---------------------------------------------------------------------------

COMMAND_NAME = "hyperresearch"

OPENCODE_COMMAND_MD = """\
---
description: Run the hyperresearch V8 deep-research pipeline
---
Load the **hyperresearch** entry skill with your `skill` tool — invoke it as
`skill({ name: "hyperresearch" })` — then execute the full V8 pipeline exactly
as the router describes, from bootstrap through the ship gate.

Research query (verbatim, gospel):

$ARGUMENTS
"""


def render_command(commands_dir: Path) -> Path:
    """Write the ``/hyperresearch`` command file; returns its path (idempotent).

    opencode command format (docs/commands): markdown at
    ``.opencode/commands/<name>.md``; frontmatter ``description``; body is
    the prompt template, with ``$ARGUMENTS`` replaced by everything the user
    typed after ``/hyperresearch``.
    """
    commands_dir.mkdir(parents=True, exist_ok=True)
    path = commands_dir / f"{COMMAND_NAME}.md"
    if not (path.is_file() and path.read_text(encoding="utf-8") == OPENCODE_COMMAND_MD):
        _atomic_write(path, OPENCODE_COMMAND_MD)
    return path


# ---------------------------------------------------------------------------
# AGENTS.md injection (PARITY §15: CLAUDE.md blurb -> AGENTS.md)
# ---------------------------------------------------------------------------

# The ops blurb is upstream's HYPERRESEARCH_BLURB (already ported verbatim in
# core/agent_docs.py) with ONLY the Claude-harness mechanics reworded to their
# opencode equivalents. Every edit is listed in PORTING-NOTES.md §P2-14.
_AGENTS_MD_BLURB_EDITS: tuple[tuple[str, str], ...] = (
    # E1: skill location (S0-4 layout)
    (
        "The entry skill at `.claude/skills/hyperresearch/SKILL.md` is a thin ROUTER.",
        "The entry skill at `.opencode/skills/hyperresearch/SKILL.md` is a thin ROUTER.",
    ),
    # E2: loading mechanism
    (
        "loaded fresh into context via the `Skill` tool when each step runs",
        "loaded fresh into context via opencode's native `skill` tool when "
        "each step runs",
    ),
    # E3: browser-lane drain reality (PARITY §17 deferral)
    (
        "The browser-fetcher agent drains them via the user's real Chrome; "
        "CAPTCHAs / logins / 2FA are ALWAYS handed to the human, consolidated "
        "into one message.",
        "The escalation queue waits for a human or a future browser lane (the "
        "Claude-side browser-fetcher agent is not installed in this opencode "
        "port); CAPTCHAs / logins / 2FA are ALWAYS handed to the human, "
        "consolidated into one message.",
    ),
    # E4: roster enumeration drops the non-installed browser-fetcher
    (
        "polish-auditor, readability-recommender, browser-fetcher)",
        "polish-auditor, readability-recommender; the browser-fetcher lane is "
        "deferred in this port)",
    ),
    # E5: spawn-contract noun
    (
        "The subagent spawn contract (every Task call passes the verbatim "
        "research_query + pipeline position + inputs)",
        "The subagent spawn contract (every task tool call passes the "
        "verbatim research_query + pipeline position + inputs)",
    ),
)


def _agents_md_blurb(hpr_path: str) -> str:
    text = HYPERRESEARCH_BLURB
    for old, new in _AGENTS_MD_BLURB_EDITS:
        if old not in text:
            raise OpencodeInstallError(
                f"AGENTS.md blurb edit target not found: {old[:60]!r}..."
            )
        text = text.replace(old, new)
    return text.format(
        marker=HYPERRESEARCH_SECTION_MARKER,
        end_marker=HYPERRESEARCH_SECTION_END,
        hpr=hpr_path.replace("\\", "/"),
    )


def inject_agents_md(path: Path, *, hpr_path: str = "hyperresearch") -> bool:
    """Inject the hyperresearch ops section into an AGENTS.md file.

    Port of upstream agent_docs.py ``inject_agent_docs`` /
    ``_inject_into_file`` (CLAUDE.md variant) retargeted at AGENTS.md with
    opencode mechanics. Semantics:

    - missing file  -> created with a ``# AGENTS.md`` header + the marked
      section; returns True;
    - no marker yet -> the section is appended, preserving every existing
      byte of user content; returns True;
    - marker present-> the marked section is replaced in place, preserving
      everything outside it; returns True only when bytes actually changed,
      so re-running an up-to-date injection is a no-op diff (False).

    Raises :class:`OpencodeInstallError` on unpaired markers (start without
    end or vice versa) — that is corruption, and silently appending a second
    section would multiply it. Writes are atomic.
    """
    blurb = _agents_md_blurb(hpr_path)

    start = HYPERRESEARCH_SECTION_MARKER
    end = HYPERRESEARCH_SECTION_END

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        # Upstream stamps "# CLAUDE" via filepath.stem; for AGENTS.md the
        # full name is the natural title (this branch is port-original:
        # upstream never created AGENTS.md).
        header = f"# {path.name}\n"
        _atomic_write(path, header + blurb.strip() + "\n")
        return True

    content = path.read_text(encoding="utf-8-sig")
    has_start = start in content
    has_end = end in content
    if has_start != has_end:
        raise OpencodeInstallError(
            f"{path}: unpaired hyperresearch section marker "
            f"(start={has_start}, end={has_end})"
        )

    if has_start:
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        new_content = pattern.sub(lambda _: blurb.strip(), content)
        if new_content == content:
            return False
        _atomic_write(path, new_content)
        return True

    separator = "\n\n" if not content.endswith("\n") else "\n"
    _atomic_write(path, content + separator + blurb.strip() + "\n")
    return True
