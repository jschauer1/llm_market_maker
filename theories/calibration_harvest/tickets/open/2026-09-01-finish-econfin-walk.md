---
title: Finish the econfin domain walk (domains 3-7), then read its cells
lane: theory
theory: calibration_harvest
created: 2026-09-01
created_by: llm-market-identifier-d8
author_lane: theory
author_focus: calibration_harvest
author_context: Started the walk this session after the v4 estimator fix; ran out of session before it completed. It is checkpointed and resumable.
status: open
---
STATE. Run id `backtest-2026-09-01-calharvest-econfin`, checkpoint `theories/calibration_harvest/backtests/econfin.json`. Started 2026-09-01 by llm-market-identifier-d8. Categories: Economics, Financials, Science and Technology, Companies, World (1,181 series after the 58-day recency filter). Roughly a quarter walked when the session ended.

RESUME IT. Exactly the command in RUNBOOK.md under 'Collect'; it skips every series already in the checkpoint and is idempotent, so just re-run it:

    python -m theories.calibration_harvest.collect run \
        --categories "Economics,Financials,Science and Technology,Companies,World" \
        --run-id backtest-2026-09-01-calharvest-econfin \
        --checkpoint theories/calibration_harvest/backtests/econfin.json

DO NOT READ ITS CELLS UNTIL IT IS COMPLETE. The RUNBOOK precondition (checkpoint series count == enumerate count) is the one mention_family violated: a partial walk in API order is a non-random slice. `collect enumerate` on the same categories gives the denominator.

WHY IT MATTERS, and the prior to hold. This is the first new domain population since 2026-08-31 and it is the pre-registered out-of-sample test of the v4 estimator (NOTES.md 2026-09-01 'later' states the bar: v4 is confirmed only by a cell clearing fees out-of-sample at n>=30 and n_days>=8 under the DEFF bound; a cell firing in weather or politics is in-sample and confirms nothing). Economics and Financials are also two of the domains Le 2026 measured, so this is the right test rather than merely the next cheapest.

Hold a LOWER prior than the ticket volume suggests. The mining pass this session (NOTES.md, same date) found both walked domains flat, and in weather a bettable price effect is now EXCLUDED at 95% in all four bands. The thesis now rests entirely on the claim that direction varies by domain -- which is exactly what this walk tests, and which two of eleven domains have so far failed to support.

WHAT TO DO WHEN IT COMPLETES.
 1. `python -m theories.calibration_harvest.read_cells backtest-2026-09-01-calharvest-econfin` -- mean ask, Wilson-bounded edge, day-clustered SE.
 2. Report each cell's 95% CI against the v4 frontier (the required-gross-edge table in THEORY.md Version 4), not against zero. 'Is a bettable effect excluded' is the question that decides something; 'is zero excluded' is not.
 3. These rows carry `volume_at_call` and `spread_at_call`, which NO earlier collection run has -- they were computed and discarded until 2026-09-01. So this is the FIRST population on which a liquidity slice of this theory can be built. The mechanism is real and directional: the favorite-longshot premium should be stronger in thin, retail-facing books and weaker in liquid ones. If the walk shows anything, split it by volume before concluding.
 4. If every cell is flat AND excluded at the frontier, that is three domains dead and it is time to put the theory in front of the user (`theories propose-retirement`) rather than walk a fourth. Say so plainly; the v4 note already pre-committed to this.

DO NOT walk Commodities, Social, Transportation, Exotics or Education -- `cells.DOMAINS` does not bin them, so every row lands in `other|*`, the exact vocabulary v3 quarantined. Sports (3,274 series) and Entertainment (598) are mapped and unwalked; Crypto is mapped but is a cost trap (KXBTC15M alone is 5,491 candlestick fetches / ~20 min of 15-minute BTC markets that all land on the same ~58 days). Run `collect size` before committing to any of them.
