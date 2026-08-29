# Series bias mining — pre-registration, written BEFORE looking

**Date:** 2026-08-29 · **Status:** pre-registered; no result yet ·
**Tier:** A (no model anywhere) · Backlog spec #4, registry slug
`series-bias-mining`

**This file's bar was fixed and committed before any per-series bias
number was computed.** At the time of writing I had looked at exactly two
things: per-series row counts and per-series price ranges. No win rate,
no edge, no split. That is the whole point — with hundreds of series,
deciding what counts as a hit after seeing the hits is how
`mention_family` died, and the peer session's politics read this morning
showed the subtler version (a contrast chosen post-hoc reported as
pre-registered).

## Why this is a study and not a theory

The spec's own §3: *"The miner produces measurements, not bets — no live
screen of its own. Survivors become separate small theories."* CLAUDE.md
is explicit that `Theory` is for things that produce bets and that a
study produces theories. So nothing here registers a theory, records an
opportunity, or touches the ledger. Survivors become **pre-registered
proposals for a follow-on theory**, never bets on this data.

## Population

Settled rows from **`backtest-2026-08-25-insider-fullcov`** and
**`backtest-2026-08-25-mention-fullcov`** pooled.

Chosen because they are the only two populations that share **one
decision rule** — both are replays of `theories/insider_bias/screen.py`
at its pinned defaults (favorites 0.65–0.97, spread ≤ 0.07, volume ≥ 500,
entered at the first screen-qualifying day) — and they are **disjoint**
(insider-fullcov is explicitly the non-mention residue). Pooling runs
with different decision rules would make a mongrel population whose
per-series bias is partly an artifact of which rule sampled which series;
`backtest-2026-08-27-calharvest-weather` is deliberately **excluded** for
exactly that reason and is a separate future pass.

**Scope honesty:** this is therefore not "every recurring series". It is
*favorites in 0.65–0.97 at first qualifying day*, which is the population
`mention_family` was found in. A bias found here generalizes to that
screen, not to the whole board.

## Per-series inclusion floors (fixed now)

A series is **tested** only if all hold. A series failing these is not
read in either direction.

- `n >= 40` settled rows, and `n_days >= 8` distinct settlement days.
- Alive in **both** halves: `n >= 15` and `n_days >= 3` in each half.
  (Spec §10's survivorship risk: a series delisted mid-window truncates
  and can fake or hide bias.)

## The statistic

Per series, the **day-clustered** calibration edge, net of fees:

- one observation per settlement day = `mean(won) − mean(ask)` over that
  day's rows, in points, minus the mean per-contract fee;
- the series' estimate is the **mean over days**, SE the between-day
  standard error, `t = mean / SE`.

Day-clustered, not row-counted, because rows are not independent draws
and this repo has now been bitten by that four separate times in one day
(`buckets.py`, `no_side_premium` cell B, `insider_judgment`'s pooled
scores, `calibration_harvest`'s Wilson bound). A recurring series is the
*worst* case for it: its markets settle in tight clumps by construction.

## The multiple-comparisons guard — the central constraint

Hundreds of series means dozens look biased by chance. **All four are
required to flag a series:**

1. **Split-sample same sign.** Split the series' settlement days
   chronologically at its median day. Both halves must have the same
   sign. (Spec §4's guard.)
2. **Both halves individually non-trivial:** each half's day-clustered
   edge at least 1.0 pt from zero in that shared direction.
3. **Full-series day-clustered `|t| >= 2`.**
4. **Holm–Bonferroni across every series tested**, α = 0.05, family =
   the full set of tested series. Reported alongside the uncorrected
   count, and alongside the **expected number of false positives under
   the null** (`α × n_series`) so a reader can see the multiplicity
   directly.

**One test per series. No price-bin subdivision in v1** — that is what
multiplies the comparison count, and spec §10 says resist it until the
guard is proven. Bins are a follow-on for a series that already survived.

## What counts as what

- **Confirmatory:** at least one series passing all four gates. Its bin
  table becomes a *pre-registered proposal* for a follow-on theory, and
  the follow-on's `edge_basis` may be `measured` **only** after a
  forward or out-of-population test — never on this data, which is the
  data that selected it.
- **Valuable negative (spec §7):** nothing survives → the recurring
  series in this population are calibrated at the family level. Record it
  and say the miner's premise did not generalize beyond
  `mention_family` — which itself later died at full coverage, so this
  outcome is genuinely likely.
- **Uninformative:** fewer than ~10 series clear the inclusion floors.
  Then the population is too thin to test the guard at all, and the
  answer is "not measured", not "nothing there". Recording that
  expectation now so a thin result is not talked up later.

## Known limits, fixed now

- `mention_family`'s series are in the population. They are measured for
  comparison but **never re-promoted** (spec §3), and their known
  full-coverage failure (−1.53 net, n=3,441) means a positive flag on
  them is evidence the guard is *too loose*, not evidence of edge. This
  is the built-in negative control.
- Single decision point (first qualifying day), inherited from the
  screen. The spec's 7d/3d/1d points would triple the comparison count
  and are not used.
- In-sample throughout. The split-sample test is out-of-sample in *time*
  within a series, which is weaker than a fresh population.
