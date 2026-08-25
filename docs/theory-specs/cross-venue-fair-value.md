# cross-venue-fair-value — Polymarket as the fair price for Kalshi

**Priority:** 6 of 12 · **Effort:** M · **LLM in decision path:** match-time
only (per-trade decisions mechanical) · **Backtest tier:** A on the
mechanical rule; the pair store is human/LLM-confirmed fact

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search
> "cross-venue-fair-value"` for status changes since this was written.
> Formalize via the `propose-theory` skill before writing procedure code.

## Thesis

On events listed on both venues, Polymarket is usually deeper and sharper
(larger positions, professional flow, per-wallet accountability). Treat the
Polymarket mid as fair value; when the Kalshi ask is cheap against it beyond
fees plus a divergence threshold, buy the Kalshi side that converges. This
is a *one-sided* trade — the user can only bet Kalshi — so it carries event
risk, unlike true two-leg arb, and needs a bigger threshold than an arb bot
would use.

## Why the edge should exist

Persistent 1–5% cross-venue gaps are widely documented, driven by different
user bases, fee structures, and capital frictions. Two-leg arb is competed
(public bots exist), but one-sided convergence-taking is a different,
riskier trade with a wider moat — it requires believing one venue is
*right*, not just that they disagree. The direction of "who is right" is
testable, not assumed (see Backtest).

## Procedure

- Maintain a stable of confirmed matched pairs. Matching is the hard part
  and the only place judgment enters: `tools/match_market.py` produces
  candidates; confirmation compares **resolution criteria, not topic**
  (different resolution sources or deadlines make a "same" market a
  different bet). Confirmation can be an LLM stage (record provenance +
  prompt on disk) or the user by hand for the first N pairs — recommend
  hand-confirming the first stable, because a bad match is this theory's
  worst failure mode and hand-checking doubles as prompt calibration for
  automating later. Match confirmation is *not* in the per-trade decision
  path — a confirmed pair is a static fact — so per-trade decisions stay
  mechanical.
- Per-trade: `edge = |PM_mid − K_ask side-adjusted| − fees − threshold`,
  with a PM liquidity floor (thin PM books are not fair value; require PM
  volume and depth minimums). `edge_basis="model"`.

## Backtest

Tier A on the mechanical rule over historical prices of hand-confirmed
pairs (both venues expose history; Polymarket via
`tools/polymarket/markets.py`). Two things to measure, in order:

1. Does the gap predict *convergence direction* — i.e., when they disagree,
   who moves? If Kalshi converges to Polymarket more often than the reverse,
   the fair-value premise holds; if not, kill the idea before betting
   anything.
2. P&L of the threshold rule net of fees.

## Kill criteria

Premise test (1) failing. Or: gaps exist but only on pairs whose resolution
criteria differ subtly — that's not mispricing, it's two different bets; if
> ~20% of candidate "gaps" turn out to be criteria-mismatch on audit, the
matching bar needs raising before the theory can run.

## Build notes

`theories/cross_venue/{THEORY.md,pairs.py,divergence.py}`. Effort M. Pair
store lives in SQLite with the confirmation evidence (who/what confirmed,
date, criteria notes) — pairs are versioned facts, and a
resolution-criteria change on either venue invalidates a pair. The pair
store is shared infrastructure: [whale-follow](whale-follow.md) reuses it.

## Sources

- [Why the same market prices differently](https://www.predictionhunt.com/blog/why-same-market-different-prices-kalshi-polymarket)
- [How PM/Kalshi arbitrage works](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works)
- [Public arb bot](https://github.com/ImMike/polymarket-arbitrage) — the competed two-leg space this idea deliberately avoids.
