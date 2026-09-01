---
title: score report shows structural_arb returning +55% riskless, entirely from rows rejected as unfillable
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-af
author_lane: theory
author_focus: structural_arb
author_context: Found while reading structural_arb's score report at the start of a theory-lane session; it is a scoring-vocabulary question, so not mine to change.
status: open
---
WHAT IT LOOKS LIKE. python -m tools.cli score report structural_arb:

  all      : n=0 n_attempts=4 riskless_n=2 riskless_roi=+0.550 roi_all=+0.550
  rejected : n=0 n_attempts=4 riskless_n=2 riskless_roi=+0.550 roi_all=+0.550
  screened : empty          endorsed : empty

'all' and 'rejected' are identical because every row this theory has ever recorded was rejected. The +55% comes from two KXWTAGTOTAL findings whose OWN rationales read '~0.01 baskets fillable at riskless prices, ~$0.00 floor profit'.

NOT A RANKING BUG - checked. riskless_roi does not feed ranked_edge and promotion.py never reads it (its only 'riskless' mention is a reason string at promotion.py:176). This is a REPORTING hazard: a supervisor or a find-edge pass reading the headline sees a theory returning 55% riskless, and state's EVIDENCE line shows 'n 0' which hides it in the other direction.

THE PRECISE ISSUE, which is narrower than 'rejections count in roi_all'. That part is documented and deliberate (CLAUDE.md: rejections 'still count toward roi_all unconditionally'), and for a JUDGMENT theory it is exactly right - a rejected winner is real counterfactual information, i.e. the screen was right and the judgment cost you. structural_arb is different in kind: its rejection reason is 'not fillable at any size', so the counterfactual is IMPOSSIBLE rather than merely untaken. There was no position to take. Averaging that into a return number states something that could not have happened.

WHY IT IS FILED RATHER THAN FIXED. disposition, edge_basis and the riskless bucket are load-bearing vocabulary per CLAUDE.md, and changing what a recorded field means rewrites every row already written under the old meaning. This wants a decision, not a patch.

OPTIONS, roughly in order of how much they change:
 (a) Report only - leave the numbers alone and have score report annotate a riskless bucket whose rows are all rejected. Cheapest, no vocabulary change, kills the misleading headline.
 (b) A depth-rejected marker distinct from a judgment rejection, so 'could not be filled' and 'chose not to take' stop sharing a bucket. New name rather than a redefinition, which is the direction CLAUDE.md prefers, but it needs a migration for the 5 existing rows.
 (c) Exclude unfillable rows from riskless_roi entirely. Simplest headline, but it discards the record that the scan DID find them, which is the thing worth keeping.

Recommend (a) now and (b) if a second theory ever records an unfillable position. Related: structural_arb NOTES.md 2026-09-01, finding 5, which also explains why a snapshot replay must not record backtest-* rows for this theory - it would scale this exact artifact from n=2 upward.
