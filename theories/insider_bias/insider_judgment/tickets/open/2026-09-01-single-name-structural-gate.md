---
title: Single-name vs broad-based may be a free structural proxy for 'is there an informed group here'
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found while reading outside literature in the find-theories lane; not acted on because another session holds insider_bias work.
status: open
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
