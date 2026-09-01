---
title: Single-name vs broad-based may be a free structural proxy for 'is there an informed group here'
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found while reading outside literature in the find-theories lane; not acted on because another session holds insider_bias work.
status: done
closed: 2026-09-01
resolution: Tested 2026-09-01; see NOTES.md same date. The ticket's binding condition ('do NOT write a prompt -- if the rule cannot be written mechanically the finding does not apply') is what decided it, in two parts.

TITLES WERE NOT STORED, and that is fixable: only 381 of 1,770 bucketed settled rows (21.5%) have a title reachable from market_snapshots, and they are the live ones -- the backtest rows carrying the evidence were fetched by the replay and never snapshotted. backtest_judged.py HAD the title (it writes one into every judging payload) and did not persist it: the same defect as calibration_harvest's collector, found the same day. It IS recoverable without re-judging -- the payloads are still on disk under backtests/*/batch_*.payload.json with title, rules_primary, event_ticker and every market ticker, and an index built from them covers 2,571 of 4,275 opportunities (60.1%). Ticketed separately as backfill-titles-from-judging-payloads.

BUT EVEN WITH TITLES the rule cannot be mechanical: 'does this name one entity or a broad field' is reading comprehension, which CLAUDE.md routes to a model and this ticket forbids. A hand-written classification of 261 series tickers is a prompt with extra steps, fitted on the rows it would be scored on.

SO I TESTED THE MECHANICAL THING THAT IS FREE -- sibling count per event, 'one named entity' vs 'one of N', structure rather than comprehension. It does NOT separate. All bucketed rows: 1 sibling +1.95 (t 0.66), 2-3 -3.33, 4-8 -1.33, 9+ -2.99. Slice rows: +6.49 / -1.95 / +7.98 / +3.45 -- ordering scrambles, nothing past 2 SE except a middle cell with no story. Unconfirmed, not disproven; NO slice registered, because registering this would be pre-registering noise.

LIMITATION that weakens my own test and should be fixed by whoever retries: the count is len(event['markets']) from the judging payload, which is built from post-screen survivors, so it counts SURVIVING markets per event rather than the event's true size. The real count is free on the board's event envelope -- use that.

Also inherits the live successor of did-stage-6-add-value (closed same day): mine the 362 stage-6-rejected rows' rationales for a mechanizable predicate. Same shape as this ticket -- a structural, free proxy for what judgment was doing -- and the rationales are a written record of what a price-aware reader objected to.
---
NOT URGENT, and filed from another lane -- a session was working
insider_bias when this surfaced, so it is written down rather than
acted on.

THE FINDING. "Adverse Selection in Prediction Markets: Evidence from
Kalshi" (Stanford Law School Legal Aggregate, 2026-04-21), over 41.6
million trades using adapted Kyle's lambda, a Glosten-Harris
decomposition and a VPIN-style toxicity metric, reports that
**SINGLE-NAME markets show notably higher informed price impact than
BROAD-BASED markets** -- and that market makers earn about twice as much
per contract in single-name venues despite only modestly wider effective
spreads.

WHY THAT MATTERS HERE. "Higher informed price impact" is a
microstructure measurement of exactly this theory's central question:
is there someone trading who already knows? Single-name vs broad-based
is a STRUCTURAL property -- one named entity versus an index, an
aggregate, or a many-people count -- derivable from the ticker and
title, with no reading comprehension required.

CLAUDE.md's division of labour ranks instruments for structural
questions: data, then code, then a structural gate, then outcome
judgment. If this split carries signal on this theory's population, it
is a free, exact, instant filter sitting above a stage that currently
costs tokens per candidate. Note gate.py ALREADY encodes a closely
related intuition from the other direction -- its
"aggregate-of-many-independent-people" exclusion removed 31 events on
the 2026-09-01 floor, and "aggregate of many people" is close to a
hand-rolled definition of broad-based. So this may be less a new gate
than external evidence that an existing one is pointed the right way,
and possibly a reason to widen it.

WHAT TO ACTUALLY CHECK, and it is cheap:
  1. Label this theory's settled rows single-name / broad-based by a
     ticker-and-title rule. Do NOT write a prompt for it -- if the rule
     cannot be written mechanically the finding does not apply, because
     the whole value is that it is free.
  2. Compare realized calibration edge across the two groups on rows
     ALREADY RECORDED. No new judging spend, no new run.
  3. If single-name is where the edge lives, the candidate change is a
     stage-1 population filter, not a new prompt -- which would bump the
     version (a gate change is a decision-path change) and should be
     pre-registered as a slice first if it is expressible over recorded
     fields.

CAVEAT WORTH TAKING SERIOUSLY. The paper measures informed PRICE IMPACT,
which is not the same as this theory's thesis that a specific group
knows an OUTCOME in advance. Higher price impact can equally mean
"single-name books are thin, so any order moves them." Check the spread
and depth confound before believing the mechanism -- the paper itself
notes single-name spreads are only modestly wider, which cuts against
the pure-thinness reading but does not rule it out.

RELATED: filed the same session,
tickets/research/open/2026-09-01-kalshi-taker-flow-toxicity.md, which
covers the same paper's flow-toxicity result and the capability finding
behind it -- Kalshi's public trades endpoint exposes per-trade taker
side, unauthenticated, retained after settlement.

SOURCE: https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/
