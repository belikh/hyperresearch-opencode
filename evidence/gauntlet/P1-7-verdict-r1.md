# P1-7 gauntlet r1 — VERDICT: COMPARISON VOID, AUDIT VALID
## Coordinator disclosure
Staged treeA was a pre-P1-7 snapshot (stale rsync), so the A/B comparison itself was
meaningless — coordinator staging error, second process failure after P1-1 r1 VOID.
Protocol amended: staging must be re-rsynced immediately before every dispatch.
## What survives (critic adapted: audited CURRENT repo against upstream directly)
All six claimed deltas map 1:1 to PORTING-NOTES §P1-7; skill goldens byte-match
upstream through our engine (8/8); agent goldens differ exactly on declared model:
lines (10/10, line numbers verified); [models] resolution matrix passes except LB-1;
404 passed/96 skipped reconciles exactly; mypy strict 0 errors/45 files.
## Defects found (execution-verified)
D1 MEDIUM (OUR regression) profiles.py:467 non-table models overlay -> bare TypeError
   escapes ProfileError wrapper (upstream wraps this case).
D2 MEDIUM (inherited) profiles.py:188-193 _range_ordered misses dict-of-Range fields;
   inverted ranges like word_targets={short=[9000,200]} accepted into prompts.
D3 MEDIUM (inherited) profiles.py:110-187 no non-negativity validation on scalar knobs.
D4 HIGH-operational (inherited) indexgen/generator.py:115 tag containing '/' crashes
   build_all AFTER unlinking existing indexes -> vault left with zero indexes.
D5 LOW-MED (inherited) indexgen raw title/tag interpolation corrupts markdown/YAML frontmatter.
D6 LOW (inherited) levers.py:211-215 unknown lever keys silently no-op (contradicts fail-loud posture).
Dispositions: D1-D6 all fix in-port (regression + cheap correctness wins), falsification-proven.
Guard-rail accepted: jinja templates package-owned; when hooks land, vault text must never become template source.
