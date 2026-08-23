# P2-13 countersign — VERDICT: SIGN-OFF WITH FIXES (all closed same session)
Protocol note: retargeting piece (Claude installer -> opencode renderer); blind A/B vs a
Claude-target artifact is meaningless — verification-style countersign per P0-3 precedent;
coordinator reconciliation on record.
C1 roster PASS (live upstream install diffed: 15 = 16 minus browser-fetcher, names 1:1).
C2 deny-sets PASS parsed from generated files: patcher/polish-auditor tools{write:false}
   with edit kept; synthesizer edit+bash denied via tools AND permission mirror.
C3 model resolution PASS both branches through public API + vault config.toml path.
C4 body fidelity FAIL->FIXED: polish-auditor doubled-bullet quirk (- - ) had been silently
   normalized; replicated byte-exactly; live-vs-render probe drifted 1/15 pre-fix, 0/15 post.
C5 determinism/atomicity PASS independently reproduced (hash-seed variation; per-file atomic,
   no whole-set rollback — documented).
C6 naming/hidden PASS (15/15 pattern + hidden:true w/ pipeline-addressed descriptions).
C7 claims re-audit PASS (zero CLAUDE refs; cross-process determinism reproduced).
REmediation wave X-1..X-4 closed: 15/15 goldens now pinned vs live-captured upstream output
(tests/fixtures/agent_goldens_opencode/), S0-3 spike table amended (dated note), PORTING-NOTES
count corrected, docstring per-file atomicity clarified.
Accepted risks on record: permission:{write:deny} key inert-if-ignored (real belt = tools map);
per-file-not-per-set atomicity.
