---
title: Official Netflix prior-week views predict the next top-movie views ladder
lane: new-theory
created: 2026-09-05
created_by: codex-attention-20260905
author_lane: find-theories
author_focus: netflix-view-carryover
author_context: Source-only successor audit after the opening-weekend box-office population proved legally unavailable; no model fitting or returns inspected.
status: open
---
Effort: S-M · LLM in decision path: no · Anticipated backtest tier: A only if predictor vintages pass the availability gate below

## Assessment

**Applicability 4/5 · Implementability 4/5 · Likelihood 2/5 · Composite 10/15.** The payoff is a recurring weekly Kalshi ladder with direct official labels and enough pre-Kalshi observations to train once. The market may already understand simple chart persistence, and only 32 unexposed settled Kalshi event dates are presently available.

## Hypothesis and mechanism

For `KXNETFLIXTOPVIEWSMOVIE` only, the next weekly maximum on Netflix's Global `Movies | English` chart is partly determined by the previous chart's #1 view count. Traders may focus on salient coming releases and named-title narratives while failing to price the empirical transition distribution consistently across numeric rungs. This can persist because the useful signal is a weekly table-to-distribution calculation and the central ladder rungs can have meaningful spreads. The counterargument is strong: this input is public and simple, so the edge may already be inside the spread.

This is fully mechanical. Wikimedia attention is excluded from version 1: it adds title matching and redirect handling before the direct official signal has earned that complexity.

## Exact population and clock

Include every event in series `KXNETFLIXTOPVIEWSMOVIE`; include no Netflix rank, runner-up, country, or non-English series. The retained current+historical API census on 2026-09-05 contains **387 markets in 35 weekly events: 34 finalized and one active**, from the chart published 2026-01-13 through 2026-09-08. Rules specify the #1 movie's `Views`, Global `Movies | English`, for the chart published Tuesday covering the week ending Sunday.

Decision time is **Wednesday 12:00 UTC after event open**. Use the first 60-minute Kalshi candle ending at or after that timestamp and strictly before close. This avoids assuming an intraday Netflix release hour: Netflix promises Tuesday publication, so the prior chart is public by Wednesday 12:00 UTC. Use the observed side ask close, never midpoint; require both sides quoted inside (0,1) and spread <=4 cents. Retain missing events and reasons.

## Data and point-in-time gate

Netflix's official Top 10 page and `all-weeks-global.xlsx` provide weekly rank, views, runtime, hours viewed, and weeks in Top 10. Netflix states weeks run Monday-Sunday, lists publish Tuesday, and the `views` ranking began in June 2023. The fixed training calendar is 2023-06-26 through 2025-12-28: 131 weekly targets before any Kalshi event.

The source audit was frozen before values and sampled 11 every-13th-week rows across 2023-2025. Every article was published Tuesday; all 11 #1 titles agreed, and #1 views agreed exactly in 10, with the eleventh stated as 55M in the article versus 55.1M in the archive. Exact age was recoverable in only 8/11 articles and complete top-five titles in 1/11, so version 1 excludes both fields. Two lower-rank view values also differed, confirming that a week date proves which release was available Tuesday but does not itself prove unchanged values. The bounded result and receipts are under `.superpowers/sdd/attention-source-census-20260905/netflix-successor/source-drift-audit/`. Kalshi market/candle data come from official current and historical APIs.

## Fixed baseline

For week `t`, target `y_t = log(#1 Views_t)` and the sole predictor is `log(#1 Views_{t-1})`. Fit one OLS on the fixed pre-2026 calendar. Freeze coefficients and the empirical training-residual CDF before loading 2026 outcomes or returns; do not refit, transform, winsorize, or scan feature subsets.

For each strike, derive `P(#1 Views_t >= strike)` from that frozen residual CDF. Compute fee-net EV at YES and NO asks. Choose at most one side/rung per event: the greatest positive fee-net gap, requiring at least 5 cents. No signal is also an output.

## Clean evaluation and falsifiers

The holdout is all 34 finalized Kalshi events through the chart published 2026-09-01, except the weeks ending 2026-06-14 and 2026-08-30, whose #1 values were exposed during source discovery. That leaves at most **32 unexposed event clusters**. Report coverage, Brier score versus the market ask-implied probability, gross and fee-net return at asks, and a 95% event-level interval. No current opportunity is claimed before this replay.

Promote only if at least 30 unexposed events have verified inputs and executable quotes and the lower 95% bound on mean fee-net return is above zero. Kill if coverage is below 30, the model fails to improve on market probability forecasts, or any apparent gross edge disappears after asks and fees. Report a source-vintage failure as underpowered, not evidence against the mechanism.

## Relation to prior work

`attention-model` is parked because its opening-weekend box-office payoff is legally/product unavailable; its predictive mechanism was never tested. This successor uses a listed streaming payoff and official labels. `fine-print-divergence` studies title/rules date misunderstandings, while this model parses `rules_secondary` only to identify the correct week. `series-bias-mining` observed a small negative `KXRT` sample but did not test this series or transition signal.

## Sources

- Netflix, `Top 10 Things to Know About Our Weekly Top 10`: https://about.netflix.com/en/news/top-10-things-about-netflix-top-10
- Netflix official Top 10 and archive: https://www.netflix.com/tudum/top10 and https://www.netflix.com/tudum/top10/data/all-weeks-global.xlsx
- Retained Kalshi/source census: `.superpowers/sdd/attention-source-census-20260905/netflix-successor/manifest.json`
