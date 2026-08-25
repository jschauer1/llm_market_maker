# News Drift — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `news-drift` · Priority: 5 of 17 · Effort: M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "news-drift"` for status changes, then
formalize via the `propose-theory` skill. **Read section 3 — this spec
shares a signal with overreaction-fade and the two must be built against
one joint measurement.**

## Assessment

**Applicability 4/5 · Implementability 4/5 · Likelihood of success 2/5 ·
Composite 10/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* frequent signals across active categories with
  direct entries.
- *Implementability 4:* candlesticks suffice; the joint sign measurement
  is shared work with overreaction-fade.
- *Likelihood 2:* scored low deliberately. The only direct Kalshi drift
  measurement (Angelini & De Angelis) found the phenomenon real but
  **dead net of spread** at its measured timescale; daily-scale survival
  is an extrapolation. The honest prior is that the net edge is zero and
  the backtest exists to overturn that cheaply, not to confirm a strong
  expectation.

## 1. Hypothesis

When a Kalshi price moves sharply (new information arriving), it
underreacts: the move continues in the same direction over the following
hours-to-days. Enter in the direction of a large recent move, hold to
resolution (v1) or for a fixed horizon (v2).

## 2. Evidence — and the honest caution

Underreaction and post-news drift are among the most robust findings in
behavioral finance (post-earnings-announcement drift; Hong–Stein slow
information diffusion). Angelini & De Angelis 2026 measured it *on Kalshi
directly* (NBA in-play, one-minute quotes vs a public-information
benchmark): prices adjust only **0.64-for-one on impact**, the missing
adjustment predicts drift over the following minutes, and underreaction
is worse when liquidity is thin and signals salient. The caution is in
the same paper: **minute-scale drift was not profitable net of bid–ask.**
So the only direct Kalshi test found the phenomenon real but untradeable
at that timescale. This theory's bet is specifically that *slower* drift
— daily-scale moves where information diffuses over days — clears the
spread. Plausible (equity drift horizons are weeks), but an extrapolation
the backtest exists to check.

## 3. Non-goals and exclusions — the overreaction-fade boundary

[overreaction-fade](2026-08-24-theory-overreaction-fade-design.md) bets
*reversal* of the same signal in political markets, backed by Clinton &
Huang's negative daily autocorrelation. Continuation and reversal are the
two signs of one measured object, so:

- **One shared move-response measurement** (section 6) assigns each
  (domain × horizon × move-size) cell a sign. This theory may only claim
  cells measured `continuation`; overreaction-fade only cells measured
  `reversal`; unstable cells go to neither. The assignment lives in both
  THEORY.md files; re-assignment bumps both versions.
- **Live sports excluded entirely** — where net drift is already measured
  dead, and it resolves too fast for manual bets. Target domains where
  information arrives in stories: politics, econ, entertainment, world
  events.

## 4. Decision procedure

Fully mechanical.

- Signal: from candlesticks, a move ≥ X points (start: 15) within ≤ 24h,
  volume above the market's trailing median (a jump on no volume is a
  stale-quote artifact), post-move price within $0.15–$0.85.
- Entry: the **ask on the move side** at the first candle after the
  signal completes — never mid, never inside the signal window.
- Edge: measured — `P(resolves in move direction | signal)` vs the
  post-signal ask, binned by move size and post-move price.
  `edge_basis="measured"` once bins have n.

## 5. Data requirements

Candlesticks with bid/ask only. Check the finest interval the API
provides and state it in THEORY.md before trusting the backtest — it
bounds entry-timing fidelity.

## 6. Backtest design

Tier A, candlesticks only, **joint with overreaction-fade**: one script
computes signed subsequent outcomes (continuation vs reversion, gross and
net) for every qualifying historical move, binned by (domain ×
days-to-close × move size), split-sample across time. Both theories
consume the resulting signed cell table.

Lookahead traps: (a) signal from completed candles only; (b) entry at the
*next* candle's ask; (c) exclude moves that are the resolution event
arriving (price-band filter plus close-time proximity check).

## 7. Kill criteria

Drift exists gross but dies net of spread + fees → record the gross/net
split explicitly; that separates "no phenomenon" from "real phenomenon,
untradeable here", which carry different revisit angles (the latter
revives if Kalshi liquidity deepens).

## 8. Implementation plan

`theories/news_drift/{THEORY.md,signal.py}` + the shared measurement
script (theory-local in whichever of the pair is built first; promoted to
`tools/` when the second consumes it). Effort M.

## 9. Testing approach

Unit tests: move detection, volume filter, next-candle entry selection,
resolution-event exclusion. Fixture paths that continue/revert, verifying
the joint measurement signs cells correctly.

## 10. Open risks

- Candlestick granularity (see section 5).
- Signal overlap with scheduled events: a post-debate move is
  information, not inattention; the joint measurement bins by
  proximity-to-scheduled-event so the two mechanisms aren't averaged.

## 11. Sources

- [Angelini & De Angelis 2026](https://arxiv.org/pdf/2606.07811) (read in full) — 0.64 impact coefficient; net-of-spread negative at minute scale.
- [Hong & Stein 1999](http://www.columbia.edu/~hh2679/jf-mom.pdf), [PEAD overview](https://jkatz.caltech.edu/documents/28622/peads.pdf) — the timescale extrapolation this thesis rests on.
