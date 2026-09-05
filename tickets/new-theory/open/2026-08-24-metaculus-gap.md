---
title: Where a fresh Metaculus community forecast diverges from a matched Kalshi price, the forecaster side is more often right
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: open
---
Effort: M · LLM in decision path: match-time only (question pairing) · Backtest tier: A on the mechanical rule; pairs are confirmed facts

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "metaculus-gap"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 2/5 · Implementability 2/5 · Likelihood of success 3/5 ·
Composite 7/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 2:* the binding constraint is question overlap —
  Metaculus's long-horizon geopolitics/science questions intersect
  Kalshi's board thinly, and its community forecast updates slowly.
- *Implementability 2:* the official API now requires authentication and
  exposes Community Prediction data only on a limited question set. A public
  embed payload currently exposes aggregate history, but it is undocumented
  and therefore needs a retained-response fallback.
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

- Metaculus question data: community-prediction time series, forecast counts,
  resolution text, and edit provenance. The authenticated API is access
  limited. The tested no-login fallback is the official
  `/questions/embed/{post_id}/` page, whose server payload contains the current
  question and `recency_weighted.history`; retain every response because this
  surface is undocumented. Metaculus also documents a question-page **Download
  data** action, but no-login access has not been verified.
- In-repo: board, candlesticks, pair store.

### Verified access and current probe — 2026-09-05

Peltola question 41678 exposed a 53% YES Community Prediction; Kalshi
`KXAKSENATE-26NOV03-MPEL` was 65/66 YES and 34/35 NO. The 47% Metaculus NO
versus the executable 35-cent NO ask was 10.41 points after the repository fee
model, with depth, and an expected 66-day duration. It is **not an accepted
pair**: Metaculus resolves from state-certified results, while Kalshi adds a
taking-office condition and disputed-result fallbacks. The ordinary-outcome
implication makes Metaculus NO a conservative translation for Kalshi NO, but
only conditional on the Metaculus probability being valid; it is not a
statistical confidence bound. Test such directional implications separately
from the exact-match baseline.

The post was edited 65 minutes after the latest aggregate segment began. The
public payload has no field-level revision history, so it does not establish
whether title, background, or criteria changed, nor the last individual
reaffirmation time. Treat freshness as unresolved. Retained source responses
and hashes are in the [2026-09-05 capture](../../../.superpowers/sdd/metaculus-gap-20260905/manifest.json).

## 6. Backtest design

Tier A given confirmed pairs: over each pair's overlapping history,
apply the rule at historical Kalshi asks against the *then-current*
community forecast, settle. Premise test first, as with cross-venue:
when the two disagree (fresh forecasts only), who ends up right — the
forecasters or the market? No positive premise, no theory. Report both event
and resolution-date clusters: multiple 2024 state races on one election day
are not independent calendar observations. A useful first test therefore needs
several nonidentical election dates or recurring macro releases.

A bounded feasibility probe found one usable recurring family: Metaculus post
13960 has resolved monthly headline-CPI questions that match Kalshi `KXCPI` on
the BLS first estimate, seasonal adjustment, month, and one-decimal resolution.
The public embed exposes a final 201-point aggregate CDF before each release,
and Kalshi's archive exposes hourly bid/ask candles, so a one-observation-per-
release diagnostic can cover at least eight 2025 release dates. It does not
support an intramonth time-series replay: older embed segments retain interval
summaries and a median, not the full historical CDF. The group post was edited
after those releases and exposes no revision diff, so this remains a
provenance-limited diagnostic until contemporaneous criteria or an official
export is recovered. Count every CPI release once; its many strikes are one
cluster.

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
