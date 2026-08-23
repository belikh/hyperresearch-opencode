# P3-20 ship-gate negatives — all blocked, each naming its check
Base: passing light-tier vault /tmp/opencode/e2e-light (tag jet-engine-turbine-metals-a1b636).
Method: in-place mutate -> `hpr run verify -j` (names) + `hpr run finish` (exit) -> restore -> control.

NEG-1 hallucinated-quote: fabricated Vasquez testimony quote appended to report.
  -> verify FAIL quote-integrity; finish EXIT=1. Restore -> control PASSED.
NEG-2 retracted-citation: cited source note marked is_retracted=1 in synced DB
  (mutation must hit notes.is_retracted, the store _check_retracted_citations reads).
  -> verify FAIL retracted-citations ("3 error(s) — first: Final report cites [[ceramic-matrix-composit…");
     finish EXIT=1, envelope passed:false. Restore -> control PASSED.
NEG-3 over-length: report padded to ~12,880 words.
  -> verify FAIL length-in-range (+citation-density dilution); finish EXIT=1. Restore -> control PASSED.
Controls after every restore: verify battery PASSED.
