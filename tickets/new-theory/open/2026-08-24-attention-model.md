---
title: Wikipedia pageviews predict opening box office, and entertainment is Kalshi's least efficient category
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: open
---
Effort: M · LLM in decision path: no · Backtest tier: A

**This ticket is the spec.** Before starting, run
`python -m tools.cli ideas search "attention-model"` in case the status
moved, and read [the backlog's shared contracts](../README.md)
first — rules 0 through 0e there have killed more ideas in this
repo than any single spec's own kill criteria have.

## Assessment

**Applicability 3/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 9/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 3:* box-office and Rotten-Tomatoes markets are a
  steady but modest inventory (weekly releases), with decent liquidity
  on blockbusters (~1.5% spreads reported).
- *Implementability 3:* Wikipedia pageview data is keyless and clean;
  the work is fitting and walk-forwarding the attention→outcome mapping
  against historical box office and Kalshi ladders.
- *Likelihood 3:* published predictive power (a month ahead) plus the
  measured fact that entertainment is Kalshi's *least efficient*
  category (4.79–7.32pp maker–taker gaps) — but the core study is a
  decade old, media consumption has shifted, and studios/traders may
  already watch the same dashboards.

## 1. Hypothesis

Public attention data — Wikipedia pageviews for a film and its cast —
predicts opening box office weeks in advance. Kalshi's entertainment
markets sit in the platform's least-efficient category and are priced by
fan sentiment. A mechanical attention→outcome model, fit on historical
releases, finds strikes where the market's implied opening diverges from
the attention signal.

## 2. Evidence

- Mestyán, Yasseri & Kertész (PLOS One 2013): Wikipedia activity
  (pageviews and editor activity) predicts opening-weekend box office
  with useful accuracy up to a month before release.
- Becker's category decomposition: Entertainment/Media shows the largest
  maker–taker inefficiency on Kalshi (4.79–7.32pp vs 0.17pp for
  Finance) — the crowd in these markets measurably prices worst.
- Kalshi's movie vertical (box office grosses, Rotten Tomatoes scores)
  is established, with reported ~1.5% median spreads on blockbusters —
  liquid enough to trade the signal.

## 3. Non-goals and exclusions

- v1 uses Wikipedia pageviews only. Google Trends has no stable keyless
  API (scraping breaks); add it later only if a compliant path exists.
- Box-office gross ladders and opening-weekend markets first; Rotten
  Tomatoes score markets are a distinct sub-model (critic dynamics, not
  public attention) and wait for a v2 with their own fit.
- No sentiment analysis, no LLM reading of buzz — pageview counts and
  their time-derivatives only, so the model stays mechanical and
  auditable.

## 4. Decision procedure

Fully mechanical.

- Feature set per film: pageview level and slope over trailing windows
  (28d/7d) for the film's article (+ lead cast), normalized against a
  reference class of past releases in the same season/genre scale.
- Model: a deliberately small regression from features →
  opening-outcome distribution, fit walk-forward on past releases with
  realized box office (public data). Map the distribution onto the
  Kalshi ladder → per-strike probabilities.
- Candidate: |model − market| ≥ threshold (start: 8 points, borrowed
  deliberately from the weather spec's practitioner floor) with a
  liquidity floor; one candidate per ladder. `edge_basis="model"`,
  claim capped (start: 5 points).

## 5. Data requirements

- Wikimedia pageviews API — keyless, with full history (verify
  per-article depth at implementation).
- Historical box-office actuals (public: Box Office Mojo-style figures;
  scrape-free sources to be confirmed — if none is keyless and stable,
  the model fits on Kalshi's own settled ladders instead, which the
  repo already has).
- In-repo: board, candlesticks, fee math.

## 6. Backtest design

Tier A: for each settled box-office market in the candlestick window,
compute features from pageview history *as of* decision dates (the API
serves historical daily counts, so as-of reconstruction is exact), apply
the walk-forward model, trade the rule at historical asks, settle.
Lookahead traps: the fit must exclude the film being scored and all
later releases; pageview windows end strictly before decision time.

## 7. Kill criteria

- Walk-forward model no better than the market at the strikes it flags →
  the attention signal is priced in; kill, record per-scale results
  (blockbusters and small releases may differ).
- Fewer than ~30 settled markets available to fit on → `paused` until
  the vertical's history grows; the spec is early, not wrong.

## 8. Implementation plan

`theories/attention_model/{THEORY.md,features.py,model.py,screen.py}` +
tests. Effort M. The pageview client is a `tools/` promotion candidate
if other cultural-market theories emerge.

## 9. Testing approach

Unit tests: feature windows and normalization, walk-forward exclusion
boundaries, ladder mapping. Fixture films with planted attention spikes
verifying the as-of reconstruction.

## 10. Open risks

- Streaming-era decay of the 2013 relationship is the main scientific
  risk; the walk-forward fit on recent years answers it directly.
- Small-n per year (~dozens of wide releases); pooled evidence across
  scales with per-scale reporting is the only way to reach n.
- Film-article naming/redirects on Wikipedia need care (renames,
  disambiguation) — resolve article IDs, not titles.

## 11. Sources

- [Mestyán, Yasseri & Kertész 2013 — Early Prediction of Movie Box Office Success Based on Wikipedia Activity](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0071226)
- [Becker — category inefficiency decomposition](https://www.jbecker.dev/research/prediction-market-microstructure)
- [Kalshi movie markets](https://kalshi.com/category/culture/movies) · [Rotten Tomatoes markets primer](https://news.kalshi.com/p/making-money-with-rotten-tomatoes-movie-markets-kalshi-kit)
