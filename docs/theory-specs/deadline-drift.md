# deadline-drift — "nothing happens by the date"

**Priority:** 2 of 12 · **Effort:** M · **LLM in decision path:** no ·
**Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search "deadline-drift"`
> for status changes since this was written. Formalize via the
> `propose-theory` skill before writing procedure code.

## Thesis

Markets that resolve YES only if a discrete, *unscheduled* affirmative event
occurs by a deadline (bill signed, resignation, deal announced, ceasefire
declared, indictment filed) systematically overprice YES as the deadline
approaches with no event. Buy NO in the late window when the market's
implied hazard exceeds the historical hazard by more than fees.

## Why the edge should exist

Three mechanisms, two documented. (a) Longshot bias: late-window YES on a
quiet market *is* a longshot, and longshots are overpriced (see
[calibration-harvest](calibration-harvest.md)'s evidence). (b) Capital
asymmetry: an Intrade study of 500k+ transactions found high-likelihood
events underpriced and low-likelihood events overpriced specifically at long
horizon, driven by NO requiring more locked capital per unit of profit —
holders of hopeful YES positions are slow to capitulate. (c) Anchoring: the
story that made the market interesting keeps its price sticky even as the
clock runs out. Quantitative support from Le 2026: buying NO here means
buying a favorite, and favorites are measurably underpriced in exactly the
relevant cells — political markets (where most unscheduled
affirmative-event markets live) show calibration slopes of 1.48–1.83 from
12h out to a month, i.e., the market's residual hope in YES is
systematically too expensive.

## Procedure

Fully mechanical, no LLM. Design agreed with the user in the 2026-08-24
session:

- Screen: by-date affirmative-event markets identified from rules-text
  patterns ("occurs by", "before <date>", "on or before") plus a family
  exclusion list, with a per-category report of exclusions (gate.py pattern).
  Two families are explicitly *not* the thesis: **scheduled certainties**
  (games, earnings, launches with fixed dates — no hazard process) and
  **continuous-threshold markets** ("BTC above X by date", weather — those
  are level-crossing processes; see [vol-crossing](vol-crossing.md)).
- Filter: days-to-close ≤ 21, YES ask in ~$0.05–$0.60 (above the band the
  market believes the event happened or is locked in; below it fees eat the
  residual), liquidity floor on the NO ask.
- Edge: empirical bins over settled by-date markets —
  `P(resolves YES | price p, t days remaining)` in (time × price) bins from
  ~12 months of candlestick history (`tools/kalshi/history.py`).
  `edge = (1 − P_hat(YES)) − NO_ask − fees`, `edge_basis="model"`.
  Rejected alternative, for the record: fitting a per-market constant-hazard
  curve from the market's own early price path assumes the early price was
  right, which contaminates the measurement. Parametric hazard by category
  is a v2 once bins have data.

## Backtest

Tier A. Lookahead trap specific to this idea: "the event hasn't happened
yet" must be inferred only from the price path at decision time (price not
yet ≥ ~0.90), never from the settlement we already know. Also split-sample
as in [calibration-harvest](calibration-harvest.md): bin rates from the
first half of history, P&L on the second.

## Kill criteria

If implied and empirical hazard agree within fees across all bins, the
market prices decay correctly — kill it. If the screen's rules-text
classifier shows > ~10% misclassification on a hand-audited sample of 50,
fix the screen before trusting any bin (misclassified threshold markets pool
a different process into the bins and poison the measurement — this is the
design's known weak joint).

## Build notes

`theories/deadline_drift/{THEORY.md,screen.py,hazard_bucket.py}` plus tests.
Effort M — the screen's rules-text classification and its audit are most of
the work; the bucket math is mention_bucket.py again.

## Sources

- [Berg, Nelson, Rietz — Accuracy and Forecast Standard Error of Prediction Markets](https://www.biz.uiowa.edu/faculty/trietz/papers/forecasting.pdf) — Intrade horizon-dependent miscalibration.
- [Can Interest-Bearing Positions Solve the Long-Horizon Problem in Prediction Markets?](https://arxiv.org/pdf/2602.21091) — capital-lockup mechanism.
- [Le 2026 — Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520) (read in full) — political-market compression at the relevant horizons.
