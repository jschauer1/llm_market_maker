---
title: A superseded endorsement at an old theory version keeps promoting to R1 forever
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-c0
author_lane: floor
author_context: Hit during the 2026-09-01 second floor: promote returned R1 on a position the same run had just re-judged as weak.
status: done
closed: 2026-09-01
resolution: Fixed with candidate (a), the ticket's own recommendation. promotion._superseded_by returns the row at the theory's CURRENT version that re-decided the same position; a match sends the stale fork to R6 naming its successor. Match is on the full position identity minus the version (theory, ticker, outcome, run_mode, lane), so a tier A/B replay or an exp/ row never suppresses a live position and the two sides of a ticker stay distinct. Absence of a successor is NOT supersession -- that is what separates (a) from the blunter (b), and the live numbers show why it mattered: 19,895 live unsettled rows sit behind their theory's current version, but only 656 have a real successor, and only 335 change rung (334 taker_flow v1 rows forked by the v1->v2 bump, plus opportunity 13663 itself). Evaluation order is preserved, so a rejected row still reports 'rejected at stage 2 -- control group'. Promotion key bumped to v4: docs/promotion-key.md gains a Supersession section, the R6 criteria row, and a changelog entry recording the 13663/109994 incident; promotion.KEY_VERSION mirrors it and tests/test_promotion.py holds the two together. Four tests pin the shape -- the incident itself (failed before the change, 'stale fork promoted R1'), plus three guards against over-suppression that must keep passing: no-successor stays promotable, a backtest row never supersedes a live one, and supersession is per outcome side. Suite 1364 green.
---
WHAT HAPPENED, CONCRETELY. Opportunity 13663 is KXPRESSSECANNOUNCE-26AUG-SEP08 NO at 0.85, recorded 2026-08-29 at insider_judgment v4, confidence=moderate, disposition=endorsed, edge_basis=prior (+2.0 placeholder). `cli promote 13663` today returns R1 RECOMMENDED, segment slice:strong-moderate-no, ranked_edge 2.46.

Today's floor re-ran the theory at v6 over the same board. The same market was re-judged, with fresh web research, and came back **weak**: Leavitt has departed and reporting says Trump may not name a replacement until after the midterms, i.e. the decision is UNMADE, which the analysis prompt lists explicitly as a bucket-lowering warning sign. That verdict recorded as opportunity **109994** -- v6, weak, screened, edge_basis=measured, -1.02 pts -- which promotes R6.

So the ledger now holds two live rows for one market, promoting to R1 and R6 simultaneously, and the R1 one is the stale one.

WHY IT HAPPENS. The position rollup keys on (theory_id, theory_version, kalshi_ticker, outcome). A version bump therefore does not supersede a position; it forks it. 13663 stopped receiving attempts the moment the theory left v4, so it is frozen at its last v4 interpretation -- and nothing ages it out, because promote's staleness checks are all about PRICE (today's ask, executability), never about whether the interpretation behind the row is still the current procedure's.

WHY IT IS WORSE THAN IT LOOKS. Three multipliers:
  1. It is silent. Both rows are legitimate records; nothing errors.
  2. It survives forever. 13663 will keep promoting R1 every session until the market settles, and the more versions the theory gains the more orphan rows accumulate behind it.
  3. It preferentially preserves ENDORSEMENTS. v5 deleted stage 6, the only path to disposition='endorsed'. So every endorsed row in the ledger is by construction stranded at v4 or earlier, at a version whose procedure no longer exists -- and those are exactly the rows most likely to clear R1.
And the frozen edge is a PRIOR placeholder (+2.0), while v6 rows carry measured edges. The stale row is claiming an unmeasured number the current procedure would not claim.

CANDIDATE FIXES -- not chosen here, this is a maintenance-lane design call.
  a. promote marks a position stale when its theory_id has a newer version AND a row for the same (ticker, outcome) exists at the current version, and drops it to R4/R6 with a reason naming the superseding row. Narrow, no schema change, and it only fires when there is a real replacement.
  b. Same, but without needing a superseding row: any position whose theory_version is behind the registry's current version is not R1-eligible. Simpler and blunter -- it would suppress rows whose market simply was not screened today, which may be wrong.
  c. Carry positions across continues-bumps so re-judging updates one row instead of forking. Correct-looking but much bigger: it changes what a position IS, and 'version' is load-bearing vocabulary (CLAUDE.md), so this rewrites how every existing row is read. Do not start here.

Recommend (a). Whichever is chosen, it needs a test pinning the 13663/109994 shape.

IMMEDIATE CONSEQUENCE, already handled: the 2026-09-01 second floor did NOT report 13663 as a bet, and said why in the report. Any session reading promote output without this context would have reported it.
