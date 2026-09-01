---
title: settlement_sources is a free published field on every event and no cell axis uses it
lane: theory
theory: calibration_harvest
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found while inspecting raw board payloads in the find-theories lane; this theory owns the cell grid so it is filed here rather than as a new theory.
status: done
closed: 2026-09-01
resolution: Cheap check run 2026-09-01 and recorded in the ticket: 41.2% ticker coverage, structurally so (the tier-A populations came through list_settled and were never snapshotted), and every one of 11 sources sits inside its own noise at 2-3 df. Not a slice -- underpowered rather than informative. Closing because the theory is now under_review with retirement proposed on the pre-registered kill criterion; if the user keeps it, re-open and re-run at ~15 settlement days. Query preserved in the ticket body.
---
THE FIELD. Kalshi's EVENT envelope carries `settlement_sources` -- the
named agency or publication a market resolves against. It is already on
the board (the envelope has been on every market since 09a66f7) and
nothing in this repo reads it.

Counts on the 2026-09-01 board (105,104 markets), by source name:

    46,440  ESPN
    20,208  Fox Sports
    17,912  the Governing League
    15,097  Kalshi using information originating from the NCAA
     4,102  CF Benchmarks
     4,012  official election authority responsible for certifying...
     3,747  The Wall Street Journal
     3,468  Reuters
     2,967  Cycling Weekly / Union Cycliste Internationale
     2,931  ABC
     2,876  the Associated Press
     2,867  AP College Football Rankings
     2,757  CNN

