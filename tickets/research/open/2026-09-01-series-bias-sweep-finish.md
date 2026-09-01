---
title: Finish the series-bias phase-2 sweep and extend pass 3
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-86
status: open
---
The broad settled-history sweep (studies/2026-08-29-series-bias-mining/collect.py) is the prerequisite for every future pass of this study, and it is PARTIALLY DONE. Resume it with:

    python studies/2026-08-29-series-bias-mining/collect.py prices
    python studies/2026-08-29-series-bias-mining/collect.py status

It is resumable and per-series atomic: it skips anything already in `progress` and commits each series as it completes, so re-running costs nothing and never restarts from zero.

STATE AT 2026-09-01. Phase 1 (walk) is COMPLETE: 8,533 series, 981,451 settled markets, 840 eligible (40-1,000 settlements). Phase 2 (prices) got to roughly 660/840 series. The remainder are the LARGEST series, because eligible_series walks ascending by count deliberately -- so what is left is the expensive tail, ~180 series at 300-1,000 markets each, which is many hours at Kalshi's ~4-5 candle fetches/s. Do not expect to finish it in one session either; just extend it.

WHY IT MATTERS AND WHY IT IS URGENT. Kalshi archives settled markets out of its public API ~60 days after close. Every day this sits, the front of the window is lost UPSTREAM, permanently -- this is the one dataset in the repo whose input perishes. It is also the fix for the study's standing defect: passes 1 and 2 tested SEVEN and ONE real series respectively and both had to declare themselves "not measured". Pass 3 tests hundreds.

WHAT PASS 3 ALREADY IS. The analysis bar is pre-registered and committed in STUDY.md ("Pass 3 analysis bar", 2026-09-01) BEFORE any per-series number was computed, along with its robustness views and its size-truncation disclosure. The runner is studies/2026-08-29-series-bias-mining/pass3.py, fixture-tested in tests/test_series_bias_pass3.py. Re-running it after extending the sweep is one command.

READ THIS BEFORE RE-RUNNING. STUDY.md fixes a one-run rule: the family grows by adding series, and a larger family is a harsher Holm divisor, so two runs over two collection states are two different tests. A later pass that extends the sweep should report its own state and its own family size, and must not present whichever of the two looks better. Say which collection state produced the number.

ALSO NOTE the pre-registered signs for the carried candidates (KXRT negative, KXLOWTLV positive) and the size-truncation caveat: the tested family is the LOWER-FREQUENCY half of the population, and the high-frequency tail is unmeasured rather than measured-and-null. Finishing the sweep is what closes that gap.
