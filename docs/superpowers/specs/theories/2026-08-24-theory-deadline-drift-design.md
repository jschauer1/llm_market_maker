# Deadline Drift — Theory Design Spec

Date: 2026-08-24
Status: backlog — design agreed with the user in the 2026-08-24 session;
ready for `propose-theory`
Registry slug: `deadline-drift` · Priority: 2 of 22 · Effort: M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "deadline-drift"` for status changes.

## Assessment

**Applicability 4/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 10/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* direct NO-side bets with clear entry windows and
  moderate candidate flow; docked one point because NO at $0.40–$0.95
  locks near-full collateral per point of profit.
- *Implementability 3:* the rules-text classifier plus its mandatory
  50-market audit is genuine work with a real misclassification risk —
  the design's own stated weak joint.
- *Likelihood 3:* the mechanism is triangulated from three documented
  effects (longshot bias, capital asymmetry, political horizon
  compression) but this exact expression is unmeasured; the bins may show
  implied and empirical hazard already agree.

## 1. Hypothesis

Markets that resolve YES only if a discrete, *unscheduled* affirmative
event occurs by a deadline (bill signed, resignation, deal announced,
ceasefire declared, indictment filed) systematically overprice YES as the
deadline approaches with no event. Buy NO in the late window when the
market's implied hazard exceeds the historical hazard by more than fees.

## 2. Evidence

Three mechanisms, two documented:

- **Longshot bias:** late-window YES on a quiet market *is* a longshot,
  and longshots are overpriced (see the
  [calibration-harvest spec](2026-08-24-theory-calibration-harvest-design.md)).
- **Capital asymmetry:** Intrade evidence (500k+ transactions; Berg,
  Nelson & Rietz) — high-likelihood events underpriced and low-likelihood
  events overpriced specifically at long horizon, driven by NO locking
  more capital per unit of profit; hopeful YES holders capitulate slowly.
- **Anchoring:** the story that made the market interesting keeps the
  price sticky as the clock runs out.

Quantitative support from Le 2026: buying NO here means buying a
favorite, and favorites are measurably underpriced in exactly the
relevant cells — political markets (where most unscheduled
affirmative-event markets live) show calibration slopes of 1.48–1.83 from
12h out to a month.

## 3. Non-goals and exclusions

Two families are explicitly *not* the thesis, excluded by the gate with a
per-category report:

- **Scheduled certainties** (games, earnings, launches with fixed dates)
  — no hazard process; the event happens on schedule or the market is
  about its outcome, not its occurrence.
- **Continuous-threshold markets** ("BTC above X by date", weather) —
  level-crossing processes with different math; owned by
  [vol-crossing](2026-08-24-theory-vol-crossing-design.md).

One direction only: no symmetric YES-side bet (an undocumented thesis
that would muddy the track record).

## 4. Decision procedure

Fully mechanical, no LLM.

- Screen: by-date affirmative-event markets identified from rules-text
  patterns ("occurs by", "before <date>", "on or before") plus the family
  exclusion list (gate.py pattern with category report).
- Filter: days-to-close ≤ 21; YES ask in ~$0.05–$0.60 (above the band the
  market believes the event happened or is locked; below it fees eat the
  residual); liquidity floor on the NO ask.
- Edge: empirical bins over settled by-date markets —
  `P(resolves YES | price p, t days remaining)` in (time × price) bins
  from ~12 months of candlesticks.
  `edge = (1 − P_hat(YES)) − NO_ask − fees`, `edge_basis="model"`.
- Rejected alternative, recorded deliberately: fitting a per-market
  constant-hazard curve from the market's own early price path assumes
  the early price was right — that contaminates the measurement.
  Parametric hazard by category is a v2 once bins have data.

## 5. Data requirements

In-repo only: board, rules text (`rules_primary` via
`tools/kalshi/markets.py`), candlesticks, fee math.

## 6. Backtest design

Tier A. Bin rates from the first half of history, P&L on the second.
Lookahead trap specific to this idea: "the event hasn't happened yet"
must be inferred only from the price path at decision time (price not yet
≥ ~0.90), never from the settlement we already know.

## 7. Kill criteria

- Implied and empirical hazard agree within fees across all bins → the
  market prices decay correctly; kill.
- Screen misclassification > ~10% on a hand-audited sample of 50 → fix
  the screen before trusting any bin. Misclassified threshold markets
  pool a different stochastic process into the bins and poison the
  measurement — this is the design's known weak joint.

## 8. Implementation plan

`theories/deadline_drift/{THEORY.md,screen.py,hazard_bucket.py}` + tests.
The rules-text classifier and its audit are most of the work; the bucket
math is mention_bucket.py again. Effort M.

## 9. Testing approach

Unit tests: rules-text pattern matching against real rule strings (both
families of exclusions), bin assignment, hazard-edge arithmetic. A
50-market hand-audit fixture for the classifier (section 7's threshold is
tested, not aspirational).

## 10. Open risks

- Rules-text phrasing drifts as Kalshi adds series; the classifier needs
  the audit re-run when its match-rate on the board shifts materially.
- The $0.05–$0.60 band interacts with the calibration-harvest fade band
  in weather-adjacent families — exclusion lists keep the screens
  disjoint, but verify at implementation time.

## 11. Sources

- [Berg, Nelson & Rietz — Accuracy and Forecast Standard Error of Prediction Markets](https://www.biz.uiowa.edu/faculty/trietz/papers/forecasting.pdf)
- [Interest-bearing positions and the long-horizon problem](https://arxiv.org/pdf/2602.21091) — the capital-lockup mechanism.
- [Le 2026](https://arxiv.org/pdf/2602.19520) — political-market compression at the relevant horizons.
