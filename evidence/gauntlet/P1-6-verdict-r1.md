# P1-6 gauntlet r1 — VERDICT: OURS (blind win) — SECURITY-CRITICAL second pass
Staging: /tmp/opencode/gauntlet/P1-6, fresh rsync, scrubbed, sealed. Sidemap: A=ours, B=upstream.
Critic empirically probed both modules (cross-battery runs + adversarial payloads).
VERDICT: A (ours) — B fails OPEN on whitespace-padded source URLs and ships raw ANSI/OSC/NUL;
A neutralizes those (F-01/F-02 hardening confirmed by independent critic).
This satisfies the plan's DOUBLE adversary requirement for P1-6:
pass 1 = forged-fence probes F-01/F-02 (+stash-falsified fixes), pass 2 = this blind review.
NEW findings on OURS to close (hardening wave 2):
- U1 HIGH: _FENCE_TAG_RE defeated by Unicode format/confusables inside tag
  (<U+200B/, soft hyphen, U+FEFF) -> forged closer survives neutralization.
- U2 MED: C1 controls (U+0080-U+009F, e.g. lone CSI 0x9B) unhandled (both trees).
- U3 LOW-MED: control-byte-prefixed source string classifies not-untrusted (both trees).
- U4 MED: replacement tag `-inner` itself matches fence regex -> re-wrap degrades
  (-inner-inner); neutralization not fixpoint-stable.
- U5 LOW: html.escape mangles query URLs in attribute provenance (both trees).
Truncation-awareness: remains a documented CONSUMER ordering constraint
(wrap-after-truncation in cli/note.py::show and cli/search.py when they land).
