# Observed close cannot stand in for a scheduled deadline

**Summary:** Build historical horizons from scheduled deadlines, then trace the exact attempt runs feeding the score before auditing exposure.
**Applies to:** By-deadline markets in the 2026-08-29 full-coverage audit and the 2026-09-01 judged-campaign audit; other resolution mechanisms are untested.
**Finding:** Measured — actual close was outcome-dependent, and 18.7% of captured judged-run markets closed more than three days early. `custom_strike.Date` supplied only 61 of 625 classifications, while a sibling-max proxy agreed 53.3%. The formal exposed-versus-clean contrast missed its cluster floor, so its magnitude remains unmeasured.
**Do next time:** Use exact published deadline fields where present, fall back to a tested rules parser, preserve UNKNOWN, and locate contributing evidence through `opportunity_attempts.run_id`.
**Evidence:** [Original exposure audit](../../tickets/study/answer/2026-08-29-early-close-exposure-existing-backtests/STUDY.md#result); [scored-population follow-up](../../tickets/study/answer/2026-09-01-early-close-exposure-in-the-bettable-slice/STUDY.md#result)
**Revisit when:** Deadline-field coverage changes or archived payloads support a stronger parser on the same population.
**Updated:** 2026-09-04

