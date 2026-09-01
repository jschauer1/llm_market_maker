---
title: Backfill spread/volume/open_interest for the 660 pre-fix series
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-86
status: open
---
URGENT AND TIME-BOXED. Pass 4 of the series-bias study cannot run until this is done, and it gets impossible rather than merely harder with time: it needs candlesticks, and Kalshi archives settled markets out of its public API ~60 days after close. Every day of delay permanently removes the front of the window.

WHAT HAPPENED. collect.py fetched candles carrying yes_bid_close, volume and open_interest, used the bid to choose the favorite side, and persisted only the derived ask. Pass 3 then could not tell a tradeable price from a one-sided book -- 23% of its observations sat at asks of 0.980-0.995 realizing 0.801, and the mention_family negative control fired on 5 of 11 because of it. Full account: studies/2026-08-29-series-bias-mining/STUDY.md, "Pass 3 result".

FIXED GOING FORWARD in 3cc5317: obs now has spread, volume, open_interest and spread_24h, and the sweep captures them. The migration was additive, so the ~660 series priced BEFORE that commit read NULL and are the backlog this ticket covers.

WHAT TO DO. Re-price the pre-3cc5317 series so their observations carry the liquidity fields. The rows are identified by:

    SELECT DISTINCT series_ticker FROM obs WHERE spread IS NULL

Two options, and the second is probably right:
 (a) clear those series' `progress` rows for phase 'prices' and re-run the sweep, which re-fetches and overwrites via INSERT OR REPLACE; or
 (b) write a `backfill` subcommand that walks only the NULL-spread rows. Same fetch cost, but it does not lose the already-correct ask/won values if a candle has since aged out -- on (a) a market whose candles are gone would drop out of the population entirely, silently shrinking it. Prefer (b) for that reason, and have it leave the row untouched rather than deleting when the fetch returns nothing.

Whichever, it is ~60k candle fetches at Kalshi's ~4-5/s, so hours. It MUST be incremental and resumable per CLAUDE.md's collection rule, and should report how many rows it could no longer backfill because the candles had aged out -- that number is the measure of what the original omission cost.

SEQUENCING against the other open ticket (2026-09-01-series-bias-sweep-finish): this one is more urgent. The unpriced series have not been fetched at all, so their data is equally perishable, but the already-priced ones represent work that will have to be thrown away entirely if their candles expire before the backfill runs. If you can only do one, do this.

---

## UPDATE 2026-09-01, same session: the tool is BUILT and RUNNING

Option (b) was taken, as this ticket recommended. `collect.py backfill`
exists and is running; what remains is letting it finish, not writing it.

    python studies/2026-08-29-series-bias-mining/collect.py backfill
    python studies/2026-08-29-series-bias-mining/collect.py status

Resumable and per-series atomic under `progress` phase `backfill`, so
re-running skips what is done. Roughly 70k candle fetches at Kalshi's
~4-5/s, i.e. several hours; it had reached 6 of 647 series when this note
was written.

**Do not run `prices` at the same time.** Both hit the same SQLite file
and the same rate limit; concurrent runs produce `database is locked`.
This backfill takes priority over `2026-09-01-series-bias-sweep-finish`
for the reason in this ticket's sequencing note.

**What it does, and the two properties that matter.** It never deletes: a
row whose candles have aged out upstream keeps its ask and simply reads
NULL, because dropping it would silently shrink the population. And it
self-checks -- `decision_prices` is now shared by `prices` and
`backfill`, and the backfill re-derives the ask through it and refuses to
write when the result disagrees with the stored value, so a spread can
never end up describing a different candle than the ask beside it.
Mismatches and aged-out rows are counted per series and in the final
line; **the aged-out count is the measure of what the original omission
cost**, so record it when the run finishes.

**Finishing this does not by itself enable pass 4** -- read STUDY.md's
"Correction to pass 4's filter" first. The filter this ticket's fields
feed was amended after the first backfilled rows arrived: a 1c spread is
not evidence of a tradeable book (the 0.99 favorites that caused pass 3's
artifact have exactly 1c spreads), and the candle's `volume` is
per-period, not the lifetime figure `insider_bias/screen.py` thresholds
at 500. Pass 4 tests `open_interest` instead, with volume reported
alongside.
