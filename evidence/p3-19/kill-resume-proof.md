# P3-19 mid-run kill -> exact resume proof
Run: mrna-vaccine-cold-chain-f82458 (smoke gear, full 16-step pipeline), project /tmp/opencode/e2e-smoke.
KILL: opencode session PID killed after manifest showed steps {"1": done, "2": running}
(width-sweep in flight; live searches streaming in log).
RESUME PROOF (captured live immediately after kill):
  hpr run resume mrna-vaccine-cold-chain-f82458 -j =>
  {"next_step": "2", "done_steps": ["1"],
   "remaining_steps": ["2","3","4","5","6","7","8","9","10","11","12","13","14","15","16"], ...}
=> resume lands on EXACTLY the next pending step.
CONTINUATION: fresh `opencode run --command hyperresearch "RESUME MODE: …"` session picked up
at step 2 (log shows width-sweep searches resuming); raw stdout archived as
e2e-smoke-run.log / e2e-smoke-resume-run.log (copied post-completion with final artifacts).
Note: first capture file lost to /tmp cleanup during P3-20 space pressure; this note plus
events.jsonl (step transitions) are the durable record; JSON line above is verbatim from the
live session.
