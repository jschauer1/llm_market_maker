# vol-crossing — pricing threshold markets as barrier options

**Priority:** 10 of 12 · **Effort:** M · **LLM in decision path:** no ·
**Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search "vol-crossing"`
> for status changes since this was written. Formalize via the
> `propose-theory` skill before writing procedure code.

## Thesis

"X above/below level L by date T" markets on continuously traded underlyings
(BTC, ETH, index levels) are digital barrier options. Price them with a
driftless random walk using realized volatility from the underlying's recent
history; bet when the market's price deviates from the model by more than
fees plus a model-risk buffer.

## Why the edge should exist

Retail systematically overprices "touch" events far from the current level
(lottery preference — the same longshot bias, in a family where the fair
price is actually computable) and under-adjusts vol regime changes. The
model side is textbook (reflection principle for barrier-hit probability);
mispricing on crypto weeklies is a known pattern among options traders who
quote Kalshi crypto ladders against Deribit vols.

## Procedure

Fully mechanical. Underlying price history from a keyless public endpoint
(Coinbase/Binance public candles for crypto; document the exact source in
THEORY.md — it is part of the procedure). Estimate realized vol (start:
EWMA over 30 days, hourly); compute hit probability; candidate when
|model − market| > fees + buffer (start: 5 points, because vol estimation
error is real). `edge_basis="model"`. Restrict v1 to BTC/ETH families —
deepest, cleanest underlying data.

## Backtest

Tier A over every settled crypto threshold market in history: compute the
model price at fixed decision points with only-then-available underlying
data, take the rule's trades, settle. Vol lookahead is the trap: the EWMA
window must end strictly before the decision timestamp.

## Kill criteria

If deviations predict *the market being right* (market beats model
out-of-sample), Kalshi crypto is sharper than assumed — kill, and record the
direction; the inverse signal ("trust the deviation") would be a different
theory needing its own justification, not a sign flip. Also kill any
expansion beyond crypto unless the underlying's data is as good — this
family is defined by underlying quality.

## Build notes

`theories/vol_crossing/{THEORY.md,model.py,underlying.py}`. Effort M. Note
the daily-recurring crypto range markets also feed
[series-bias-mining](series-bias-mining.md)'s miner; if the miner flags them
first with a pure base-rate edge, that is the cheaper capture and this model
becomes its v2.

## Sources

- Longshot-bias evidence in [calibration-harvest](calibration-harvest.md)'s
  sources (the "touch" overpricing is its expression in this family; Le 2026
  measures crypto near-calibrated short-dated, compressed at 1mo+).
