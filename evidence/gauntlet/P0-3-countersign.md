# P0-3 countersign review (adversary) — FIX-FIRST countersigned

Reviewer: gauntlet adversary pass over P0-3 spike docs (`docs/spikes/S0-1..S0-6`),
2026-08-22. Every finding below was re-grounded against upstream source before
being accepted as an amendment instruction.

## Findings requiring amendment (all accepted)

### F-CS1 — S0-1 internal contradiction (design consequence vs its own verdict)

S0-1's adopted fallback says investigators call `hpr fetch-batch` directly, yet
the design-consequence paragraph ordered chains "flattened into sequential task
calls from the primary session." That would serialize step-5 per-locus fetching
and break `source_budget` accounting (budgets are per-locus, tracked inside each
investigator's own procedure — hooks.py :395-399). Struck. Replacement is the
three-artifact degradation patch list, grounded in
`/tmp/opencode/hyperresearch-reference/src/hyperresearch/core/hooks.py`:

1. Roster `.opencode/agents/hyperresearch-depth-investigator.md` gets a
   degraded-mode clause.
2. `DEPTH_INVESTIGATOR_AGENT` template (hooks.py ~291-404; frontmatter tools
   line :306 lists Task; mandate at :401-404 forbids direct `hpr fetch` and
   demands Task delegation to `hyperresearch-fetcher`) must be ported WITH the
   delegation directive deleted and Task dropped from the tools line.
3. Fetch-batch economics kept via ONE `hpr fetch-batch` invocation instead of
   per-locus Task hops.

Additional contradiction recorded: `DRAFT_ORCHESTRATOR_AGENT` self-contradicts
— comment at hooks.py :1854-55 claims "Full tool access including Task", while
the procedure at :1974-76 says "You don't spawn subagents." Port resolves
restrictively: no Task capability or spawn language in the drafter prompt.
Also: the entry skill (`src/hyperresearch/skills/hyperresearch.md` :175)
requires shim files be pasted "VERBATIM ... never compose, summarize, or trim",
so degraded-mode edits cannot ride on prompt clauses — shims must be pre-patched
at render time.

### F-CS2 — S0-3 belt-and-braces wrong on two axes

Upstream locks patcher/polish-auditor to `[Read, Edit]` (hooks.py :1331, :1508)
and synthesizer to `[Read, Write]` (:2071-73). The spike's recommendation told
those roles to disable BOTH write and edit — which would break their actual job
(surgical Edit hunks on markdown reports) — and excused leaving bash open with a
bogus "need bash for builds" rationale (sed/redirect bypass restores everything
if bash stays). Corrected deny-sets:

| Role | Upstream lock | Frontmatter deny-set |
|---|---|---|
| patcher / polish-auditor | Read, Edit | `{write: false, bash: false}` — edit ENABLED |
| synthesizer | Read, Write | `{edit: false, bash: false}` |
| plugin denywrite.js | — | must throw on `tool == "write"` AND `tool == "bash"` |

New probe round S0-3c required (denial-transcript standard): does `bash: false`
actually remove the bash tool, and does a plugin throw on bash hard-deny?

### F-CS3 — S0-6 row 2 rests on dry-run only

The `[all]` claim ("resolves without crawl4ai") was proven by `pip install
--dry-run`, which the spike's own finding F-METADATA says proves nothing about
installability. Row 2 must be upgraded to a real-install proof in a CLEAN venv
(`/tmp/opencode/s06-clean`), installing the repo path with `[all]`.

## Disposition

FIX-FIRST countersigned: all three findings accepted verbatim; amendments
landed in the same commit as this countersign file. S0-3c probe outcomes and
the S0-6 clean-venv result are recorded in the respective spike docs with raw
transcripts under `evidence/spikes/`.
