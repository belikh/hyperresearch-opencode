# HYPERRESEARCH → OPENCODE — Progress Watch

Live status page for the port of
[github.com/jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch)
(v0.10.0, reference pinned at `15010c5142244b88265f7abadf7b7aa1a8237fde`)
to opencode. Scope and citations per piece live in [PARITY.md](PARITY.md).

**Last updated:** 2026-08-22 — P1-7 remediation landed: gauntlet r1 defects D1–D6 fixed in-port (profile overlay error contracts + dict-range ordering + knob non-negativity; indexgen tag slugs + render-then-swap crash-safe rebuild + markdown/YAML interpolation escaping; levers fail-loud on unknown keys) AND P1-5 hardening closed the twin-site SSRF filings from P1-4's sweep (oa/scholar httpx lanes routed through _netguard.guarded_get with per-hop revalidation; scholar doi.org exact-host classifier); all 34 new regressions falsified against pre-fix code; gates green (483 passed / 96 skipped, ruff+mypy strict clean), details in PORTING-NOTES.md §P1-7 remediation + §P1-5 hardening. Prior state: P1-7 built: profiles/render/levers/templates + indexgen ported near-verbatim; planner-decided `[models]` alias table landed with EMPTY-INHERIT ModelMap defaults (upstream sonnet/opus pins dropped, keys recognized, configs round-trip); golden prompts frozen — 8/8 skill goldens byte-match upstream verbatim, 10 agent goldens regenerated once on exactly the `model:` frontmatter line each (18/18 byte-match vs current output, evidence in evidence/p1-7/)

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
| P1-4 | Web layer: providers/base + fetcher (+PDF text extraction, junk gates) + tests | built | pending review; near-verbatim port; crawl4ai imports made lazy so the provider module (and its offline PDF/smart-wait helpers) import without the uninstallable-on-3.14 extra — factory ImportError contract unchanged; P1-4 hardening landed — gauntlet r1 (ours won blind): HIGH SSRF containment via new web/_netguard.py (validate_url_public requires http(s) + every resolved address globally routable; manual per-hop revalidation ≤5 hops on crawl4ai PDF lane and both builtin HTML lanes incl. urllib validating redirect handler; DNS rebinding documented out of scope), MEDIUM invisible-padding junk-gate fix (strip_invisible before length accounting + signal matching in looks_like_junk and looks_like_login_wall), LOW arXiv exact-host/suffix match (notarxiv.org.evil.com no longer lane-chooses or gets rewritten), env-conditional mypy dirt retired via [[tool.mypy.overrides]] for tavily/exa with inline ignore dropped — proven clean in 3 SDK-presence configurations and dirty pre-fix in 2 (stash rounds); all regressions falsified against pre-fix code (13 failed / 43 passed in the window); known-inherited issues filed; 449 passed / 96 skipped, ruff+mypy strict clean | PORTING-NOTES.md §P1-4, evidence/gauntlet/P1-4-verdict-r1.md |
| P1-5 | Open-access recovery (Unpaywall/Europe PMC) + scholar enrichment + backfilled tests | built | pending review; near-verbatim port of core/{oa,scholar,enrich}.py (annotation-only strict-mypy deltas); test_oa_recovery (61) + test_scholar_enrichment (10) byte-identical, TestDoiExtraction + FTS-ranked-search backfilled into test_source_ranking.py; all HTTP/DNS/PDF/JATS stubbed — 93 offline tests proven inside `unshare -rn`; one ownership exception: P1-4's scheduled `type: ignore` retirement in core/fetcher.py (mechanical comment removal); P1-5 hardening landed with the P1-7 remediation wave — twin-site SSRF closure granted from P1-4's sweep: oa._http_get_text and scholar._http_get_json routed through _netguard.guarded_get (start URL + every redirect hop validated, UnsafeUrlError stays soft-fail), scholar doi.org classifier exact/suffix match (notdoi.org.evil.com no longer routes its path through DOI extraction), regressions falsified pre-fix; 335 passed / 6 skipped at piece landing | PORTING-NOTES.md §P1-5, §P1-5 hardening |
| P1-6 | Untrusted-source fencing (core/untrusted) | built | pending review; module + full upstream test file byte-identical (zero strict-mypy deltas needed); exhaustive consumer trace: only runtime consumers are cli/note.py::show and cli/search.py want_body path — both later pieces, engagement points + wrap-after-truncation ordering constraint documented in PORTING-NOTES.md §P1-6; 6 upstream weak spots filed, not fixed — P1-6 hardening landed: fence-probe F-01 (padded-URL fail-open → fail-closed) + F-02 (body ANSI/OSC control-byte sanitization, strip-before-neutralize order documented) fixed with stash-round falsifying tests; probes P9/P10 now NEUTRALIZED; W1/W3/W5/W6 remain filed | PORTING-NOTES.md §P1-6 |
| P1-7 | Profiles/render/levers/templates + indexgen (+ `[models]` alias table, golden prompts frozen) | built | pending review; near-verbatim port; ONE behavioral delta (planner-decided): `[models]` vault-global alias table + empty-inherit ModelMap defaults, upstream keys recognized/round-trip; golden outcome: 8/8 skill goldens byte-match upstream verbatim (not regenerated), 10 agent goldens regenerated once on the single `model:` line each ([models] delta), 18/18 verified vs current output; test_prompt_golden staged skipped until hooks/skills piece; levers/profiles CLI + claims-dependent classes deferred byte-faithful; new offline indexgen smoke tests (upstream ships none); P1-7 remediation landed from gauntlet r1: D1 non-table `models` overlay now ProfileError'd at the merge boundary (was bare TypeError outside wrapper), D2 dict-of-Range ordering validated per entry, D3 knob non-negativity with upstream-zero semantics documented (chapters (0,0), bracket thresholds, off-caps stay legal), D4 tag slugification (same slugify as note ids) + render-then-swap crash-safe build_all (mid-build failure leaves prior generation byte-identical; slash-tag no longer vault-indexless), D5 markdown/YAML interpolation flattening+escaping, D6 unknown lever keys fail loud incl. None-valued; twin-site SSRF closure landed under §P1-5 hardening; all 34 new regressions falsified pre-fix; 483 passed / 96 skipped, ruff+mypy strict clean | PORTING-NOTES.md §P1-7, §P1-7 remediation, evidence/p1-7/, evidence/gauntlet/P1-7-verdict-r1.md |
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
