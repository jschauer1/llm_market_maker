---
title: Finish the series-bias phase-2 sweep and extend pass 3
lane: maintenance
study: 2026-08-29-series-bias-mining
created: 2026-09-01
created_by: llm-market-identifier-86
author_context: Filed as new-theory before the study lane existed; it is the study's own phase-2 sweep, resumed with its own collect.py.
status: done
closed: 2026-09-03
resolution: Both halves done 2026-09-03 by fleet-w2-g4 (study lane). PHASE 2 IS COMPLETE: 840/840 eligible series priced, 146,964 observations across 830 series, 99.98% carrying spread+open_interest. Nothing eligible remains to collect. PASS 3 RE-RUN on the completed state: 496 tested (was 347), 30 flagged (was 9), median MDE 9.67 (was 12.16) -- still NOT MEASURED against the 8.0 bar, and 10 of 17 control series trip the gates. Reported in STUDY.md as its own test on its own collection state, never pooled with the frozen run, per the one-run rule. The urgency this ticket named was real and is now spent: the corpus is captured. NOTE the ticket's documented resume command did not run -- collect.py/mine.py/pass3.py still carried parents[5]/parents[6] sys.path offsets from the pre-retirement location, so every one of them died with ModuleNotFoundError. Fixed by locating the repo root by marker instead of by depth; that is almost certainly why the collector was found IDLE.
---
The broad settled-history sweep (tickets/study/investigation/2026-08-29-series-bias-mining/collect.py) is the prerequisite for every future pass of this study, and it is PARTIALLY DONE. Resume it with:

    python tickets/study/investigation/2026-08-29-series-bias-mining/collect.py prices
    python tickets/study/investigation/2026-08-29-series-bias-mining/collect.py status

It is resumable and per-series atomic: it skips anything already in `progress` and commits each series as it completes, so re-running costs nothing and never restarts from zero.

STATE AT 2026-09-01. Phase 1 (walk) is COMPLETE: 8,533 series, 981,451 settled markets, 840 eligible (40-1,000 settlements). Phase 2 (prices) got to roughly 660/840 series. The remainder are the LARGEST series, because eligible_series walks ascending by count deliberately -- so what is left is the expensive tail, ~180 series at 300-1,000 markets each, which is many hours at Kalshi's ~4-5 candle fetches/s. Do not expect to finish it in one session either; just extend it.

WHY IT MATTERS AND WHY IT IS URGENT. Kalshi archives settled markets out of its public API ~60 days after close. Every day this sits, the front of the window is lost UPSTREAM, permanently -- this is the one dataset in the repo whose input perishes. It is also the fix for the study's standing defect: passes 1 and 2 tested SEVEN and ONE real series respectively and both had to declare themselves "not measured". Pass 3 tests hundreds.

WHAT PASS 3 ALREADY IS. The analysis bar is pre-registered and committed in STUDY.md ("Pass 3 analysis bar", 2026-09-01) BEFORE any per-series number was computed, along with its robustness views and its size-truncation disclosure. The runner is tickets/study/investigation/2026-08-29-series-bias-mining/pass3.py, fixture-tested in tests/test_series_bias_pass3.py. Re-running it after extending the sweep is one command.

READ THIS BEFORE RE-RUNNING. STUDY.md fixes a one-run rule: the family grows by adding series, and a larger family is a harsher Holm divisor, so two runs over two collection states are two different tests. A later pass that extends the sweep should report its own state and its own family size, and must not present whichever of the two looks better. Say which collection state produced the number.

ALSO NOTE the pre-registered signs for the carried candidates (KXRT negative, KXLOWTLV positive) and the size-truncation caveat: the tested family is the LOWER-FREQUENCY half of the population, and the high-frequency tail is unmeasured rather than measured-and-null. Finishing the sweep is what closes that gap.

---

## Lane change, 2026-09-02 — this was a `mention_family` theory ticket

`mention_family` was retired by the user on 2026-08-27 and migrated to
`theories/retired/mention_family/` on 2026-09-02. This ticket lived in
that theory's own `tickets/open/` folder until then, which is why its
`author_lane` and history read the way they do.

It is a **maintenance** ticket now, and it has no owning theory. The
study it concerns did not retire with the theory: it was still in
`investigation`, other studies read its corpus, and it is now ownerless
at

    tickets/study/investigation/2026-08-29-series-bias-mining/

Every path in the body above has been repointed to that home. Nothing
about the work asked for here changed with the move.
