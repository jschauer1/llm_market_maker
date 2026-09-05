---
title: Does resting a limit order beat crossing the spread, once you pay for the fills you do not get?
lane: study
created: 2026-09-03
created_by: fleet-w3-g5
author_lane: study
author_context: Deciding experiment for the open new-theory spec maker-mode-execution, twice named in RESEARCH_LOG as the recommendation; spec section 6 is the measurement design and section 7 says it must run before any live recommendation carries a limit-price line.
---

# Maker mode — pre-registration, written BEFORE looking

<!-- research-memory-route -->
> [Find related lessons and their applicability](../../../../knowledge/README.md). This document is
> source evidence: read its verdict and limits first, then the relevant method
> or result section. A useful short answer needs no duplicate summary.
<!-- /research-memory-route -->


**Date:** 2026-09-03 ·
**Tier:** A (no model anywhere in the path) ·
**Verdict:** PENDING — this file is the bar, committed before any contrast was computed

Deciding experiment for `tickets/new-theory/open/2026-08-24-maker-mode-execution.md`
(idea 17). That spec's §6 is a measurement design and its §7 says the test
"should run before any live recommendation carries a limit-price line."
This study is that test. It **never bets**: no ledger row, no ticker, no
score.

## The question, in one sentence

For a candidate this repo would enter by crossing the spread, does
**resting a limit order one cent inside the bid, and crossing later if it
does not fill**, beat **crossing immediately** — measured at executable
prices, net of fees?

## Why this is worth a session

Rule 0f in `tickets/new-theory/README.md` has killed or gutted eight
ideas, all the same way: the effect is at the mid and dies at the ask.
Maker mode is the only spec in the backlog that attacks that mechanism
head-on rather than paying it. If resting captures 1-3 points, it moves
every theory here at once; `no_side_premium` runs at +2.14 net and
`taker_flow`'s tail at +4.29 gross against a ~1.7pt fee, so a 1-point
execution improvement is not a rounding error against either. If resting
loses, rule 0f is confirmed as absolute and the recommendation format
stays taker-only forever, which is also worth knowing once rather than
re-litigating.

## The instrument, and why it is better than the spec assumed

The spec (§6, §10) assumed fills would have to be **inferred from a
candle bid path**, and flagged two problems it could not solve: a candle
hides intra-period touches, and queue position is invisible.

`theories/taker_flow/backtests/settled_trades.jsonl` (305 MB, already on
disk, collected 2026-09-01) makes both cheaper, because it is **per-trade
prints, not candles**. Each line is one settled market —
`{ticker, resolved_at, result, trades:[{t, s, c, p, b}]}` — where `s` is
the **aggressor** side, `p` is the yes-price and `b` is the block flag.

Kalshi's aggressor bit pins which side of the book each print consumed
(`tools/domain.Trade`: the three taker fields are perfectly collinear
over 93,399 measured trades):

- a print with `s='yes'` consumed a resting **YES ask** -> `ask ~= p`
- a print with `s='no'` consumed a resting **YES bid** -> `bid ~= p`

So the two aggressor sides **straddle the spread**, and an executable
bid/ask can be reconstructed for archived markets whose candlesticks are
empty. That is worth stating on its own: `taker_flow`'s own RESULTS.md
lists "entry is the last trade price, not the ask" as bias #1 and says
"no historical order book exists". One does, at print resolution.

This also gives a **real** fill test rather than an inferred one. A fill
is an observed print that a resting order would have had price priority
over — not a candle that might have touched.

## Population — the inclusion rules, stated concretely

Every market in `settled_trades.jsonl` satisfying **all** of:

1. `result` is `yes` or `no` (a settled binary outcome exists).
2. **Both sides of the book are observable and fresh at the decision
   point:** at least one non-block `s='yes'` print and at least one
   non-block `s='no'` print in the 72 hours ending at T.
