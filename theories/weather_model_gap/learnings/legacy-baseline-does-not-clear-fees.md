# The simple weather-error baseline did not beat executable asks

**Summary:** Do not reuse WG-1's legacy NWS baseline as a demonstrated edge or an automatic bridge to current TWC prices.

**Applies to:** Unchanged WG-1 formula under NWS rules; NYC/LAX/Midway, May 1–August 13, 2026; one frozen experimental holdout.

**Finding:** Measured: 297 settled positions averaged −5.61 net points (−5.99 with rounded one-contract fees). Event, weather-date and settlement-date 95% intervals were below zero; all upper bounds were below the +3-point practical-effect bar. No city passed its adjusted support test. NYC's +1.57-point mean remains uncertain, not a rescued winner.

**Do next time:** Require a new mechanism or justified forecast improvement and untouched evidence before repeating this baseline. More current-source history alone does not repair the legacy model's demonstrated failure.

**Evidence:** [Frozen diagnostic](../backtests/wg1-nws-20260905/RESULTS.md), run `exp/wg1-nws-20260905/holdout`; decisions and source identity retained. Experiment rows cannot calibrate production.

**Revisit when:** A predefined improvement has an independent validation population.

**Updated:** 2026-09-05.
