# HYPERRESEARCH → OPENCODE — Progress Watch

Live status page for the port of
[github.com/jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch)
(v0.10.0, reference pinned at `15010c5142244b88265f7abadf7b7aa1a8237fde`)
to opencode. Scope and citations per piece live in [PARITY.md](PARITY.md).

**Last updated:** 2026-08-22 00:55 UTC — gauntlet r1: P0-2 critic-won; P0-1 lost round 1, 5+1 findings fixed, awaiting round 2

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
| P0-3 | — | pending | — | — |
| S0-1 | — | pending | — | — |
| S0-2 | — | pending | — | — |
| S0-3 | — | pending | — | — |
| S0-4 | — | pending | — | — |
| S0-6 | — | pending | — | — |
| P1-1 | — | pending | — | — |
| P1-2 | — | pending | — | — |
| P1-3 | — | pending | — | — |
| P1-4 | — | pending | — | — |
| P1-5 | — | pending | — | — |
| P1-6 | — | pending | — | — |
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
