# S0-1 — Nested subagents (RISK R1)

Question: can an opencode SUBAGENT spawn another subagent via the task tool?

Probed on opencode 1.18.21, host Linux, model `opencode/x-preview-f-free`,
2026-08-22. Scratch project: `/tmp/opencode/s01-nest`.

## Method

Two-step design, forced by a method correction discovered on the first run:

1. **Run 1 (spec'd attempt).** `.opencode/agents/nester.md` (`mode: subagent`,
   prompt: use your task tool to spawn agent `general` asking it to reply with
   exactly `NESTED_OK`; report the reply verbatim; if you have no task tool,
   reply exactly `NO_TASK_TOOL_AVAILABLE`). Invoked directly:
   `opencode run --model opencode/x-preview-f-free --agent nester "..."`.
2. **Run 2 (real nesting test).** Because run 1 revealed that a `mode:
   subagent` agent cannot be driven from the CLI (see F-METHOD), a second
   agent `driver.md` (`mode: primary`) was added and instructed to spawn
   `nester` via its task tool with the fixed message "Run your nesting probe
   now." and relay nester's final answer verbatim.

Ground truth read back from session exports (`opencode export <sessionID>`),
not from model prose alone. Retry-once policy on provider errors was armed but
never needed — no provider errors occurred.

### Finding F-METHOD (method correction)

```
$ opencode run --model opencode/x-preview-f-free --agent nester "Use your task tool to spawn ..."
!  agent "nester" is a subagent, not a primary agent. Falling back to default agent

> build · x-preview-f-free
•  Reply NESTED_OK test General Agent
✓  Reply NESTED_OK test General Agent
It replied: `NESTED_OK`
```

A `mode: subagent` agent cannot be the target of `--agent`; opencode falls
back to the default `build` agent. Incidentally this proves level-1 delegation
works: the parent session export shows one completed `task` tool call with
`subagent_type: "general"` returning `<task_result>NESTED_OK</task_result>`.
Raw files: `evidence/spikes/S0-1-run1-direct-agent-{stdout,stderr}.txt`,
`evidence/spikes/S0-1-run1-fallback-export.json`.

## Transcript (run 2 — does the SUBAGENT get a task tool?)

```
$ opencode run --model opencode/x-preview-f-free --agent driver "Run the nesting probe now."

> driver · x-preview-f-free
•  Run nesting probe Nester Agent
✓  Run nesting probe Nester Agent
The nester agent's final answer, verbatim:

NO_TASK_TOOL_AVAILABLE
```

Parent-session export (trimmed): exactly ONE tool call, completed —

```json
{ "tool": "task", "state": {
    "status": "completed",
    "input": { "description": "Run nesting probe", "prompt": "Run your nesting probe now.",
               "subagent_type": "nester" },
    "output": "<task id=\"ses_fd8d6d0afffesJt9Jqar2wWzzk\" state=\"completed\">\n<task_result>\nNO_TASK_TOOL_AVAILABLE\n</task_result>\n</task>" } }
```

Child-session export (`ses_fd8d6d0afffesJt9Jqar2wWzzk`) — the ground truth
that the subagent genuinely ran as agent `nester` and made ZERO tool calls:

```
$ opencode export ses_fd8d6d0afffesJt9Jqar2wWzzk   → 2 messages:
[user text agent=nester]      'Run your nesting probe now.'
[assistant text agent=nester] 'NO_TASK_TOOL_AVAILABLE'
TOOL CALLS IN NESTER CHILD SESSION: 0
```

Raw exports: `evidence/spikes/S0-1-run2-driver-stdout.txt`,
`evidence/spikes/S0-1-run2-parent-export.json`,
`evidence/spikes/S0-1-run2-nester-child-export.json`.

## Verdict: REFUTED

An opencode subagent cannot spawn another subagent. Level-1 delegation
(primary → subagent via task tool) works and returns results faithfully
(`NESTED_OK` came back through `general`). Level-2 nesting does not exist:
the spawned child's transcript contains zero tool invocations and it answers
`NO_TASK_TOOL_AVAILABLE`, matching its actual toolset.

## Fallback if refuted (ADOPTED — this is our reality)

- Investigators call `hpr fetch-batch` directly instead of delegating through
  a nested agent hop.
- Roster prompts carry a "## Degraded mode" clause describing direct calls.

Design consequence for later pieces: orchestration depth in the port is capped
at primary → subagent; any "researcher spawns fetcher" chain must be flattened
into sequential task calls from the primary session.

## Residual risk

- The child's self-report is model-generated. Mitigated by the exported child
  transcript showing zero tool calls, and by consistency across two runs.
- Probed on one free-tier model; toolset visibility (not model choice) governs
  the behavior, so provider variance risk is low.
- A future opencode version could grant nested task access — re-run this spike
  after any major version bump before relying on the flattened design.
