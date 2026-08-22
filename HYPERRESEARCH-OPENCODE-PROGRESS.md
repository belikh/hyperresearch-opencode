# HYPERRESEARCH → OPENCODE — Progress Watch

Live status page for the port of
[github.com/jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch)
(v0.10.0, reference pinned at `15010c5142244b88265f7abadf7b7aa1a8237fde`)
to opencode. Scope and citations per piece live in [PARITY.md](PARITY.md).

**Last updated:** 2026-08-22 — P1-5 built: open-access recovery (Unpaywall/Europe PMC) + scholar enrichment ported near-verbatim with byte-identical offline test files (93 new/backfilled tests proven network-free inside an `unshare -rn` namespace); deferred TestDoiExtraction + FTS-ranked-search backfilled; gates green (335 passed / 6 skipped, ruff+mypy strict clean), details in PORTING-NOTES.md §P1-5

## Legend

| State | Meaning |
|---|---|
| pending | Not started; no builder has picked it up. |
| in-progress | Builder actively working; not yet critic-reviewed. |
| built | Implementation landed; awaiting or passed critic review. |
| critic-won | Critic verified the piece against its acceptance criteria. |
| critic-lost-deferred | Critic rejected or the piece was consciously deferred with justification recorded in PARITY.md. |
| blocked | Waiting on another piece, a decision, or external access. |

Titles marked "—" are assigned by the plan owner as pieces are scoped;
evidence pointers fill in at first commit touching the piece.

## Piece status

