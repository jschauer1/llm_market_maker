# whale-follow — mirror proven Polymarket wallets into Kalshi

**Priority:** 9 of 12 · **Effort:** L · **LLM in decision path:** match-time
only (via the shared pair store) · **Backtest tier:** A on the Polymarket
signal; Kalshi feasibility measured separately

> Read [README.md](README.md) for the shared repo contracts before
> implementing, and check `python -m tools.cli ideas search "whale-follow"`
> for status changes since this was written. Formalize via the
> `propose-theory` skill before writing procedure code.

## Thesis

Polymarket exposes per-wallet trade history; a small minority of wallets are
persistently profitable. Score wallets on realized, fee-adjusted PnL over a
trailing window; when a top-scored wallet opens or adds meaningfully to a
position, mirror it into the matched Kalshi market.

## Why the edge should exist

Skill persistence is measurable there: only ~13% of Polymarket wallets are
profitable at all, and public backtests of copy-scoring report meaningful
win rates for top-scored wallets' subsequent trades. The whole premise is
testable offline before a dollar moves. Known traps from the copy-trading
ecosystem, to design around: spread-capture bots look profitable but their
edge is *execution* (copying them at market buys what they already skimmed)
— filter by holding time and avoid wallets whose PnL comes from maker-side
scalping; top wallets rotate addresses — scores must decay and re-earn.

## Procedure

- Offline scoring pipeline over `tools/polymarket/trades.py` history:
  per-wallet realized PnL, win rate, n, holding time, category
  concentration. Score = shrunk PnL rate (same n/(n+k) shrinkage philosophy
  as `tools/rank.py`). All code.
- Signal: top-decile wallet takes a new position ≥ its own median size.
- Mirror: `tools/match_market.py` → confirmed Kalshi pair (same pair-store
  discipline as [cross-venue-fair-value](cross-venue-fair-value.md) — reuse
  it) → buy the same side at the Kalshi ask if it is within a tolerance of
  the whale's PM entry. `edge_basis="model"` (the model is the wallet's
  shrunk track record).

## Backtest

Tier A, entirely on the Polymarket side first: score wallets on months 1–6
of trade history, follow their months 7–12 entries on paper, settle. This
tests the *signal*. The Kalshi leg adds match-rate and price-slippage
haircuts, measured separately (how often does a matched Kalshi market exist,
and at what price vs the whale's entry). Keeping the two measurements
separate shows where the edge dies if it dies.

## Kill criteria

Signal test failing (top-decile wallets' subsequent trades don't beat their
entry prices) kills it cleanly. Signal passing but match rate < ~20% doesn't
kill it — it bounds throughput; record and decide.

## Build notes

`theories/whale_follow/{THEORY.md,wallets.py,signal.py}`. Effort L — the
largest data pipeline in this backlog. Build only after
[cross-venue-fair-value](cross-venue-fair-value.md)'s pair store exists; it
shares the matching infrastructure.

## Sources

- [Polycopy trader rankings](https://polycopy.app/best-polymarket-traders) — profitability base rates.
- [Copy-score backtest write-up](https://polyloly.com/blog/polymarket-insider-tail-backtest-46-percent-roi).
- [Finding wallets without getting rekt](https://medium.com/@0xmega/how-to-find-the-best-polymarket-wallets-to-copy-trade-without-getting-rekt-26dd65123324) — the spread-capture-bot and wallet-rotation traps.
