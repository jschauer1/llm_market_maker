# calendar-arb does not fire, and its premise is false at every tradeable horizon

<!-- research-memory-route -->
> [Find related lessons and their applicability](../../../../knowledge/README.md). This document is
> source evidence: read its verdict and limits first, then the relevant method
> or result section. A useful short answer needs no duplicate summary.
<!-- /research-memory-route -->


**Date:** 2026-08-27 ·
**Tier:** A (no model in the measurement path) ·
**Verdict:** do not build the spec as written ·
**Code:** the investigation was deleted 2026-09-03; it lives at git rev `38028e6` - `git ls-tree -r --name-only 38028e6 tickets/study/answer/2026-08-27-calendar-arb-firing-rate` lists it, `git show 38028e6:<path>` returns any file

## Question

calendar-arb (spec: `git show 6e7d920:tickets/new-theory/completed/2026-08-24-calendar-arb.md`)
(backlog #12, effort S) proposes trading date-monotonicity violations:
P(X by June) ≤ P(X by July) is a hard logical constraint, so buying the
later-deadline YES and the earlier-deadline NO locks a profit whenever
`ask(YES, later) + ask(NO, earlier) < 1 − fees`.

Its premise is explicit: *"Kalshi lists these as separate events, priced by
separate crowds, with no cross-event margining — so date-monotonicity
violations at executable quotes are a hard-logic arbitrage no within-event
scanner sees."*

The spec's own first deliverable is measuring the firing rate from snapshot
history. That is cheap, so it was done **before** building anything.

## Method

Ten stored board snapshots, 2026-08-24T01:34Z → 2026-08-27T23:18Z
(96k–110k markets each). Within each, group markets into date-ladder
families and check every ordered pair.

**Grouping is strike-aware, and that matters.** A first, naive pass keyed
only on (series, title with the deadline clause removed) and produced three
"violations" — one of which was `KXU3MAX-30-20` ("unemployment reaches 20%
by 2030") paired against `KXU3MAX-27-4.5` ("reaches 4.5% by 2027"). Those
are **not nested**: different thresholds, and *both legs can lose*. Trading
that pair loses money outright. The strike (`floor_strike`, `cap_strike`,
`strike_type`) therefore joins the key. This is the by/in classifier trap
the spec calls "the whole risk concentrated in one place", and a naive
implementation walks straight into it.

Prices are the snapshot's own `yes_ask_dollars` / `no_ask_dollars` —
executable top-of-book, never mids. Fees are
`min(0.07·P·(1−P), 0.035)` per leg.

Reproduce with `probe.py`; raw findings in `data/`.

## Result 1 — the firing rate is zero at any usable buffer

| execution buffer | pairs checked | violations |
|---|---|---|
| 1¢ per leg (the spec's own starting buffer) | 18,877 | **0** |
| none at all | 18,877 | 7 |

The seven no-buffer hits are only **two distinct positions**; one recurs
across six consecutive snapshots.

| position | profit/basket | resolves | annualized |
|---|---|---|---|
| `KXDECLAREPRESFIRSTD-…-KHAR` (cross-event) | 1.21¢ | Nov 2028 | ~0.55%/yr |
| `KXFDAAPPROVE-MDMA` (same-event) | 0.60¢ | Jan 2031 | ~0.14%/yr |

Both are worse than holding cash, and neither survives a 1¢/leg buffer.
`structural_arb`'s live experience adds the rest: both of its own
top-of-book finds died on orderbook depth (~$0.02 and ~$0.30 fillable), and
nothing here suggests these would fare better.

## Result 2 — the premise is false where it would matter

Splitting all 1,944 ladder pairs on the newest board by horizon and by
whether the two legs share an event page:

| later-leg horizon | scope | pairs | min cost |
|---|---|---|---|
| **≤ 90d** | **same-event** | **295** | **1.000** |
| ≤ 90d | cross-event | **0** | — |
| 90d–1y | same-event | 668 | 1.000 |
| 90d–1y | cross-event | 39 | 1.050 |
| 1y–3y | same-event | 593 | 0.990 |
| 1y–3y | cross-event | 43 | 0.980 |
| > 3y | same-event | 292 | 0.960 |
| > 3y | cross-event | 14 | 1.040 |

**There is not one cross-event date-ladder pair inside 90 days.** Kalshi
lists near-dated date ladders as *sibling markets within a single event*
(`KXGROK-GROK5` carries "Before July" and "Before October" as siblings on
one page), which is the exact opposite of the spec's premise. Those
siblings sit on the same page, get compared by the same crowd, and are
priced **exactly consistently**: the minimum cost across all 295 near-dated
pairs is 1.000, never below.

Cross-event ladders — the ones the premise correctly describes as
uncompared — exist only at **1+ year** horizons, where the best violation
observed (0.980 gross) is dwarfed by years of carry.

Two conclusions follow, and together they close the theory:

1. Where the arbitrage would be worth taking (near-dated), the pairs are
   same-event and perfectly priced — and same-event nesting is already
   `structural_arb`'s territory, not a new lens.
2. Where the premise holds (cross-event), the horizon is measured in years
   and the mispricing in tenths of a cent per year.

## Verdict

**Do not build calendar-arb as specced.** Recorded against idea 21 as
`dead`, with the revisit angle below. This cost one session-hour and saved
building an effort-S theory that cannot fire.

## Revisit angle — the v2 is untouched by this

The spec's own deferred v2 — *soft* relative value, where a later deadline
trades implausibly close to an earlier one, implying an absurd conditional
hazard — is a **forecast** theory, not an arbitrage. It needs no hard
violation and is therefore completely unaffected by everything above.

It is also unusually well-supplied: the 295 near-dated same-event pairs
sitting at exactly cost 1.000 are a ready-made dataset for asking whether
the *implied conditional hazard* between two deadlines is ever absurd. That
is a real question this study does not answer and did not try to.

Anyone picking it up should treat it as a new theory with its own
pre-registration, not as calendar-arb v2 — the mechanism, the evidence, and
the risk profile all differ.

## Limits

- Four days of snapshots, all within one week. A rare violation regime
  (a mispriced ladder appearing after a news shock) would not show up.
  The Result 2 structural finding does not depend on the window, though:
  it is about how Kalshi *lists* these markets.
- The deadline is proxied by `close_time` rather than parsed from rules
  text. For genuine ladders these agree; a series where they diverge would
  be misordered, which would create false positives, not hide real ones.
- Title-regex subject matching is coarser than the rules-text classifier
  the spec asks for. It is deliberately *over*-inclusive (1,944 pairs from
  325 families), so it cannot be hiding violations by under-matching.

Note (2026-08-30): re-running this probe against post-compression snapshot rows requires routing raw_json/event_json reads through tools.snapshot.payload_text (spec 5.2 phase 3).

---

# Addendum 2026-09-01 — re-run on correctly reconstructed boards

*Maintenance lane, session `fleet-w3-g2`, ticket
`calendar-arb-probe-exact-stamp-board`. Facts only: this addendum does
**not** revisit the verdict, which stands. `probe.py` is left exactly as
run; `probe_as_of.py` supersedes it and produced everything below. Raw
output: `data/rerun-2026-09-01-board-as-of.txt`.*

**What was wrong.** `probe.py` rebuilds each board with
`WHERE captured_at = ?`. Dedup-on-write (spec 5.2 phase 2, 2026-08-30)
means a pull writes no row for a market whose payload did not change, so
that query returns *the markets that moved at that pull*. The probe ran on
2026-08-27, before dedup, so **its published numbers were correct when
made** — but every capture it walked is now re-read short, and the
truncation is severe and biased toward liquid markets:

```
2026-08-27T11:47:05Z    exact  3,254 markets    as_of 107,656 markets
2026-08-27T11:46:17Z    exact 19,005           as_of 107,660
2026-09-01T11:34:32Z    exact  5,580           as_of 103,940
```

**Result 1 changes as stated, and does not change as concluded.** Over the
20 captures now stored, on correctly reconstructed boards:

```
snapshots=20   pairs checked=38,124   violations=25   cross-event=22
median profit/basket=0.0134
```

So "the firing rate is zero" is **no longer literally true** and should be
read as *"~7 violations per 10,000 ladder pairs, none of them near-dated."*
What the violations are matters more than the count:

- **19 of 25 are one recurring pair**, `KXDECLAREPRESFIRSTD-28NOV07-KHAR`
  against `-28NOV01-KHAR`, at +0.004 to +0.023 per basket on a **2028**
  horizon. That is two years of carry for one to two points, which is the
  study's own Result 2 argument, not a counter-example to it.
- **3 are `KXTRUMPSAYMONTH` pairs whose NO leg asks 0.01.** A one-cent ask
  is the placeholder-quote trap this repo has now hit in three separate
  studies (the mirror image of the 0.980–0.995 artifact that made the
  series-bias pass-3 unreadable). Treat as artifact until depth is checked.
- The four earliest captures (2026-08-24) still return **zero** on the
  corrected board.

**Result 2 has NOT been re-derived, and that is the open piece.** The 295
near-dated same-event pairs at min cost 1.000 — the structural finding that
actually closes the theory, and the dataset
`tickets/new-theory/open/2026-09-01-calendar-arb-soft-relative-value.md`
proposes to reuse — came from a separate horizon/scope tabulation that
`probe.py`'s `main()` does not compute, so `probe_as_of.py` does not
reproduce it either. It was measured on a board that was **~90k markets
short**. Whoever picks up the soft-relative-value ticket must re-derive that
table before leaning on the 295 figure; ticketed.

**Verdict unchanged: do not build the spec as written.** Nothing here
disturbs it — the violations that appeared are long-dated or one-cent-ask,
which is what Result 2 predicts. What changed is that the zero is not a
zero, and one of the two supporting tables is unverified.

---

# Addendum 2026-09-03 — Result 2 re-derived on correct boards: it reproduces exactly

Session `fleet-w3-g4`, study lane. Closes ticket
`2026-09-02-calendar-arb-295-pair-table-unverified`, which flagged that
Result 2 — the horizon x scope table, the finding that actually closes
this theory — had never been re-derived after the exact-stamp board bug
was found, because `probe.py`'s `main()` does not compute it.

**The bar was fixed before any number here existed**, by that ticket on
2026-09-02: *does the near-dated same-event cell still hold ~295 pairs at
min cost 1.000, and is the near-dated cross-event cell still empty?* Both
questions are answered below and neither was reworded afterwards.

## The table reproduces cell for cell

`probe_as_of.py --table` rebuilds the board with `snapshot.board_as_of`
and tabulates every ladder pair. On **2026-08-27T23:18:30Z, the exact
board Result 2 was computed on**:

| later-leg horizon | scope | pairs | min cost | published |
|---|---|---|---|---|
| <= 90d | same-event | **295** | **1.000** | 295 / 1.000 |
| <= 90d | cross-event | **0** | — | 0 / — |
| 90d–1y | same-event | 668 | 1.000 | 668 / 1.000 |
| 90d–1y | cross-event | 39 | 1.050 | 39 / 1.050 |
| 1y–3y | same-event | 593 | 0.990 | 593 / 0.990 |
| 1y–3y | cross-event | 43 | 0.980 | 43 / 0.980 |
| > 3y | same-event | 292 | 0.960 | 292 / 0.960 |
| > 3y | cross-event | 14 | 1.040 | 14 / 1.040 |
| | **TOTAL** | **1,944** | | 1,944 |

**Every cell matches — counts and minima both.** So Result 2 was never
distorted, and the structural argument that closes calendar-arb stands
exactly as recorded.

**Why it was safe when Result 1 was not.** `probe.py` ran on 2026-08-27,
*before* dedup-on-write landed on 2026-08-30, so the exact-stamp query
returned the whole board on the day it was used. The truncation is
retroactive to the stored rows, not to what the probe saw. Today that
same stamp re-reads 87,769 of 110,399 markets, and the table is
**unchanged at 79% of the board** — the missing fifth contains no ladder
pair that moves any cell. Result 1 moved because it counts a handful of
extreme-tail violations, which is exactly the statistic a truncated board
can lose; Result 2 counts population structure, which it cannot.
Generalizable: *a defective instrument does not invalidate every number
it produced — tail counts are fragile to a truncated sample and
population structure is robust to it, and which one you have is knowable
in advance.*

## The claims restated on today's board, and on all 21 captures

On the newest capture (2026-09-03T00:48:42Z, 118,630 markets): **280
near-dated same-event pairs at min cost 1.010, and 0 near-dated
cross-event pairs.** Both claims hold.

Across all 21 stored captures the near-dated same-event cell runs
202–305 pairs with min cost 0.990–1.010, and the near-dated cross-event
cell is **0 on 19 of 21**. The two exceptions are both real and both
explained below; neither is an arbitrage.

## Exception 1 — 23 "cross-event near-dated pairs" that are not a date ladder

Captures `2026-09-01T11:32:57Z` and `11:34:32Z` (one board state, two
minutes apart) show 23 near-dated cross-event pairs, all in
`KXTRUMPSAYCOMPANY` (13) and `KXTRUMPSAYMONTH` (10). They are a
**classifier false positive**, not a violation:

```
KXTRUMPSAYMONTH-26OCT01-ANTI  "Will Trump say 'Antifa' before Oct 1, 2026?"
    open 2026-09-01T04:00Z  close 2026-10-01T14:00Z   yes_ask 0.64
KXTRUMPSAYMONTH-26SEP01-ANTI  "Will Trump say 'Antifa' before Sep 1, 2026?"
    open 2026-08-01T04:00Z  close 2026-09-01T14:00Z   yes_ask 1.00 (resolved YES)
```

The titles read as a nested ladder — anything said before Sep 1 was said
before Oct 1 — but the series is a **monthly reset**: each contract opens
on the first of its own month and only counts statements from its own
open. **The price proves it, and no reading of the rules text is
needed.** The September leg has already resolved YES at ask 1.00; under
genuine nesting the October leg would have to be ~1.00 as well, and it
prices 0.64. Equivalently, the pair "costs" 0.65, so a true nesting would
be a **35-cent riskless arbitrage sitting on a two-sided board** — which
is a classifier error by inspection, not an opportunity.

**Why only two captures.** The two legs are simultaneously listed for
about ten hours a month, at the rollover: the October leg opens
2026-09-01T04:00Z and the September leg closes 2026-09-01T14:00Z. All
four captures on 2026-09-01 agree — 02:06 (before, 0 pairs), 11:32 and
11:34 (inside, 23), 22:00 (after, 0).

**This is the `KXU3MAX` trap arriving through a different door.** The
Method section added `floor_strike`/`cap_strike`/`strike_type` to the key
because two markets can share a subject and differ in threshold. Here the
strikes are identical and the *period* differs, so a strike-aware key
does not help. The general form: **a rolling per-period series whose
title states a cumulative deadline looks nested and is not.** Recorded in
`tickets/new-theory/README.md` as rule 0g, because it is a trap for any
theory pairing markets by parsed dates — `structural_arb` included — and
not only for this one.

The fix is deliberately **not** applied to `probe.py` or to the pair
walk. This study is answered, its verdict does not turn on these 23, and
retrofitting a filter would change the population underneath a published
table for no gain. A future consumer of the dataset excludes rolling
series at the point of use.

## Exception 2 — the one sub-par near-dated pair, and it is not a counter-example

`2026-09-01T22:00:44Z` shows a near-dated same-event minimum of **0.990**:

```
YES KXMLBDEBUT-AMILLER-26NOV01 @0.05  ("...before Nov 1, 2026?")
NO  KXMLBDEBUT-AMILLER-26OCT01 @0.94  ("...before Oct 1, 2026?")
```

Genuinely nested, same event, same subject — this one is real. It is also
**0.990 gross and 0.997 net of both legs' fees: 0.3 cents, held to
2026-11-01.** That is about 1.8%/yr annualized, worse than cash, and it
sits on a market whose payload carries no volume or open interest at all,
so the depth behind the 0.05 ask is unknown. It belongs to the same
category as Result 1's two no-buffer hits and changes nothing.

## What this settles for the open specs

- **`2026-09-01-calendar-arb-soft-relative-value` has its dataset.** The
  295 near-dated same-event pairs at cost 1.000 are verified on a correct
  board. Whoever takes that ticket should exclude rolling per-period
  series (rule 0g) at the point of use.
- **The verdict of this study is unchanged, and was never in question
  here** — `do not build the spec as written`. This addendum re-derives a
  published table; it does not reopen a decision.

Reproduce: `python tickets/study/answer/2026-08-27-calendar-arb-firing-rate/probe_as_of.py --table`

