"""opencode lockdown-plugin renderer — layer 2 of the tool-lock belt-and-braces.

Emits the canonical JavaScript opencode plugin that HARD-denies (throws in
``tool.execute.before``) the tools each locked roster agent must never reach,
even when layer 1 (the per-agent frontmatter locks emitted by
:mod:`hyperresearch.core.opencode_install`) is missing, misconfigured, or
bypassed by a future regression. S0-3 proved both layers on opencode 1.18.21:
frontmatter ``tools.X: false`` removes the tool structurally (a1/a2/c1), while
a plugin throw surfaces as a real executed-attempt error (``✗ Write … failed``
/ ``✗ echo … failed``) that also reaches the model (probes b/c2). This piece
ships the second belt as a data-driven template.

Mechanism (pinned by the plugin type package bundled with the host install,
``@opencode-ai/plugin/dist/index.d.ts``): the ``tool.execute.before`` hook
receives ``{tool, sessionID, callID}`` — NO agent identity — so the plugin
tracks the calling agent by recording ``chat.params`` inputs
(``{sessionID, agent, ...}``, fired for every LLM request, primary sessions
and task-spawned child sessions alike) in a sessionID -> agent map consulted
at deny time. Agents absent from the matrix are untouched: no entry, no
lookup hit, no throw.

Deny matrix — mirrors the ORIGINAL S0-3 tool-lock intent (as amended by
countersign F-CS2 and narrowed by the P2-13 mission), pinned by tests.
F-B1 (2026-09-02): this plugin is now the ONLY layer enforcing the granular
edit-vs-write split. opencode's permission model groups edit+write+patch
under a single ``edit`` permission key, so the frontmatter layer cannot
express "Write denied, Edit enabled" (or the inverse) — any attempt either
no-ops (unknown key) or blocks both tools at once. This plugin denies by
granular tool NAME, which is the sole correct mechanism for the split:

============================  =========================
Agent                         Denied tools
============================  =========================
hyperresearch-patcher         write   (edit/bash open)
hyperresearch-polish-auditor  write   (edit/bash open)
hyperresearch-synthesizer     edit + bash (write open)
============================  =========================

Unknown agents are unaffected by design — the plugin is a targeted backstop,
not a sandbox.

Directory spelling: project plugins load from ``.opencode/plugins/``
(plural) on this opencode version — proven live by denial transcripts at
P2-15 close (S0-3b fired from the plural dir; the singular-vs-plural probe is
archived under ``evidence/p2-15/``). :func:`write_plugin` takes the target
plugins directory explicitly so P2-16's installer stays in control of where
it lands; ``PLUGIN_SUBDIR`` records the proven spelling for that call site.

The public surface is deterministic: identical inputs render byte-identical
bytes (the source is a frozen constant with no timestamps or environment
reads) and every write lands via temp-file + ``os.replace`` so a failure
never leaves a torn file behind — same contract as the agent/skill
renderers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hyperresearch.core.opencode_install import _atomic_write

__all__ = [
    "PLUGIN_DENY_MATRIX",
    "PLUGIN_FILENAME",
    "PLUGIN_SOURCE",
    "PLUGIN_SUBDIR",
    "PluginManifest",
    "render_plugin",
    "write_plugin",
]

# ---------------------------------------------------------------------------
# Deny matrix — single Python-side mirror of the JS table below.
#
# Derived-from and pinned-to AGENT_SPECS tools_deny by
# tests/test_core/test_opencode_plugin.py; keep the two in lockstep. Order is
# roster order (patcher, polish-auditor, synthesizer).
# ---------------------------------------------------------------------------

PLUGIN_DENY_MATRIX: dict[str, tuple[str, ...]] = {
    "hyperresearch-patcher": ("write",),
    "hyperresearch-polish-auditor": ("write",),
    "hyperresearch-synthesizer": (
        "edit",
        "bash",
    ),
}

#: File name the plugin installs as inside the project's plugins directory.
PLUGIN_FILENAME = "hyperresearch-lockdown.js"

#: Proven directory spelling (relative to the project ``.opencode/`` dir).
PLUGIN_SUBDIR = "plugins"

# The JS table between Object.freeze( ... ) is STRICT JSON — the test suite
# parses it back out of PLUGIN_SOURCE and diffs it against
# PLUGIN_DENY_MATRIX. Do not add comments or trailing commas inside it.
PLUGIN_SOURCE = """\
// hyperresearch-lockdown.js — P2-15 belt-and-braces tool lock (layer 2).
//
// Hard-denies the tools each locked hyperresearch roster agent must never
// reach, even if its agent-file frontmatter locks (layer 1) are absent or
// regressed. Hook shape proven live on opencode 1.18.21 by spike S0-3
// (probes b + c2): throwing inside "tool.execute.before" aborts the tool
// call with a hard error that reaches both the transcript and the model.
//
// Mechanism: "tool.execute.before" input carries {tool, sessionID, callID}
// but NO agent identity, so this plugin records chat.params inputs
// ({sessionID, agent}) — fired for every LLM request, including
// task-spawned child sessions — and consults that map at deny time.
//
// Unknown agents are unaffected: no matrix entry, no lookup hit, no throw.
// Edit the Python template (hyperresearch.core.opencode_plugin), not this
// installed copy.

