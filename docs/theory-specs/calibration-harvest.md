# calibration-harvest — board-wide favorite-longshot harvesting

**Priority:** 1 of 12 · **Effort:** S · **LLM in decision path:** no ·
**Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search
> "calibration-harvest"` for status changes since this was written.
> Formalize via the `propose-theory` skill before writing procedure code.

## Thesis

Kalshi prices are systematically miscalibrated as a function of price,
horizon, and category — and the *direction* of the miscalibration depends on
the (domain × horizon) cell. Bet the side each cell's measured realized rate
says is cheap, when the gap exceeds the ask plus fees.

## Why the edge should exist

This is the favorite-longshot bias, the oldest documented anomaly in betting
markets (Griffith 1949), and it has been measured *on Kalshi specifically*,
twice, at scale, with signed magnitudes:

- Whelan ("Makers and Takers", 300,000+ contracts): low-price contracts win
  far less often than break-even requires after fees; high-price contracts
  win more often and yield small positive returns.
- Le 2026 (353M trades, 429k contracts across Kalshi + Polymarket; read in
  full for this backlog; replication repo public): calibration slopes by
  domain × horizon, Table 4. **Politics is compressed toward 50% at nearly
  all horizons** (slopes 1.32–1.83 beyond 3h; a 70¢ political contract one
  week out maps to ≈83%; at a raw price of 0.75 the isotonic estimate is
  0.886 — a ~13-point gross gap on the favorite side). **Weather is the
  opposite at short horizons** (slopes 0.69–0.87 within 12h; a 75¢ weather
  contract is really 69.1% — the *favorite* is rich and the fade side is
  cheap). Sports and crypto are near-calibrated short-dated but compressed
  long-dated (slopes 1.74 and 1.36 beyond one month). The universal horizon
  component rises from 0.99 (0–1h) to 1.32 (1mo+): everything compresses
  toward 50% as horizon grows.

The repo's own `mention_family` work independently rediscovered the same
shape in one family: win rate rises from 0.73 below $0.75 to 1.00 at $0.85+.
The mechanism is structural (lottery-ticket preference on the cheap side,
capital lockup aversion on the expensive side), so it should decay slowly if
at all.

## Procedure

Fully mechanical, no stage 2.

- Cells are **signed**: a cell's trade can be "buy the favorite" (politics,
  most horizons; anything long-dated) or "fade the favorite" (short-horizon
  weather). Never encode a universal buy-favorites rule — Le's Table 4 shows
  the sign flips by domain, and this repo must re-measure the signs on its
  own settled history rather than importing the paper's numbers as the edge
  (`edge_basis="measured"` means *our* measurement; the paper is the prior
  that says where to look, and two pre-registered cells to check first:
  political favorites at 2d–1mo horizons, and short-dated weather extremes).
- Screen: every market on the board with YES ask in a configurable band
  (start: $0.65–$0.97 on the favorite side, plus the mirrored fade band where
  a cell's sign says so), and a liquidity floor. Do not hard-cap
  days-to-close at 14 — the documented compression *grows* with horizon, so
  bin horizon (≤2d / 2d–1w / 1w–1mo / 1mo+) instead of truncating it, and
  let capital lockup enter through sizing (`tools/sizing.py`), not through
  the screen. Exclude families already claimed by a running theory
  (`mention_family`'s MENTION/SAY/ACT tickers) so two theories never book the
  same trade — do the exclusion by series-ticker pattern and report what was
  excluded, gate.py-style.
- Edge: `edge = realized_rate(cell) − ask − fees`, where `realized_rate` comes
  from tier-A measurement over settled history, binned by
  (price bin × horizon bin × coarse category). `edge_basis="measured"` for
  cells with n ≥ 30, `"model"` for thinner cells if reported at all. Use
  Wilson lower bounds, not point rates, for thin cells — the mention_family
  log already flagged that an unshrunk 1.000 win rate (n=41) is a defect.
- Rank across candidates by net edge; size via `tools/sizing.py`.

## Backtest

Tier A. Split settled history in half by time; measure cell rates on the
first half, evaluate P&L of the rule on the second half. This guards against
the main statistical trap: with many cells, some look golden by chance. A
cell only counts if it survives out-of-sample.

## Kill criteria

If no cell clears fees out-of-sample at n ≥ 30, the bias exists but is
priced in — record that in the registry and stop. Partial survival (e.g.,
only $0.90+ within 7 days) is a success, not a failure; narrow the screen to
the surviving cells.

## Build notes

`theories/calibration_harvest/{THEORY.md,screen.py,cells.py}` plus tests.
Reuse `mention_bucket.py`'s structure for `cells.py`. Effort S — this is
mention_family's math with a wider screen. The overlap-exclusion list is
part of the versioned procedure.

## Sources

- [Whelan — Makers and Takers](https://www.karlwhelan.com/Papers/Kalshi.pdf)
  ([CEPR summary](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market))
- [Le 2026 — Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520)
  (read in full; [replication repo](https://github.com/namanhzz/prediction-market-calibration))
- [Kalshi macro-market calibration](https://www.researchgate.net/publication/409472804_Information_Efficiency_Across_Macroeconomic_Prediction_Markets_Evidence_from_Kalshi)
  and [unemployment-market favorite-longshot bias](https://www.researchgate.net/publication/409238145_Market_Efficiency_and_the_Favorite-Longshot_Bias_in_Unemployment_Prediction_Markets)
