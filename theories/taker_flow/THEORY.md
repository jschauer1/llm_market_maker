# Taker Flow

## Hypothesis

**Sustained, near-total one-sided aggressive order flow marks informed
trading, and the edge is to trade *with* it rather than fade it.**

Kalshi publishes the aggressor side of every executed trade. When almost
all the volume in a market over a week is takers hitting one side, the
makers absorbing it are being adversely selected — and maker losses are
taker gains.

**What mistake is the market making?** Market makers in thin single-market
books cannot tell toxic flow from noise fast enough. They stay anyway
because the toxic tail is cross-subsidised by behavioural flow elsewhere
(the same Stanford study finds traders systematically overbet YES in
markets that predominantly settle NO — an independent 41.6M-trade
confirmation of `no_side_premium`'s thesis, reached from microstructure
rather than behavioural priors).

**Why does it persist?** An equilibrium that is profitable *on average*
for makers can still be systematically unprofitable in the tail, and the
tail is what this trades. Acting on it requires reading a per-trade feed
nobody on the retail side reads.

**The thesis is narrower than the source's.** The Stanford result
localises the effect in single-name markets. That did **not** replicate
here (see Status). What survived is a *tail* phenomenon: moderate
imbalance is worth nothing and near-total imbalance is worth something.

## Data sources

- Kalshi board via `tools.board.get_board` — liquidity screen.
- Kalshi executed trades via `tools/kalshi/trades.py` — the aggressor side.
  Built by this theory's first session; the module docstring carries the
  feed's three measured quirks (retention floor, newest-first ordering,
  no bulk route).
- Outcomes for the replay from the `settlements` table.

No external data, no API keys, no model.

## Status

`testing` — 2026-09-01. The procedure runs end to end, records live rows,
and has a tier A replay behind it.

- 2026-09-01 `proposed` → `testing`: screen runs against the live board and
  records; replay `backtest-2026-09-01-takerflow` completed over 3,585
  settled decisions.

Measured aggregate at v1–v2: `calibration_edge` +0.70 gross, **−0.17 net**
over 813 event clusters, all of it backtested. Flat, as expected — the
population is dominated by the `strong` bucket, which is the control.

**It is not `active` and should not be read as demonstrated.** The
pre-registered rule failed (below). What is positive is a mined subset,
registered as a slice so it has to earn its own out-of-sample evidence.

## Version

**2** (current) — 2026-09-01, `continues`. v1 could emit a position at an
ask of **1.00**, whose maximum profit is zero, and applied the flat
measured gross edge at prices where it implies a probability above 1 (18
of 816 live rows). v2 excludes an unpayable ask in the screen (funnel key
`unpayable_ask`) and caps the claim at `(1 - entry)` headroom in `price`.
Neither alters any decision on a payable candidate at a normal price, so
the tier A replay stays valid evidence — but both change the decision
path, so the version moves.

1 — 2026-09-01, initial. Screen, thresholds and the flow-bucket split as
described.

## Stage 1 — mechanical screen

Fully deterministic. No stage 2.

0. **Payability**: the chosen side's ask must be strictly inside (0, 1).
   An ask of 1.00 costs exactly what it can pay. This is arithmetic, not a
   liquidity judgement — which is why it is not the price cap this theory
   otherwise avoids.
1. **Liquidity floor** on the session board: open, both asks present,
   `spread <= 0.05`, `volume_24h >= 1000`, `open_interest >= 500`,
   `1 <= days_to_close <= 45`. ~1,768 markets on the 2026-09-01 board.
   A *price cap* is deliberately not used — the 0.980–0.995 placeholder-ask
   trap is a liquidity artifact, so spread and open interest exclude it.
2. **Flow window**: trades in the trailing 7 days, `>= 20` of them.
3. **Signal**: volume-weighted taker imbalance in [-1, +1], weighted by
   contract count so one 300-lot does not read like three 1-lots.
4. **Entry**: `|imbalance| > 0.6`, taking the side the flow is taking, at
   that side's ask.
5. **Bucket**, recorded on every row as `extra.flow_bucket`:
   `extreme` at `|imbalance| >= 0.9`, else `strong`.