const DENY_MATRIX = Object.freeze({
  "hyperresearch-patcher": ["write"],
  "hyperresearch-polish-auditor": ["write"],
  "hyperresearch-synthesizer": ["edit", "bash"]
});

export default async function HyperresearchToolLock() {
  const sessionAgent = new Map();
  return {
    "chat.params": async (input) => {
      const sessionID = input && input.sessionID;
      const agent = input && input.agent;
      if (
        typeof sessionID === "string" &&
        typeof agent === "string" &&
        agent.length > 0
      ) {
        sessionAgent.set(sessionID, agent);
      }
    },
    "tool.execute.before": async (input) => {
      const sessionID = input && input.sessionID;
      if (typeof sessionID !== "string") return;
      const agent = sessionAgent.get(sessionID);
      if (agent === undefined) return;
      if (!Object.hasOwn(DENY_MATRIX, agent)) return;
      const denied = DENY_MATRIX[agent];
      if (!Array.isArray(denied) || !denied.includes(input.tool)) return;
      throw new Error(
        "DENIED_BY_PLUGIN: tool '" + input.tool +
          "' is hard-denied for agent '" + agent +
          "' by hyperresearch-lockdown.js (layer 2)"
      );
    },
  };
}
"""


@dataclass(frozen=True)
class PluginManifest:
    """Result of one :func:`write_plugin` pass (exactly one side is set)."""

    written: Path | None
    unchanged: Path | None

    @property
    def path(self) -> Path:
        """The installed plugin file, whichever side of the pass produced it."""
        return self.written if self.written is not None else self.unchanged  # type: ignore[return-value]


def render_plugin() -> str:
    """Return the canonical plugin bytes.

    Deterministic seam kept parallel to the other renderers: the source is a
    frozen constant today; any future parameterization renders HERE, and the
    determinism tests already pin byte-for-byte stability across calls.
    """
    return PLUGIN_SOURCE


def write_plugin(plugins_dir: Path) -> PluginManifest:
    """Install the lockdown plugin into ``plugins_dir`` (idempotent).

    ``plugins_dir`` is the full target directory (P2-16 passes
    ``<project>/.opencode/plugins`` — the proven spelling,
    ``PLUGIN_SUBDIR``). Byte-identical existing files are left untouched and
    reported under ``unchanged``; anything else is replaced atomically via
    temp file + ``os.replace``.
    """
    content = render_plugin()
    path = plugins_dir / PLUGIN_FILENAME
    plugins_dir.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return PluginManifest(written=None, unchanged=path)
    _atomic_write(path, content)
    return PluginManifest(written=path, unchanged=None)
