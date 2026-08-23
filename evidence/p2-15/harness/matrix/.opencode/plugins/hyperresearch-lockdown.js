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
