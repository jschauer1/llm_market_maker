---
title: Aggregation gap: many small markets sum to more than the one aggregate market pricing the same quantity
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found by surveying the 2026-09-01 board for cross-event structure; measured on that board before filing.
status: open
---
MECHANISM. When Kalshi prices one quantity BOTH as many small
independent markets AND as a single aggregate market, the small markets
each carry their own longshot premium and spread markup, and nothing
arbitrages ACROSS events -- so their sum drifts above the aggregate.
Who is on the other side: retail takers hitting individual district
races / individual team-strike ladders one at a time, where each looks
like a standalone bet. Why it persists: reconciling the two sides
requires simultaneously quoting 7-544 legs in DIFFERENT Kalshi events,
which no maker does and no public bot appears to.

THIS IS THE SUCCESSOR idea 8 (smile-smoothing, dead) EXPLICITLY ASKED
FOR. Its revisit_angle route (2): "CROSS-EVENT, NOT WITHIN-EVENT -- the
within-event channel is closed by construction, so the only place
sibling inconsistency could survive is ladders on the SAME UNDERLYING IN
DIFFERENT EVENTS; that is a different theory needing its own
pre-registration." That is this. It also respects idea 8's generalizable
warning (anything BETWEEN SIBLINGS OF ONE EVENT finds nothing), because
every relation here spans events.

MEASURED ON THE 2026-09-01 BOARD, BEFORE FILING. Two independent
instances, same sign.

(1) NFL SEASON WIN TOTALS -- an exact conservation law. KXNFLWINS lists
32 teams as 32 separate EVENTS, each a complete 1..17 strike ladder
("wins at least N games"), so E[wins] = sum_N P(wins>=N) is exact, not
an approximation. Every game produces exactly one win, so the identity
is sum over 32 teams of E[wins] = 272 - ties.

    SUM yes_mid = 274.25   vs true <= 272      -> +2.25 wins (+0.83%)
    SUM yes_ask = 284.47 ; SUM yes_bid = 264.03
    544 legs, 374 with volume >= 100, 0 monotonicity violations

  HONEST READING: NOT SIGNIFICANT. The bid/ask band [264.0, 284.5]
  straddles 272 comfortably, so this is a sign, not a violation. Both
  riskless baskets fail at executable prices: all-NO costs 279.96
  against a 272 floor (-7.96, -11.89 after ~$3.93 of fees); all-YES
  costs 284.47 against a 272 ceiling. Reported because it is the same
  direction as (2), not as evidence on its own.

(2) HOUSE SEATS -- two independently quoted markets on ONE number, and
this is the stronger case. KXHOUSEWINSTATE-<ST>D prices a distribution
over Democratic seats in a state; KXHOUSERACE prices each district
separately. Restricting to the 5 states with COMPLETE district coverage
(AL 7/7, GA 14/14, LA 6/6, SC 7/7, TN 9/9 -- the incomplete states show
exactly the negative gaps that missing districts predict, which is what
validates the method):

    gap = (sum of district P(Dem)) - (state market E[Dem seats])

    st  gap@mid  gap@worst-case
    AL   +0.30      +0.14
    GA   +0.31      -0.14
    LA   +0.21      +0.05
    SC   +0.40      +0.20
    TN   +0.38      +0.10
    mean +0.320 (5/5 positive)   +0.073 (4/5 positive)

  "Worst case" marks districts at BID and the state expectation at ASK
  -- the most adverse quoting assumption available. The sign survives it
  in 4 of 5 states. D/R pair sums are 0.992-1.005, so the district side
  is internally consistent.

KALSHI POPULATION. Live today: KXNFLWINS 544 legs / 32 events; KXHOUSERACE
704 markets over ~50 states, KXHOUSEWINSTATE 84 over 14. Further families
where the same identity is available and UNCHECKED: KXNBAWINS (30 events),
KXNCAAFWINS (73), KXMLB/NHL equivalents, KXHOUSEWINSTATE vs a national
seat-count market, KXMIDTERMMOV (628) vs KXHOUSERACE.

WHAT WOULD KILL IT.
  - The gap's sign is not stable across boards -- re-measure on stored
    snapshots (tools/snapshot.py keeps complete raw payloads, so this
    replays for free, tier A) and on new boards. A gap that flips sign
    is spread noise.
  - The gap does not exceed fees plus the cost of holding both legs. This
    is the LIKELY killer and must be tested first: +0.07 to +0.32 seats
    spread over 12-28 legs is a few cents a leg, against fees on every
    leg and a >1-year hold to Nov 2026 (KXHOUSERACE medDTC 428 days).
    Capital lockup is a real cost -- see deadline_drift's capital-asymmetry
    note.
  - The aggregate market, not the small markets, is the biased side. The
    identity says they disagree; it does not say WHICH is wrong. Settling
    that needs settled outcomes, not more quotes.

MECHANICAL, tier A. No LLB anywhere: ticker patterns give the grouping,
the identity comes from the domain's own rules (one win per game; seats
per delegation), arithmetic gives the gap. edge_basis="model". Replays
over stored snapshots for free and scales to every family that has an
aggregate twin.

IMPORTANT SCOPE LIMIT FOUND WHILE MEASURING. E[wins] is only recoverable
where the strike ladder SPANS THE FULL SUPPORT. NFL qualifies (1..17 for
a 17-game season). NBA and NCAAF do NOT -- KXNBAWINS tops out at 10-12
strikes for an 82-game season, so sum P(>=N) is a truncated lower bound,
not an expectation, and the naive sums (158.87 for NBA) are meaningless.
Any implementation must verify ladder completeness per family before
computing anything, or it will manufacture enormous fake gaps.

RELATION TO EXISTING WORK, checked before filing:
  - idea 4 / structural_arb: groups strictly BY event_ticker -- this
    population is invisible to it by construction. Sibling theory, not a
    slice.
  - idea 13 / implication-graph: LLM-proposed logical implications
    between non-sibling markets. Overlapping ambition, different
    instrument -- this needs no model, and it is an EQUALITY ON
    EXPECTATIONS derived from domain rules rather than an implication
    between binaries. Build this one first: it is the part of idea 13
    that needs no judgment and no provenance obligations.
  - ideas 8 and 21 (both dead): within-event. This is their cross-event
    successor.

SOURCE: own board measurement, 2026-09-01 board (105,104 markets),
scripts in the session scratchpad; mechanism is standard
favorite-longshot / per-market markup accumulation.
