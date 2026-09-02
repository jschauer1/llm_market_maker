---
title: Soft relative value on near-dated date ladders
lane: new-theory
created: 2026-09-01
created_by: setup
status: open
---
calendar-arb's hard-arbitrage premise was falsified (zero violations across 10 snapshots; near-dated ladders turn out to be same-event siblings priced at exactly 1.000). Its revisit angle is a different theory and is unbuilt: ask whether the implied conditional hazard between two deadlines is ever absurd, using the 295 near-dated same-event pairs already sitting at cost 1.000 as a ready-made dataset. Treat as a NEW theory with its own pre-registration -- mechanism, evidence and risk profile all differ from the arbitrage version. Check first whether structural_arb's within-event nesting scan already covers the population. Source: idea 21 revisit_angle, tickets/study/answer/2026-08-27-calendar-arb-firing-rate/.

## BLOCKER, added 2026-09-02: the 295-pair dataset this ticket points at is unverified

This spec offers "the 295 near-dated same-event pairs already sitting at
cost 1.000 as a ready-made dataset". **Do not use that figure without
re-deriving it.** It comes from `tickets/study/answer/2026-08-27-calendar-arb-firing-rate/`
Result 2, which rebuilt boards with `WHERE captured_at = ?`. Dedup-on-write
(shipped 2026-08-30) made that query return only the markets that *moved*
at a pull, so those captures now re-read as few as 3,254 markets against a
real board of 107,656. The numbers were right when made and are not right
now. `probe_as_of.py` supersedes `probe.py` and uses `snapshot.board_as_of`,
but its `main()` does not compute Result 2's table — so that half is still
outstanding. Full detail and scope:
`2026-09-02-calendar-arb-295-pair-table-unverified.md`.

The hard-arbitrage premise being falsified is *not* in doubt (zero
violations across 10 snapshots, and rule 0 has since been confirmed from
four more directions). What is unverified is only the **pair count and the
1.000 cost table** this spec wants as its input population. Re-derive it
before pre-registering anything, or the power calculation is built on a
board that was ~90k markets short.