WHY IT BELONGS TO THIS THEORY. This theory's whole instrument is the
signed calibration cell, currently (domain x horizon x price). Resolution
source is a fourth axis of exactly the same kind: a published field, free
to read, exact, no model, and stable over a market's life. It is also a
plausible MECHANISM rather than a random cut -- how a source behaves is
the thing that decides marginal resolutions. A source that revises, that
publishes late, that has a definition diverging from the market's title,
or that Kalshi restates ("Kalshi using information originating from the
NCAA" is a restatement, not a primary source) should show a different
calibration signature from a clean primary feed like CF Benchmarks.

CHEAP FIRST CHECK, on rows already recorded -- no new run, no new spend:
this theory has 14,436 rows / 3,106 settled. Label them by
`settlement_sources` from the stored snapshot payload and read
calibration per source. If the spread across sources is flat, drop it;
if not, it is a pre-registerable slice axis.

DO IT AS A REGISTERED SLICE, NOT A NEW CELL DIMENSION, at least first.
Adding an axis to the cell grid multiplies the cells and this theory's
binding constraint is already settlement DAYS per cell, not rows -- 0 of
21 cells were measurable on the 2026-09-01 floor, best at 4 days against
a bar of 8. Splitting the grid four ways makes that strictly worse. A
slice over the existing population re-weights without subdividing the
grid, and it carries the out-of-sample bookkeeping automatically.

CAVEATS.
  - The field is free text and messy: "For example, Google Finance"
    (3,452) is clearly a parse artifact of a longer sentence, and
    "Cycling Weekly" / "Union Cycliste Internationale" appear as
    separate entries at identical counts, i.e. one event listing two.
    Normalise before grouping, and expect a long tail.
  - Sport dominates (ESPN + Fox Sports + Governing League + NCAA is
    ~95k of 105k markets), so a naive source cut is largely a
    sport/non-sport cut wearing a different name. Control for domain
    before claiming the source axis carries anything of its own -- this
    is the composition trap this theory already hit once on the horizon
    gradient (38% of the one-week step was which series sat on each
    side; see the idea-2 revisit angle).

SEQUENCING: this is well behind the open double-run defect
(tickets/maintenance/open/2026-09-01-calharvest-double-run-contaminates-
other-cells.md), which corrupts the `other|*` cells every day it runs.
Fix that first -- a source axis read off contaminated cells inherits the
contamination.

SOURCE: own board inspection, 2026-09-01.

---

## RAN THE CHEAP FIRST CHECK, 2026-09-01 (session llm-market-identifier-d8, theory lane)

The ticket asked for exactly this and it cost nothing, so it is done.
**The answer is neither "flat" nor "signal" — it is "this corpus cannot
answer the question", and the reason is the one that binds everything
else in this theory: settlement days.**

### Coverage

Joined every settled `calibration_harvest` attempt (11,830 rows, 7,293
distinct tickers) to `settlement_sources` from the stored snapshot
`event_json`. **41.2% ticker coverage (3,006 of 7,293).**

That number is structural, not a gap to fill. `market_snapshots` holds
markets seen on a *live board*; the two tier-A collection populations
(weather 3,267 obs / 59 days, politics 1,541 / 47 days) were fetched
through `list_settled` and were **never snapshotted**, so they carry no
event envelope. The source axis is therefore readable *only* on the
forward corpus — and the forward corpus is four settlement days old.

### What it looks like, day-clustered

    settlement source                n   day    ask   real     net  daySE      t
    DAZN                            60     3  0.848  0.567  -46.03  25.40  -1.81
    MLB                            216     4  0.831  0.778  -26.45  19.42  -1.36
    MLS                             70     3  0.767  0.657  -24.36  11.01  -2.21
    WTA                            242     4  0.800  0.793  -23.92  15.85  -1.51
    ESPN                          2502     4  0.838  0.815  -13.55  10.95  -1.24
    the Governing League           608     4  0.828  0.796   -8.78   4.12  -2.13
    FIFA                           146     3  0.848  0.795   -5.42   1.50  -3.63
    CF Benchmarks                  191     3  0.863  0.848   -5.05   6.71  -0.75
    Fox Sports                    1214     4  0.855  0.802   -3.55   2.21  -1.61
    ATP                            300     3  0.789  0.760   -2.70   3.00  -0.90
    Sofascore                       78     4  0.777  0.923  +13.10   6.34  +2.07

**Do not read this table as a result.** Every row spans 3-4 settlement
days, so each t has 2-3 degrees of freedom, where the two-sided 95%
critical value is 3.18-4.30, not 1.96. On that bar exactly one row
clears — FIFA at -3.63 — and it is one of eleven comparisons, so it
clears nothing after Holm. The apparent spread from -46 to +13 is what
eleven noisy four-day estimates look like; it is not evidence of a
source effect. This is the same error the 2026-08-30 ruling was made
about (a calibration figure under 3 settlement days carries no usable
error bar), one day above the floor rather than below it.

Sofascore's +13.10 is the one positive and it is **not** significant
(t=2.07 at 3 df). Recorded here so nobody rediscovers it in a fortnight
and thinks it was overlooked.

### What is real in the table, and it is not about sources

The corpus is dominated by **sports** (ESPN 2,502 rows, Fox Sports
1,214, plus MLB/ATP/WTA/FIFA/MLS/DAZN). Those are the quarantined
`other|*` live rows seen through a different lens: the theory has been
screening a mostly-sports board and labelling it `other`. So
calibration_harvest's -2.87 headline is, to a first approximation, a
**sports-favorite** number, and the theory has never had a sports cell
to put it in. That is an argument for walking Sports as a domain, not
for a source slice.

### Verdict: do not register a slice yet, and here is what would change that

The ticket's own instruction was "if the spread across sources is flat,
drop it; if not, it is a pre-registerable slice axis." Neither branch
fires, because the check is underpowered rather than informative. Do
**not** register a slice on this — a slice registered off a four-day
read is a pre-registration of noise, and its `mined_from_run_ids` would
poison the very rows it needs to prove itself on.

**Re-run this check once the forward corpus clears ~15 settlement days**
(one line: the query is in this ticket's git history at this commit).
The ticket's core argument still stands and is untouched by the above —
resolution source is a published field, free, exact, no model, stable
over a market's life, and a plausible mechanism rather than a random
cut. It is a good idea waiting on calendar time, like everything else
here.

**One concrete thing worth doing before then**, and it is cheap: have
`price()` stamp the settlement source into `extra_json` alongside the
cell key. Precedent is exact — v2 added the cell key to `extra_json` for
this same reason and recorded it as *not* a decision change, since
nothing decides on it. Today the axis is only reachable by a snapshot
join that covers 41% of tickers and depends on dedup-on-write having
kept an envelope; stamped at attempt time it is 100% and permanent.
"Save as much as you can, while you can" — the source is on the board
today and the join may not be there later.
