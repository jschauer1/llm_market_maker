# smile-smoothing — soft mispricing across strike ladders

**Priority:** 7 of 12 · **Effort:** M · **LLM in decision path:** no ·
**Backtest tier:** A

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search
> "smile-smoothing"` for status changes since this was written. Formalize via
> the `propose-theory` skill before writing procedure code.

## Thesis

Even when a strike ladder is monotone (no hard
[structural-arb](structural-arb.md) violation), individual strikes get
pushed off the smooth implied distribution by uninformed flow. Fit a
monotone probability curve across the ladder; bet the strike whose price
deviates most from the fit, toward the fit, when the deviation clears fees.

## Why the edge should exist

Same mechanism as structural-arb — retail hits single strikes without
repricing siblings — but the soft version fires far more often than hard
violations. The fitted curve pools information from the whole ladder, which
is more data than any single strike's book. This is standard practice in
options markets (smile smoothing); Kalshi ladders (CPI, temps, crypto
ranges, box office) are the same object with worse participants.

## Procedure

Fully mechanical. Group ladder siblings by event; fit an isotonic
(shape-constrained, assumption-light — preferable to parametric first) curve
to mid prices; compute each strike's deviation; candidate = deviation > fees
+ buffer at the executable quote (ask if buying, bid side via NO if selling
— express everything as buying YES or NO at the ask). `edge_basis="model"`.
Liquidity floor per strike; skip ladders with < 4 liquid strikes — the fit
is meaningless.

## Backtest

Tier A. For settled ladders in history: at decision points, fit on that
day's prices, take the rule's trades, settle them. Trap: fitting on mids but
"trading" at mids overstates the edge badly on thin strikes — the backtest
must charge the historical spread (candlesticks carry bid/ask).

## Kill criteria

If deviations mean-revert to the curve but the *curve* was wrong (deviating
strikes settle in their own favor as often as not), the "noise trader"
premise is wrong — the deviant strike is where the informed flow was. That
result inverts the theory and is worth knowing; test the direction
explicitly before trusting the sign.

## Build notes

`theories/smile_smoothing/{THEORY.md,fit.py}`. Effort M. Depends on the
sibling-grouping helper from [structural-arb](structural-arb.md) — build
that one first, or build the helper here and share later per the repo's
promotion rule.

## Sources

Mechanism-based; no external study needed beyond the structural-arb
evidence. Options-market smile smoothing is the standard-practice analogue.