Pricing is the bucket's measured gross edge from the tier A replay, capped
at the position's headroom `(1 - entry) × 100`, minus fees at the entry
ask. `edge_basis='model'` — a mechanical calculation over measured base
rates.

## Stage 2 — what needs judgment

**None.** The decision path is fully deterministic, which is why this
backtests at tier A. No prompts, no provenance obligations, no model.

## Confidence buckets

Not applicable — nothing judges. `flow_bucket` is a *population* label
derived from a threshold, not a confidence assessment, and its number
comes from that population's realized history rather than from a prior.

## How to backtest

**Tier A** — no model in the decision path, so the replay runs over all
reachable history and re-runs for free. `backtest.py` in this folder.

The reachable window is the intersection of two hard floors, and it is
not a parameter to tune:

- the trade feed retains nothing before **2026-06-26T00:00:00Z**
  (`trades.RETENTION_FLOOR`), so the whole flow window must sit above it;
- outcomes come from `settlements`, and Kalshi archives settled markets
  out of `/markets` at ~60 days, so they cannot be backfilled either.

That intersection is roughly **2026-07-06 onward**.

Three known biases, stated so the number can be caveated:

1. **Entry is the last trade price, not the ask.** Kalshi archives no
   historical order books and candlesticks are empty for archived tickers,
   so no ask is reconstructable. This **flatters** the strategy by roughly
   a half-spread per position. A result that does not clear the typical
   spread of its population is not a result.
2. **Survivorship in the outcome source.** `settlements` holds what past
   sessions captured, not a census.
3. **The decision point is relative to resolution, not close**, because
   `settlements` has no `close_time`. This makes the stated buffer a lower
   bound on how early the decision was taken — the conservative direction.

## Learnings

Distilled; the raw record is in `NOTES.md` (2026-09-01).

- **The three `taker_*` fields are one bit.** Over 93,399 trades they took
  exactly two joint values. `normalize()` raises on anything else rather
  than silently collapsing a side that no longer means what it did.
- **The trade feed does not reach past the archive floor.** It retains
  ~67 days against `/markets`' ~60 — a one-week extension, not a route to
  lost history. The ticket that proposed this theory claimed otherwise; it
  had mistaken a market's oldest *retained* trade for its open.
- **The pre-registered rule failed.** `|imbalance| > 0.6` at a 24h
  decision buffer: +0.70 pts, t=+0.62, CI [−1.51, +2.91]. The single-name
  localisation that the rule was built to test showed **no difference at
  all** (+0.71 single-name vs +0.69 broad-based). That specific claim does
  not replicate on Kalshi at a tradeable horizon.
- **The effect is a tail, not a gradient**, and this is the finding worth
  keeping: `strong` (0.6–0.9) is −0.78 pts over 618 clusters, while
  `extreme` (≥0.9) is +4.29 pts over 280 clusters (t=+2.04). Mined
  post-hoc, so it is registered as the slice `extreme-imbalance` with the
  mining run declared — it starts at n=0 out-of-sample and has to earn its
  record forward.
- **The tail survived every partition check** that could have killed it:
  top series is 3% of the cell, positive in all five price bands, positive
  on both sides, stable across time (+4.46 then +4.21), and
  leave-one-series-out worst case is still +3.50. Consistency across
  partitions is not significance, but it rules out the one-lucky-corner
  explanation.
- **Flow does not predict the next price move.** Lead correlation at a
  25-trade horizon is −0.008. Whatever this is, it is not short-horizon
  price prediction.
- **Liquidity filters do not imply payability.** A one-cent-wide book at an
  ask of 1.00 with 2,000 open interest passes every liquidity test this
  theory has and is still not a position. Caught by looking at the extreme
  values of the first live run rather than by reading the code; any theory
  pricing from a population average should check both.

**What would move it to `active`:** the `extreme-imbalance` slice clearing
its evidence gates (≥10 event clusters, ≥5 settlement days, out of sample)
with positive net edge. **What would send it to `under_review`:** the
slice reaching its gates flat or negative, which would make the mined
+4.29 a multiple-comparison artifact and leave the theory with nothing.
