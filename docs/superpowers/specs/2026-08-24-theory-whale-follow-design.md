# Whale Follow — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `whale-follow` · Priority: 19 of 22 · Effort: L ·
LLM in decision path: match-time only (via the shared pair store) ·
Backtest tier: A on the Polymarket signal; Kalshi leg measured separately

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "whale-follow"` for status changes,
then formalize via the `propose-theory` skill.

## Assessment

**Applicability 3/5 · Implementability 2/5 · Likelihood of success 3/5 ·
Composite 8/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* bounded by the Kalshi match rate (unknown, possibly
  under 20% of whale entries); matched alerts are directly actionable.
- *Implementability 2:* the largest pipeline in the backlog — wallet
  scoring at scale, wash filtering, incremental updates, plus the
  pair-store dependency.
- *Likelihood 3:* ecosystem copy-score backtests are encouraging but not
  peer-reviewed; copy latency and wallet rotation erode the signal; wash
  contamination inflates apparent skill. The PM-side 1–6/7–12 split test
  is decisive, tier-A, and runs before any money is at risk.

## 1. Hypothesis

Polymarket exposes per-wallet trade history; a small minority of wallets
are persistently profitable. Score wallets on realized, fee-adjusted PnL
over a trailing window; when a top-scored wallet opens or adds
meaningfully to a position, mirror it into the matched Kalshi market.

## 2. Evidence

Skill persistence is measurable there: only ~13% of Polymarket wallets
are profitable at all, and public backtests of copy-scoring report
meaningful win rates for top-scored wallets' subsequent trades. The
premise is testable offline before a dollar moves. Known traps from the
copy-trading ecosystem, designed around in section 3: spread-capture bots
look profitable but their edge is *execution* (copying them at market
buys what they already skimmed); top wallets rotate addresses.

## 3. Non-goals and exclusions

- No copying of maker-side/scalping wallets: filter by holding time and
  PnL decomposition, or the score selects execution bots whose edge
  cannot be copied.
- Scores decay and re-earn (wallet rotation); no permanent whitelist.
- No mirror without a confirmed pair (resolution criteria, not topic) —
  the pair-store discipline from
  [cross-venue-fair-value](2026-08-24-theory-cross-venue-fair-value-design.md),
  reused.
- Sports-heavy wallets discounted: wash trading is worst there (see
  section 10) and contaminates their apparent PnL.

## 4. Decision procedure

- Offline scoring over `tools/polymarket/trades.py` history: per-wallet
  realized PnL, win rate, n, holding time, category concentration. Score
  = shrunk PnL rate (the n/(n+k) shrinkage philosophy of `tools/rank.py`).
  All code.
- Signal: top-decile wallet takes a new position ≥ its own median size.
- Mirror: match via the pair store → buy the same side at the Kalshi ask
  if within a tolerance of the whale's PM entry. `edge_basis="model"`
  (the model is the wallet's shrunk track record).

## 5. Data requirements

Polymarket trade history at scale (in-repo tools; Becker's public
dataset can bootstrap the historical window), the pair store, Kalshi
quotes.

## 6. Backtest design

Tier A, entirely on the Polymarket side first: score wallets on months
1–6 of trade history, paper-follow their months 7–12 entries, settle.
That tests the *signal*. The Kalshi leg adds match-rate and
price-slippage haircuts, measured separately — keeping the two apart
shows where the edge dies if it dies.

## 7. Kill criteria

- Signal test failing (top-decile wallets' subsequent trades don't beat
  their entry prices) kills it cleanly.
- Signal passing but match rate < ~20% doesn't kill — it bounds
  throughput; record and decide.

## 8. Implementation plan

`theories/whale_follow/{THEORY.md,wallets.py,signal.py}` + tests. Build
after cross-venue-fair-value's pair store exists. The wash filter (shared
with
[insider-flow-radar](2026-08-24-theory-insider-flow-radar-design.md)) is
a `tools/` promotion candidate. Effort L — the largest data pipeline in
this backlog.

## 9. Testing approach

Unit tests: PnL reconstruction from trade fixtures, shrinkage scoring,
holding-time filter, signal thresholds. The 1–6/7–12 split harness as a
reusable script with fixed seeds/windows.

## 10. Open risks

- **Wash trading**: ~25% of all-time PM volume estimated fake (45% in
  sports; worse in high-attention periods). Wallet PnL and market volume
  screens must be wash-filtered or scores select for manipulators.
- Copy latency: by the time a whale's fill is visible and matched, the PM
  price has moved; the entry-tolerance rule bounds but does not eliminate
  the decay. Measure realized copy-lag slippage in the backtest.
- Polymarket data volume is large; the scoring pipeline needs incremental
  updates, not full recomputes per session.

## 11. Sources

- [Polycopy trader rankings](https://polycopy.app/best-polymarket-traders) — profitability base rates.
- [Copy-score backtest](https://polyloly.com/blog/polymarket-insider-tail-backtest-46-percent-roi) · [wallet-selection traps](https://medium.com/@0xmega/how-to-find-the-best-polymarket-wallets-to-copy-trade-without-getting-rekt-26dd65123324)
- [Becker dataset](https://github.com/jon-becker/prediction-market-analysis) — historical bootstrap.
- Columbia wash-trading study (SSRN 5714122) — the contamination filter's motivation.
