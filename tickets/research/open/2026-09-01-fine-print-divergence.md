---
title: rules_secondary narrows what the title promises, and almost nothing in this repo reads it
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found by following an outside claim (Kalshi settles off full terms, not the card summary) into the raw board payload; counts measured on the 2026-09-01 board.
status: open
---
MECHANISM. Kalshi settles off its full contract terms, not the summary
on the market card. `rules_primary` is the summary; `rules_secondary`
carries the timing, windowing and revision mechanics -- and it routinely
NARROWS or SHIFTS what the title and primary rule appear to promise.
A trader who reads the card and not the fine print is pricing a
different contract from the one that settles.

Who is on the other side: retail reading the title. Why it persists: the
fine print is a second field that the Kalshi UI de-emphasises and that
requires actually comparing two texts to notice; the divergence is
invisible on the price surface, so nothing propagates it.

WORKED EXAMPLES, from the 2026-09-01 board.

  KXNETFLIXRANKMOVIE-... -- THREE different dates in one market:
    title           : "...Top US Netflix Movie on Aug 31, 2026?"
    rules_primary   : "...#1 on the chart published on Sep 1, 2026..."
    rules_secondary : "The Netflix charts are updated on Tuesday...
                       The chart published on Sep 1, 2026 will be for
                       THE WEEK ENDING THE PREVIOUS SUNDAY."
  So the title's date is neither the chart date nor the measured week.

  KXAAAGASMIN-26DEC31-* (liquid) -- the window is restricted:
    title           : "Will average gas prices be below $2.00 by Dec 31, 2026?"
    rules_secondary : "This market only considers AAA prices posted from
                       Issuance (March 23, 2026) through December 31,
                       2026, inclusive; prices reported earlier [do not
                       count]."
  "By Dec 31" reads as "at any point"; the contract says "only since
  March 23". Any pre-Issuance touch of the strike is excluded.

MEASURED ON THE BOARD (105,104 markets):
    non-empty rules_secondary                    100,272  (95.4%)
    rules_secondary containing a timing/revision
      clause (week ending / the day before /
      published on / will close at / revis* /
      final value ...)                            12,806  (12.2%)
    a DATE in rules_secondary disjoint from every
      date in the title and rules_primary          2,977
      of those, liquid (vol>=500, spread<=0.07)       91

  BE HONEST ABOUT THAT 2,977: it is an UPPER BOUND from a crude regex
  and it has false positives -- AMAZONFTC-29DEC31 trips it on a 2023
  terms-amendment note, not a live divergence. The number to trust is
  the 91 liquid ones, and even those need eyeballing before anything is
  built. The real population is "material narrowing", which is a subset.

AND THE REPO BARELY READS THE FIELD. `grep -rn rules_secondary
--include=*.py .` returns TWO hits, both inside insider_judgment
(pipeline.py's MARKET_FIELDS and backtest_judged.py), both reaching into
`.raw`. It is NOT on the typed `tools.domain.Market` object at all, so
every consumer using the typed board sees only `rules_primary`.

  WORTH FLAGGING SEPARATELY: `theories/deadline_drift/screen.py` and
  `collect_settled.py` parse the STATED DEADLINE out of `rules_primary`
  alone. That theory's whole time anchor is the stated deadline, and its
  NOTES.md already records one painful correction about which anchor is
  sound. If a market's operative date lives in `rules_secondary`, that
  parse silently takes the wrong one. Not verified against its 70-series
  allowlist -- checking it is cheap and should happen before the hazard
  bins are trusted.

KALSHI POPULATION. 12,806 markets carry a timing/revision clause today;
the actionable subset is the liquid narrowing cases (91 by the crude
filter, fewer after review). Recurring families are the place to look,
because a divergence in a recurring series repeats every cycle: the
Netflix chart-week offset recurs weekly, forever.

WHAT WOULD KILL IT.
  - The market already prices the fine print. This is the real test:
    take settled markets WITH a narrowing clause and compare realized
    outcomes against the naive title reading. If the price tracked the
    contract rather than the title, there is no edge and this is just a
    correctness note for the repo (which would still be worth having).
  - The divergences are not directional. A clause that narrows the YES
    condition should bias one way; if the detected set is a mix of
    narrowings and broadenings with no net sign, there is nothing to bet
    even if the divergence is real. Classify direction, do not just
    detect difference.
  - The population is too small or too illiquid after honest filtering.
    91 liquid candidates board-wide is thin, and it may shrink a lot on
    review.
  - insider_judgment already harvests this. Its stage 5 reports
    rules/title divergences (six on the 2026-09-01 floor). Check the
    overlap before building: if that stage is already catching the
    material cases, this is a mechanical CHEAPENING of an existing
    judged step, not a new source of edge -- still valuable, different
    claim.

MECHANICAL FIRST, then judged. Detection is mechanical: date-set
disjointness, plus a phrase list for narrowing constructions ("only
considers", "week ending", "from Issuance", "posted from"). Direction
and materiality probably need a cheap judged pass over a few hundred
survivors -- which is fine, and is the correct division of labour: code
finds the candidates, judgment reads the two texts. Tier B if the judged
pass is in the decision path; tier A if the date-window subclass alone
turns out to be enough, which is worth checking first because it is the
cleanest sub-population.

SOURCE: OddsShopper, "Kalshi Market Rules: How A 90-Cent Yes Settled No"
and "Kalshi Vs Polymarket Rules: Same Event, Different Winners" -- the
claim that the card blurb is a summary and the exchange settles off full
terms; verified against raw board payloads this session.
