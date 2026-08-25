# Metaculus Gap — Theory Design Spec

Date: 2026-08-24
Status: backlog — not yet proposed as a theory
Registry slug: `metaculus-gap` · Priority: 18 of 22 · Effort: M ·
LLM in decision path: match-time only (question pairing) ·
Backtest tier: A on the mechanical rule; pairs are confirmed facts

Part of the theory backlog
([index](2026-08-24-theory-backlog-index.md)). Before implementing: check
`python -m tools.cli ideas search "metaculus-gap"` for status changes,
then formalize via the `propose-theory` skill.

## Assessment

**Applicability 2/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 8/15** (rubric in the
[index](2026-08-24-theory-backlog-index.md); ordinal priors, not
calibrated probabilities)

- *Applicability 2:* the binding constraint is question overlap —
  Metaculus's long-horizon geopolitics/science questions intersect
  Kalshi's board thinly, and its community forecast updates slowly.
- *Implementability 3:* the API is keyless and clean; the work is the
  pair store (reused from cross-venue) and the staleness handling.
- *Likelihood 3:* Metaculus's aggregate is documented as well-calibrated
  and competitive with markets in comparative studies — but a
  no-capital, slow-updating forecast lagging a fast market means many
  "gaps" are just staleness; the premise test must separate the two
  before any bet.

## 1. Hypothesis

Metaculus's recency-weighted community forecast is a calibrated,
skill-weighted probability produced by a fundamentally different crowd
than Kalshi's bettors — forecasters scored on accuracy, not flow. Where a
matched Kalshi market's price diverges from a *fresh* Metaculus community
forecast beyond fees plus a threshold, the forecaster side is more often
right, and the Kalshi side that converges toward it is cheap.

## 2. Evidence

- Comparative studies find aggregated judgment platforms match or exceed
  prediction-market accuracy (markets-vs-polls experiments; Codi et al.
  2022 found Metaculus/GJO aggregates competitive with model ensembles on
  COVID forecasting; an ongoing multi-platform comparison tracks
  Polymarket/Metaculus/Manifold on matched questions).
- Metaculus scores forecasters with proper scoring rules and weights the
  aggregate by track record — structurally the "measured bucket rate"
  philosophy this repo already trusts, applied to people.
- The honest counterweight: with no capital at risk and slower update
  cadence, the community forecast can lag news by hours-to-days; on a
  fast-moving question the market is fresher, and the gap measures
  staleness, not mispricing. The design gates on forecast freshness for
  exactly this reason.

## 3. Non-goals and exclusions

- No pair without confirmed resolution-criteria equivalence — the
  cross-venue pair-store discipline, reused verbatim (Metaculus
  resolution text vs Kalshi rules; hand-confirm the first stable).
- Freshness gate: no candidate unless the community forecast has
  meaningfully updated (forecast count/recency from the API) after the
  most recent large Kalshi price move — a stale forecast is not fair
  value.
- Questions where Metaculus resolves on a different source or date are
  different bets, excluded at pairing.

## 4. Decision procedure

- Pair store: match Kalshi tickers to Metaculus questions via
  `tools/match_market.py`-style shortlisting on the Metaculus API's
  question list; confirmation compares resolution criteria (hand-first,
  LLM-later with provenance, exactly as cross-venue).
- Per-trade (mechanical): candidate when
  `|metaculus_cp − kalshi_price|` ≥ fees + threshold (start: 10 points —
  wider than cross-venue because the venues are less comparable), the
  freshness gate passes, and Kalshi liquidity clears the floor. Buy the
  Kalshi side that converges toward the community forecast.
  `edge_basis="model"`.

## 5. Data requirements

- Metaculus public API (keyless): community prediction time series,
  forecast counts, resolution text. Historical CP time series enables
  the tier-A backtest; verify depth at implementation.
- In-repo: board, candlesticks, pair store.

## 6. Backtest design

Tier A given confirmed pairs: over each pair's overlapping history,
apply the rule at historical Kalshi asks against the *then-current*
community forecast, settle. Premise test first, as with cross-venue:
when the two disagree (fresh forecasts only), who ends up right — the
forecasters or the market? No positive premise, no theory.

## 7. Kill criteria

- Premise test failing on fresh-forecast disagreements.
- Pair inventory < ~15 confirmed live pairs after an honest matching
  pass → throughput-bound; park with the revisit condition "Kalshi
  lists more long-horizon geopolitics/science markets" rather than kill.

## 8. Implementation plan

`theories/metaculus_gap/{THEORY.md,questions.py,divergence.py}` + tests,
reusing the cross-venue pair store. Build after cross-venue-fair-value
so the store exists. Effort M.

## 9. Testing approach

Unit tests: freshness gate logic, divergence arithmetic, pair-store
reuse, API-shape fixtures. Premise-test harness on fixture time series
with planted "who was right" outcomes.

## 10. Open risks

- Overlap may skew toward exactly the slow-moving questions where
  neither venue has edge worth fees; the premise test reports per-
  category so a surviving niche (e.g., science/tech timelines) is
  visible.
- Metaculus question wording drifts (edited questions); pair records
  pin resolution-text hashes like the implication-graph store.

## 11. Sources

- [Codi et al. 2022 context and platform-comparison work](https://manifund.org/projects/comparing-forecasting-platform-accuracy)
- [Metaculus scoring/aggregation documentation](https://www.metaculus.com/notebooks/17599/why-i-reject-the-comparison-of-metaculus-to-prediction-markets/) — including the platform's own argument for why it differs from markets, which is this spec's premise stated from the other side.
- [Markets-vs-polls literature overview](https://corporate.jasoncollins.blog/forecasting-platforms)