| Piece ID | Title | State | Critic verdict summary | Evidence pointer |
|---|---|---|---|---|
| P0-1 | Parity pack: PARITY.md inventory + this progress page | in-progress | — | `PARITY.md`, `HYPERRESEARCH-OPENCODE-PROGRESS.md` (this commit) |
| P0-2 | — | critic-won | blind critic chose ours; split-brain finding accepted->fix assigned | evidence/gauntlet/P0-2-verdict-r1.md |
| P0-3 | Spikes S0-1..S0-6 + toolchain policy alignment | built | countersigned (FIX-FIRST findings accepted, amendments landed same commit) | docs/spikes/, evidence/spikes/, evidence/gauntlet/P0-3-countersign.md, PORTING-NOTES.md §P0-3 |
| S0-1 | Nested subagents (RISK R1) | built | REFUTED: child session export shows zero tool calls; level-1 delegation works (NESTED_OK round-trip). Countersigned; amendments landed — flattened-chain consequence struck, replaced by three-artifact degradation plan + DRAFT_ORCHESTRATOR restrictive resolution + render-time shim patching | docs/spikes/S0-1-nested-subagents.md, evidence/spikes/S0-1-*, evidence/gauntlet/P0-3-countersign.md |
| S0-2 | Agents dir naming (`agent` vs `agents`) | built | CONFIRMED: both dirs in one listing; cold-init miss seen once (coordinator), not reproduced; installer retry rule. Countersigned; no amendments required | docs/spikes/S0-2-agents-dir-naming.md, evidence/spikes/S0-2-agent-list-names.txt, evidence/gauntlet/P0-3-countersign.md |
| S0-3 | Tool-lock mechanisms (RISK R2) | built | CONFIRMED: frontmatter write/edit locks + plugin `tool.execute.before` throw all denied on live transcripts. Countersigned; amendments landed — deny-sets corrected per upstream locks (edit KEPT for patcher/polish-auditor; synthesizer {edit,bash} denied), bogus bash-builds rationale deleted, S0-3c bash probes both CONFIRMED (frontmatter removes tool; plugin throws) | docs/spikes/S0-3-tool-lock.md, evidence/spikes/S0-3*, evidence/gauntlet/P0-3-countersign.md |
| S0-4 | Skill-load freshness (static) | built | CONFIRMED(static)-DYNAMIC-DEFERRED to P3 E2E: both SKILL.md path patterns proven via `opencode debug skill` locations. Countersigned; no amendments required | docs/spikes/S0-4-skill-load.md, evidence/spikes/S0-4-debug-skill-project-and-global.txt, evidence/gauntlet/P0-3-countersign.md |
| S0-6 | Packaging on Python 3.14 | built | CONFIRMED tiered: pymupdf wheel works (round-trip), Crawl4AI real install FAILS at lxml build (dry-run-only false pass recorded). Countersigned; amendment landed — `[all]` row upgraded to REAL-install proof in clean venv /tmp/opencode/s06-clean (exit=0, no crawl4ai, hpr CLI OK) | docs/spikes/S0-6-packaging.md, evidence/spikes/S0-6-*, evidence/gauntlet/P0-3-countersign.md |
| P1-1 | Foundation layer: models + core | critic-won | blind r2 win; 4 latent upstream defects fixed as deltas, 1 filed | evidence/gauntlet/P1-1-verdict-r2.md |
| P1-2 | Search layer (fts/filters) + embeddings | built | pending review; near-verbatim port incl. deferred test_fts.py; similarity.py drift re-check clean; P1-3 side-fixes (LSH banding guard, linker determinism) landed with regression tests; P1-2 hardening landed — r1 findings F1 (bm25 weights coerced pre-SQL), F2 (bare-date before covers whole final day), F4 (has_backlinks=False raises, upstream truthy-only intent documented), F3 still filed; each with stash-round falsifying tests | PORTING-NOTES.md §P1-2, evidence/gauntlet/P1-3-verdict-r1.md |
| P1-3 | Graph layer: linker/graphrank/quality/independence (+ similarity) | critic-won | blind r1 win; 2 latent upstream defects found (MEDIUM LSH banding all-pairs, LOW ref_vocab unordered-SQL nondeterminism), both fixed as P1-2 side-deltas with regression tests | evidence/gauntlet/P1-3-verdict-r1.md, PORTING-NOTES.md §P1-2 |
| P1-4 | Web layer: providers/base + fetcher (+PDF text extraction, junk gates) + tests | built | pending review; near-verbatim port; crawl4ai imports made lazy so the provider module (and its offline PDF/smart-wait helpers) import without the uninstallable-on-3.14 extra — factory ImportError contract unchanged; 211 passed / 6 skipped, ruff+mypy strict clean | PORTING-NOTES.md §P1-4 |
| P1-5 | Open-access recovery (Unpaywall/Europe PMC) + scholar enrichment + backfilled tests | built | pending review; near-verbatim port of core/{oa,scholar,enrich}.py (annotation-only strict-mypy deltas); test_oa_recovery (61) + test_scholar_enrichment (10) byte-identical, TestDoiExtraction + FTS-ranked-search backfilled into test_source_ranking.py; all HTTP/DNS/PDF/JATS stubbed — 93 offline tests proven inside `unshare -rn`; one ownership exception: P1-4's scheduled `type: ignore` retirement in core/fetcher.py (mechanical comment removal); 335 passed / 6 skipped, ruff+mypy strict clean | PORTING-NOTES.md §P1-5 |
| P1-6 | Untrusted-source fencing (core/untrusted) | built | pending review; module + full upstream test file byte-identical (zero strict-mypy deltas needed); exhaustive consumer trace: only runtime consumers are cli/note.py::show and cli/search.py want_body path — both later pieces, engagement points + wrap-after-truncation ordering constraint documented in PORTING-NOTES.md §P1-6; 6 upstream weak spots filed, not fixed — P1-6 hardening landed: fence-probe F-01 (padded-URL fail-open → fail-closed) + F-02 (body ANSI/OSC control-byte sanitization, strip-before-neutralize order documented) fixed with stash-round falsifying tests; probes P9/P10 now NEUTRALIZED; W1/W3/W5/W6 remain filed | PORTING-NOTES.md §P1-6 |
| P1-7 | — | pending | — | — |
| P1-8 | — | pending | — | — |
| P1-9 | — | pending | — | — |
| P1-10 | — | pending | — | — |
| P1-11 | — | pending | — | — |
| P1-12 | — | pending | — | — |
| P2-13 | — | pending | — | — |
| P2-14 | — | pending | — | — |
| P2-15 | — | pending | — | — |
| P2-16 | — | pending | — | — |
| P2-17 | — | pending | — | — |
| P3-18 | — | pending | — | — |
| P3-19 | — | pending | — | — |
| P3-20 | — | pending | — | — |
| P3-21 | — | pending | — | — |

## Known non-goals (carried on every piece)

Browser-fetcher lane · banner/benchmark asset scripts · pre-3.0 archive
migration internals (none exist upstream — vacuous) · crawl4ai headful
login-profile lane (documented via `setup` instead) · PyPI publish.
Full justifications: PARITY.md §16.