3. **The reconstructed book is coherent:** `bid_hat(T) < ask_hat(T)`.
   A crossed reconstruction means the two sides were observed at
   different times across a move; it is excluded, not repaired.
4. **There is something to capture:** `ask_hat(T) - bid_hat(T) >= 0.02`.
   At a 1-cent spread, "bid + 1c" *is* the ask, so resting is crossing
   and the contrast is undefined. This rule is load-bearing and is
   declared here because it decides who is in the sample.
5. `0.02 <= ask_hat(T) <= 0.98`.
6. Block trades (`b=true`) are excluded from **both** the book
   reconstruction and the fill rule — they are negotiated off-book and
   never consume a resting order.

**Decision point `T` = 48h before `resolved_at`. Horizon `H` = 24h.**
One primary horizon, chosen for a stated reason and not swept: this repo
runs a session once a day, so an order rests exactly until the next
session, and the fallback cross at `T+24h` lands on the same 24h-before
decision point `taker_flow` already uses.

## The two arms

Both arms buy **YES** — one observation per market, no double counting.

- **CROSS (control):** buy at `ask_hat(T)`.
  Cost = `ask_hat(T) + fee(ask_hat(T))`.
- **REST:** post a bid at `L = bid_hat(T) + 0.01`.
  - **Filled** if any non-block `s='no'` print occurs in `(T, T+H]` at
    `p <= bid_hat(T)` — i.e. selling pressure traded **through** my
    level. Since `L` is strictly better than every historical resting
    bid at `bid_hat(T)`, any aggressor who transacted there would have
    taken me first, and I am alone at `L` rather than queued behind it.
    This is the spec's own §10 conservative rule ("fill only if the bid
    trades through the limit, not merely touches"), and it is the
    strictest of the three available fill rules.
    Cost = `L + fee(L)`.
  - **Unfilled:** cross at `T+H` at `ask_hat(T+H)`.
    Cost = `ask_hat(T+H) + fee(ask_hat(T+H))`. Unfilled orders do not
    disappear — they get a later price, which is the whole point of the
    paired design (spec §6).

## The contrast, and its predicted direction

**Primary statistic: `D = cost(CROSS) - cost(REST)`, in percentage
points, per market.** Positive means resting was cheaper.

