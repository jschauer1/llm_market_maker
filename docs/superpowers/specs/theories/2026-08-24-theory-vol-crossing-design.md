# Vol Crossing — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `vol-crossing` · Priority: 20 of 22 · Effort: M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "vol-crossing"` for status changes,
then formalize via the `propose-theory` skill.

## Assessment

**Applicability 3/5 · Implementability 3/5 · Likelihood of success 2/5 ·
Composite 8/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* crypto ladders are numerous and recurring, so
  candidate flow is fine when the model disagrees.
- *Implementability 3:* a textbook model plus one external keyless data
  feed; the discipline cost is vol-lookahead hygiene.
- *Likelihood 2:* scored low deliberately. Kalshi crypto is its most
  professionally traded corner (temporal-lag bots operate there), Le 2026
  measures short-dated crypto near-calibrated, and a 5-point model-risk
  buffer may leave few surviving candidates. The plausible residue is
  longer-dated touches only.

## 1. Hypothesis

"X above/below level L by date T" markets on continuously traded
underlyings (BTC, ETH, index levels) are digital barrier options. Price
them with a driftless random walk using realized volatility from the
underlying's recent history; bet when the market's price deviates from
the model by more than fees plus a model-risk buffer.

## 2. Evidence

Retail systematically overprices "touch" events far from the current
level (lottery preference — the longshot bias, in a family where the fair
price is actually computable) and under-adjusts to vol regime changes.
The model side is textbook (reflection principle for barrier-hit
probability); mispricing on crypto weeklies is a known pattern among
options traders who quote Kalshi crypto ladders against Deribit vols.
Le 2026 measures Kalshi crypto near-calibrated short-dated but compressed
at 1mo+ — so the model's largest disagreements should appear in
longer-dated touches.

## 3. Non-goals and exclusions

- v1 restricted to BTC/ETH families — deepest, cleanest underlying data.
  Any expansion requires underlying data of equal quality; this family is
  defined by underlying quality.
- No drift estimation, no vol-surface modeling in v1: driftless EWMA
  realized vol only, with the buffer absorbing model error.
- Unscheduled-event by-date markets belong to
  [deadline-drift](2026-08-24-theory-deadline-drift-design.md), the
  complementary exclusion.

## 4. Decision procedure

Fully mechanical. Underlying history from a keyless public endpoint
(Coinbase/Binance public candles; the exact source is part of the
versioned procedure, documented in THEORY.md). Estimate realized vol
(start: EWMA, 30 days, hourly); compute barrier-hit probability;
candidate when |model − market| > fees + buffer (start: 5 points — vol
estimation error is real). `edge_basis="model"`.

## 5. Data requirements

External: keyless crypto candles (source pinned + snapshotted). In-repo:
board, candlesticks, fee math.

## 6. Backtest design

Tier A over every settled crypto threshold market in history: model price
at fixed decision points using only-then-available underlying data, take
the rule's trades at historical asks, settle. The trap is vol lookahead:
the EWMA window must end strictly before the decision timestamp.

## 7. Kill criteria

If deviations predict *the market being right* (market beats model
out-of-sample), Kalshi crypto is sharper than assumed — kill, record the
direction; an inverse "trust the market against the model" theory would
need its own justification, not a sign flip.

## 8. Implementation plan

`theories/vol_crossing/{THEORY.md,model.py,underlying.py}` + tests.
Effort M. Note: daily-recurring crypto range markets also feed
[series-bias-mining](2026-08-24-theory-series-bias-mining-design.md); if
the miner flags them first with a pure base-rate edge, that is the
cheaper capture and this model becomes its v2.

## 9. Testing approach

Unit tests: barrier-hit probability against closed-form cases, EWMA
window boundaries (the lookahead guard as a test, not a convention),
buffer/fee arithmetic. Fixture backtest on constructed price paths with
known hit outcomes.

## 10. Open risks

- Crypto vol is regime-heavy; a 30-day EWMA lags regime breaks exactly
  when mispricing is largest — the buffer is doing a lot of work, and the
  backtest should report sensitivity to it.
- Kalshi crypto is among its most professionally traded segments
  (sub-100ms temporal-lag bots operate there); the *short-dated* end is
  likely efficient, which section 2's horizon evidence already suggests —
  expect the surviving cells to be longer-dated.

## 11. Sources

- Longshot/touch overpricing: see
  [calibration-harvest](2026-08-24-theory-calibration-harvest-design.md)
  sources; [Le 2026](https://arxiv.org/pdf/2602.19520) crypto horizon
  slopes.
