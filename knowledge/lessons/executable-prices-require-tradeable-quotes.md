# A displayed price needs a tradeable book before it can evidence edge

**Summary:** Price the side actually payable and retain decision-time book fields so a historical quote can be tested for fillability.
**Applies to:** The completed 2026-09-03 series-bias sweep and the dated ladder, calendar, and aggregation probes; every liquidity threshold remains population-specific.
**Finding:** Measured — series-bias all-row favorite gaps ran from -2.05 to -15.27 points, while the study's filtered 36,257 observations were -1.04 to +0.36 gross across bands, with MDE 0.42-1.80. This does not establish a universal spread or open-interest cutoff.
**Do next time:** Store bid, ask, spread, open interest, and volume at the decision point; pre-register a local fillability test and compare mid, displayed quote, and executable price.
**Evidence:** [Series-bias pass 4](../../tickets/study/investigation/2026-08-29-series-bias-mining/STUDY.md#the-finding-at-a-fillable-quote-favorites-are-calibrated-at-every-level); [aggregation-gap executable basket](../../tickets/study/answer/2026-09-01-aggregation-gap-probe/STUDY.md)
**Revisit when:** A new corpus has order-level depth or a separately validated fill model.
**Updated:** 2026-09-04