**Predicted: POSITIVE, +1 to +3 points** (spec §1: "adds 1-3 points to
every filled trade"). The competing prediction is the spec's own
Likelihood-3 caveat, from Palumbo: fills are adversely selected badly
enough that the drift paid on non-fills exceeds the spread captured on
fills, making `D` zero or negative.

**Note the outcome cancels, and that is a design property, not an
oversight.** Both arms end holding the same contract in the same market,
so `won` appears identically in both and drops out of `D`. Adverse
selection is therefore *not* a cost on fills here — filling in a market
that later falls still leaves you better off than crossing in that same
market did. Adverse selection enters exactly one way: **the markets you
fail to fill are the ones that ran away from you, and you cross them
later at a worse price.** `D` prices that in full. The consequence is
that the dominant variance term (settlement) is gone, so this design is
far better powered than a P&L comparison, and it is a **pure execution**
measurement rather than a forecasting one.

**Reported gross and net.** `D` is stated with fees in (it is a cost
comparison, so fees are part of the quantity under test) and the
fee-free version is reported beside it, per rule 0d's lesson that a
near-constant fee offset can manufacture a sign.

## Power floor — stated before running

Clustered by **settlement day** (`resolved_at` date); `n_days` and event
clusters both reported. Settlement-day clustering is a first-order
confound in this repo (`2026-08-27-settlement-day-clustering`).

**MDE ceiling: 1.0 point.** The claimed effect is 1-3 points, so a design
that cannot resolve 1.0 point cannot inform the question. If the
day-clustered MDE at 80% power exceeds 1.0 pt, the run is reported as
**not measured** — not as a null — and resized rather than reinterpreted.
This is `series-bias-mining`'s pass-3 lesson applied in advance.

## What kills the idea

Taken verbatim from the spec's §7 kill criterion, made numeric:

- **KILL** if `D <= 0` and the upper bound of its 95% clustered CI is
  below **+1.0 pt** — the low end of the claimed effect. Then maker mode
  is dropped, the recommendation format stays taker-only, and the spec
  closes `disproven`.
- **BUILD** if `D > 0` with a clustered `t >= 2` and a lower CI bound
  above 0. Then the spec goes to `build/` with these magnitudes.
- **NOT MEASURED** if the MDE ceiling above is breached, or if fewer
  than 10 settlement days survive the inclusion rules.

A result between those — positive but not significant — is reported as
what it is and carried as unconfirmed, never rounded up to a build order.

## Pre-declared secondary splits (Holm-corrected, reported as secondary)

Fixed now, so that none of them can be chosen after seeing the primary:

1. **Price band** of `ask_hat(T)`: `[0.02,0.20)`, `[0.20,0.50)`,
   `[0.50,0.80)`, `[0.80,0.98]`.
2. **Spread width** at T: 2-3c, 4-6c, >=7c.
3. **Mirror check — buy NO instead of YES.** Not an independent
   confirmation (it is the same spread, reflected) but it does test
   whether any result is an artifact of *directional drift* on the
   non-filled arm rather than of spread capture.
4. **Fill rate** and the composition of filled vs unfilled markets.

## Negative controls

Rule 0c asks for a slice whose answer is already known. This study runs
one contrast rather than a mining family, so the multiple-comparisons
half of 0c does not bite; what it needs is proof the *instrument* is
not manufacturing the effect. Two controls, both built into the run:

1. **Zero-improvement arm.** Re-run the identical accounting with
   `L = ask_hat(T)` — posting at the crossing price. Its `D` must be
   **exactly 0.00** for every market. Any drift from zero is an
   accounting bug, and the run is void.
2. **Planted-path fixtures** (rule 0d — build the fixtures before
   touching real data). A constructed market whose print sequence has a
   known answer, covering: fills through the level, touches at exactly
   the level (must NOT fill), block trades at the level (must NOT
   fill), no prints in the window, and a book that crosses. Written and
   passing before the corpus is read.

## Known limits, stated in advance

- **My own order is not in the historical book.** Posting a better bid
  could attract sellers who would otherwise not have traded, or scare
  them off. Unmodellable from prints; it biases the fill rate in an
  unknown direction and is stated rather than corrected.
- **`bid_hat`/`ask_hat` are last-touch, not live.** They are real
  executed prices, which is stronger than a mid, but they lag the book
  by however long since the last print on that side. Rule 2 caps that
  lag at 72h and the realized lag distribution is reported.
- **Corpus scope.** `settled_trades.jsonl` is `taker_flow`'s collection
  (resolutions 2026-07-06 -> 2026-09-01, 5,184 markets collected), and
  its own RESULTS.md flags survivorship in the outcome source: it is
  what past sessions captured, not a census. A result here generalizes
  to that window and that collection, and the trade feed's retention
  floor (2026-06-26) is why it cannot reach further back.
- **This is an execution layer, not a theory.** Nothing here proposes a
  bet, and a positive result is a change to `tools/sizing.py`,
  `find-edge`'s report format and `ledger.mark-taken` (spec §8), not a
  new theory.

## What was looked at before this file was committed

Population counts and the reconstructed spread distribution only —
written by `counts.py` beside this file, which is deliberately incapable
of reading `result`. No fill rate, no `D`, no split, no outcome of any
kind.

## investigation — 2026-09-03

User ruling 2026-09-03: a study in question/ holds nothing but the statement of what should be investigated -- the design, the code and the data are the investigation. This study already carried its pre-registration, its simulator (sim.py, run.py), its planted-path fixtures and a collected data/markets.jsonl, so it moves to the state its work is actually in. Nothing about the measurement changed.
