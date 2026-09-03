---
title: Soft relative value on near-dated date ladders
lane: new-theory
created: 2026-09-01
created_by: setup
status: open
---
calendar-arb's hard-arbitrage premise was falsified (zero violations across 10 snapshots; near-dated ladders turn out to be same-event siblings priced at exactly 1.000). Its revisit angle is a different theory and is unbuilt: ask whether the implied conditional hazard between two deadlines is ever absurd, using the 295 near-dated same-event pairs already sitting at cost 1.000 as a ready-made dataset. Treat as a NEW theory with its own pre-registration -- mechanism, evidence and risk profile all differ from the arbitrage version. Check first whether structural_arb's within-event nesting scan already covers the population. Source: idea 21 revisit_angle, tickets/study/answer/2026-08-27-calendar-arb-firing-rate/.

## BLOCKER, added 2026-09-02 — CLEARED 2026-09-03 (see the section below)

This spec offers "the 295 near-dated same-event pairs already sitting at
cost 1.000 as a ready-made dataset". **Do not use that figure without
re-deriving it.** It comes from `tickets/study/answer/2026-08-27-calendar-arb-firing-rate/`
Result 2, which rebuilt boards with `WHERE captured_at = ?`. Dedup-on-write
(shipped 2026-08-30) made that query return only the markets that *moved*
at a pull, so those captures now re-read as few as 3,254 markets against a
real board of 107,656. The numbers were right when made and are not right
now. `probe_as_of.py` supersedes `probe.py` and uses `snapshot.board_as_of`,
but its `main()` does not compute Result 2's table — so that half is still
outstanding. Full detail and scope: the re-derivation that cleared this, in
`tickets/study/answer/2026-08-27-calendar-arb-firing-rate/STUDY.md`
("Addendum 2026-09-03").

The hard-arbitrage premise being falsified is *not* in doubt (zero
violations across 10 snapshots, and rule 0 has since been confirmed from
four more directions). What is unverified is only the **pair count and the
1.000 cost table** this spec wants as its input population. Re-derive it
before pre-registering anything, or the power calculation is built on a
board that was ~90k markets short.

## BLOCKER CLEARED, 2026-09-03 — the table reproduces exactly, and the dataset is verified

Session `fleet-w3-g4`, study lane. `probe_as_of.py --table` now computes
Result 2's horizon x scope table, and it was re-derived on
`snapshot.board_as_of` reconstructions of all 21 stored captures.

**On 2026-08-27T23:18:30Z — the exact board Result 2 was published from —
all eight cells reproduce, counts and minima both, totalling 1,944
pairs.** The near-dated same-event cell is **295 pairs at min cost
1.000**, exactly as the spec quotes it. The exact-stamp defect did not
distort this table: `probe.py` ran on 2026-08-27, before dedup-on-write
landed on 2026-08-30, so it saw the whole board on the day it ran. The
table is also unchanged when recomputed on only the 79% of that board the
broken query still returns — population structure is robust to a
truncated sample in a way Result 1's tail counts were not.

**So this spec may use the 295-pair dataset as written.** On today's
board (2026-09-03) the same cell holds 280 pairs at min cost 1.010; across
21 captures it runs 202–305 pairs at 0.990–1.010, so size and price level
are both stable.

**Two things to carry into the pre-registration:**

1. **Exclude rolling per-period series at the point of use — this is now
   rule 0g** in `tickets/new-theory/README.md`. Two captures showed 23
   "near-dated cross-event pairs" that are `KXTRUMPSAYMONTH` /
   `KXTRUMPSAYCOMPANY` monthly resets whose titles state a cumulative
   deadline ("before Oct 1") while each contract only counts its own
   month. They are not ladders, both legs can lose, and a strike-aware
   key does not catch them — compare `open_time`, not just
   `close_time`. They surface only during the ~10-hour monthly rollover
   when both legs are listed, so a probe run on any other day sees a
   clean population and concludes wrongly.
2. **The population is priced at or above par almost everywhere, which
   is the thing this spec has to beat.** Min cost across 295 near-dated
   pairs is 1.000 and the single sub-par near-dated pair found anywhere
   in 21 captures (`KXMLBDEBUT-AMILLER`, 0.990 gross) is **0.997 net of
   fees — 0.3 cents held for two months**, on a market carrying no volume
   or open interest at all. A soft-relative-value thesis cannot lean on
   dispersion that is not there; it needs to argue the *conditional
   hazard between the two deadlines* is absurd, which is a different
   claim from the prices being inconsistent, and rule 0f still applies
   to whatever it proposes to trade.

