# Overreaction Fade — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `overreaction-fade` · Priority: 7 of 22 · Effort: M ·
LLM in decision path: no · Backtest tier: A

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "overreaction-fade"` for status changes,
then formalize via the `propose-theory` skill. **Read section 3 first — this
spec shares a signal with news-drift and the two must be built against one
joint measurement.**

## Assessment

**Applicability 4/5 · Implementability 4/5 · Likelihood of success 3/5 ·
Composite 11/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* politics is Kalshi's deepest category; signals are
  dense in election cycles and sparse off-cycle.
- *Implementability 4:* candlesticks only; the joint sign measurement is
  shared with news-drift.
- *Likelihood 3:* negative autocorrelation is measured at scale, but at
  mid prices, during an extraordinary period (the 2024 final weeks);
  net-of-spread survival and off-cycle stability are both untested, and
  the regime-dependence risk is named in the spec's own kill criteria.

## 1. Hypothesis

In political and politics-adjacent markets, large short-window price moves
overshoot: traders react to the market's own dynamics (momentum chasing,
herding, salience) rather than to information, and the move partially
reverts over the following day(s). Fade large moves — buy the side the move
ran away from — in the (domain × horizon) cells where reversion is
measured.

## 2. Evidence

- Clinton & Huang 2025 (Vanderbilt; 2,500+ political markets across IEM,
  Kalshi, PredictIt, Polymarket; $2.4B in the final five weeks of the 2024
  presidential campaign): daily price changes weakly correlated or
  **negatively autocorrelated**; little evidence of efficiency; traders
  "react not only to political developments but also to the dynamics of
  the markets themselves." Practitioner summaries report negative serial
  correlation in a majority of national presidential markets and 60–70%
  reversion of 10pp+ moves near expiry.
- Dalen 2025, "Toward Black-Scholes for Prediction Markets"
  (arXiv 2510.15205): documents "event vega" — price jitter from
  uncertainty itself rather than news, concentrated before close; a
  structural reason late moves overshoot without information.
- The tension worth stating: Angelini & De Angelis 2026 measured
  *under*reaction on Kalshi (NBA in-play). Both are real — underreaction to
  verifiable public signals at minute scale, overreaction to narrative and
  market-dynamics at day scale in politics. The sign is an empirical
  property of the (domain, timescale, trigger) cell, which is why section 6
  is a joint design.

## 3. Non-goals and exclusions — and the news-drift boundary

The [news-drift spec](2026-08-24-theory-news-drift-design.md) bets
*continuation* after large moves; this spec bets *reversal*. They are the
two signs of one measured object. To prevent the two theories from taking
opposite sides of the same market and calling both a win:

- **One shared move-response measurement** (section 6) assigns each
  (domain × horizon × move-size) cell a measured sign. news-drift may only
  claim cells measured `continuation`; overreaction-fade may only claim
  cells measured `reversal`. A cell is claimed by at most one theory, the
  assignment lives in both THEORY.md files, and re-assignment bumps both
  versions.
- Live sports excluded (resolves too fast for manual bets; the in-play
  literature is its own regime).
- Moves explainable by a scheduled information event (a debate, a data
  release, a verdict — detectable from close-time/series metadata) are not
  "market dynamics" moves; v1 excludes moves within 12h after a known
  scheduled event for the *fade* side.

## 4. Decision procedure

Fully mechanical.

- Signal: from candlesticks, a move ≥ X points (start: 10) within ≤ 24h in
  a politics-domain market, post-move price within $0.15–$0.85, volume
  above the market's trailing median (rules out stale-quote jumps).
- Candidate: buy the faded side (the side the move ran away from) at its
  ask on the first candle after the signal window.
- Edge: measured — `P(reverts ≥ fees+buffer | cell)` from the tier-A
  measurement; `edge_basis="measured"` per cell, Wilson-bounded.
  Exit: v1 holds to resolution (simplest, no exit-timing model);
  a fixed-horizon exit (48h) is a v2 requiring its own measured rates.

## 5. Data requirements

In-repo only: candlesticks with bid/ask (`tools/kalshi/history.py`),
domain from ticker hierarchy, board for live scanning. No external feeds.

## 6. Backtest design

Tier A, and **joint with news-drift**: one script computes, for every
settled market with a qualifying move, the signed subsequent outcome
(continuation vs reversion, gross and net of spread+fees), binned by
(domain × days-to-close × move size). Output: a signed cell table both
theories consume. Split-sample discipline: signs assigned on the first half
of history must hold in the second half; unstable cells are claimed by
neither theory.

Lookahead traps: signal from completed candles only; entry at the *next*
candle's ask; exclude moves that are the resolution event arriving
(close-time proximity + post-move price extremity check).

## 7. Kill criteria

- No cell shows out-of-sample reversion clearing spread + fees → the
  Clinton–Huang effect exists at mid but is untradeable at Kalshi
  executable prices; record gross/net split (same protocol as news-drift).
- Cells flip sign between halves of history → the phenomenon is
  regime-dependent (election-cycle-driven); park with revisit condition
  "next high-volume political cycle" rather than kill.

## 8. Implementation plan

`theories/overreaction_fade/{THEORY.md,signal.py}` + the shared
measurement script, which should live with whichever of the two theories
is built first and be promoted to `tools/` when the second consumes it
(the repo's promotion rule). Effort M.

## 9. Testing approach

- Unit tests: move detection windows, cell assignment, the
  scheduled-event exclusion, entry-price selection (next candle's ask).
- Fixture backtests with constructed reverting/continuing price paths
  verifying the joint measurement assigns signs correctly and neither
  theory claims an unstable cell.

## 10. Open risks

- Candlestick granularity bounds signal precision — same risk as
  news-drift; state the finest available interval in THEORY.md.
- The strongest evidence is from one extraordinary period (final weeks of
  a presidential election). Off-cycle politics may show nothing; the
  measurement must bin by proximity-to-major-event or the cycle effect
  will be averaged invisible.
- Holding to resolution on faded political markets can mean weeks of
  capital lockup for a few points; sizing must price that.

## 11. Sources

- [Clinton & Huang 2025 — Prediction Markets? The Accuracy and Efficiency of $2.4B in the 2024 Presidential Election](https://ideas.repec.org/p/osf/socarx/d5yx2_v1.html)
- [Dalen 2025 — Toward Black-Scholes for Prediction Markets](https://arxiv.org/pdf/2510.15205)
- [Angelini & De Angelis 2026](https://arxiv.org/pdf/2606.07811) — the underreaction counter-evidence that motivates the joint sign measurement.
