---
title: Signed price x horizon x domain calibration cells: bet the side each cell's own measured rate says is cheap
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-09-01
resolution: BUILT then RETIRED. Theory `calibration_harvest` ran v1-v4 and was retired 2026-09-01 on its own pre-registered kill criterion. Across three complete populations -- weather, politics, and econfin (1,181/1,181 series, 2,666 observations) -- 47 cells cleared both floors and ZERO cleared fees. The horizon axis reversed sign out of sample (1mo+ +9.38 -> -5.09), 0 of 27 econfin cells survived Holm, and 87% of the forward corpus turned out to be sports reading -6.69 gross. This was the highest-scoring spec in the backlog (composite 14/15). Full record in theories/calibration_harvest/.
---
Effort: S · LLM in decision path: no · Backtest tier: A

**This spec was acted on; the `resolution` field above says what
came of it.** Kept rather than deleted, because a completed ticket
is the record of what was asked for and why — which is what a
future session re-deriving the same idea needs.

## Assessment

**Applicability 5/5 · Implementability 5/5 · Likelihood of success 4/5 ·
Composite 14/15** (rubric in the
[index](../README.md); ordinal priors for
prioritization, not calibrated probabilities)

- *Applicability 5:* scans the whole board every session; output is
  directly bettable Kalshi contracts with frequent candidates across all
  horizons and categories.
- *Implementability 5:* every input is already in-repo, and the math is
  mention_family's, already validated end-to-end on 116 settled markets.
- *Likelihood 4:* the bias is measured on Kalshi twice with magnitudes
  above fees in named cells (politics ≈13pts gross at $0.75). Residual
  risks — multiple comparisons and thin-cell overfitting — are addressed
  by split-sample and Wilson bounds. Not 5 because our 12-month window is
  shorter than the papers' and the after-fee residue may concentrate in
  few cells.

## 1. Hypothesis

Kalshi prices are systematically miscalibrated as a function of price,
horizon, and category — and the *direction* of the miscalibration depends
on the (domain × horizon) cell. Bet the side each cell's measured realized
rate says is cheap, when the gap exceeds the ask plus fees.

## 2. Evidence

This is the favorite-longshot bias, the oldest documented anomaly in
betting markets (Griffith 1949), measured *on Kalshi specifically*, twice,
at scale, with signed magnitudes:

- Whelan ("Makers and Takers", 300,000+ contracts): low-price contracts
  win far less often than break-even requires after fees; high-price
  contracts win more often and yield small positive returns.
- Le 2026 (353M trades, 429k contracts, Kalshi + Polymarket; read in full
  for this backlog; replication repo public): calibration slopes by
  domain × horizon (Table 4). **Politics is compressed toward 50% at
  nearly all horizons** (slopes 1.32–1.83 beyond 3h; a 70¢ political
  contract one week out maps to ≈83%; at a raw price of 0.75 the isotonic
  estimate is 0.886 — a ~13-point gross gap on the favorite side).
  **Weather is the opposite at short horizons** (slopes 0.69–0.87 within
  12h; a 75¢ weather contract is really 69.1% — the *favorite* is rich).
  Sports and crypto are near-calibrated short-dated but compressed
  long-dated (slopes 1.74 and 1.36 beyond one month). The universal
  horizon component rises 0.99 (0–1h) → 1.32 (1mo+).

The repo's own `mention_family` work independently rediscovered the same
shape in one family: win rate rises from 0.73 below $0.75 to 1.00 at
$0.85+. The mechanism is structural (lottery-ticket preference on the
cheap side, capital-lockup aversion on the expensive side), so it should
decay slowly if at all.

## 3. Non-goals and exclusions

- **Never a universal buy-favorites rule** — the sign flips by domain
  (weather vs politics), so every cell carries its own sign from our own
  measurement. The paper is the prior that says where to look, never the
  edge itself.
- Families claimed by running theories (`mention_family`'s
  MENTION/SAY/ACT tickers) are excluded by series-ticker pattern, with a
  gate-report of what was removed, so two theories never book the same
  trade.
- The side-conditional (YES vs NO at equal price) effect is a different
  measurement owned by
  [no-side-premium](2026-08-24-no-side-premium.md); the two
  screens stay disjoint by construction (favorite-side band here,
  YES-longshot band there).

## 4. Decision procedure

Fully mechanical, no stage 2.

- Cells: (price bin × horizon bin × coarse category), **signed** — "buy
  the favorite" (politics most horizons, anything long-dated) or "fade the
  favorite" (short-horizon weather). Two pre-registered cells to check
  first: political favorites at 2d–1mo horizons; short-dated weather
  extremes.
- Screen: board markets with YES ask in a configurable band (start:
  $0.65–$0.97 favorite-side, plus the mirrored fade band where a cell's
  sign says so), liquidity floor. Do not hard-cap days-to-close — the
  documented compression *grows* with horizon; bin horizon
  (≤2d / 2d–1w / 1w–1mo / 1mo+) and let capital lockup enter through
  sizing, not the screen.
- Edge: `edge = realized_rate(cell) − ask − fees`, rates from tier-A
  measurement over settled history. `edge_basis="measured"` for cells with
  n ≥ 30 (Wilson lower bounds for thin cells — the mention_family log
  already flagged an unshrunk 1.000 (n=41) as a defect); `"model"` for
  thinner cells if reported at all.
- Rank by net edge; size via `tools/sizing.py`.

## 5. Data requirements

All in-repo: session board, settled markets + candlesticks
(`tools/kalshi/history.py`, ~12 months), ticker-hierarchy categories, fee
math. No external data, no LLM.

## 6. Backtest design

Tier A. Split settled history in half by time: measure cell rates on the
first half, evaluate rule P&L on the second. This guards the main
statistical trap — with many cells, some look golden by chance; a cell
only counts if it survives out-of-sample.

## 7. Kill criteria

If no cell clears fees out-of-sample at n ≥ 30, the bias exists but is
priced in — record and stop. Partial survival (e.g., only $0.90+ within
7 days) is success, not failure; narrow the screen to surviving cells.

## 8. Implementation plan

`theories/calibration_harvest/{THEORY.md,screen.py,cells.py}` + tests.
Reuse `mention_bucket.py`'s structure (`PRICE_BINS`, `bucket_for_price`)
for `cells.py`. The overlap-exclusion list is part of the versioned
procedure. Effort S — mention_family's math with a wider screen.

## 9. Testing approach

Unit tests: cell assignment (price/horizon/category), signed-cell edge
arithmetic, exclusion gate + its category report, Wilson-bound fallback
for thin cells. Backtest harness against constructed settled fixtures
where the planted bias is/isn't present.

## 10. Open risks

- Multiple-comparisons residue even with split-sample: many cells ×
  two signs. Keep the cell grid coarse (the pre-registered cells first).
- Long-dated cells lock capital for months per settled data point —
  evidence accrues slowly exactly where the measured edge is largest.
- Category mapping from tickers is coarse; version it in the theory
  folder.

## 11. Sources

- [Whelan — Makers and Takers](https://www.karlwhelan.com/Papers/Kalshi.pdf) ([CEPR summary](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market))
- [Le 2026 — Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520) (read in full; [replication repo](https://github.com/namanhzz/prediction-market-calibration))
- [Kalshi macro-market calibration](https://www.researchgate.net/publication/409472804_Information_Efficiency_Across_Macroeconomic_Prediction_Markets_Evidence_from_Kalshi) and [unemployment-market favorite-longshot bias](https://www.researchgate.net/publication/409238145_Market_Efficiency_and_the_Favorite-Longshot_Bias_in_Unemployment_Prediction_Markets)
