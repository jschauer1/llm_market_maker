---
title: settlement_sources is a free published field on every event and no cell axis uses it
lane: theory
theory: calibration_harvest
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found while inspecting raw board payloads in the find-theories lane; this theory owns the cell grid so it is filed here rather than as a new theory.
status: open
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
