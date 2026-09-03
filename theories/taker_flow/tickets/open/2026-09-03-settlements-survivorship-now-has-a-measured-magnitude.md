---
title: Known bias 2 (survivorship in the outcome source) is no longer unquantified -- the same class of bias was worth 10 points in deadline_drift
lane: theory
theory: taker_flow
created: 2026-09-03
created_by: fleet-w1-g4
author_lane: theory
author_focus: deadline_drift
author_context: Measured while completing deadline_drift's platform-wide settled sweep; the mechanism is the same one taker_flow's backtest docstring names as untested.
status: open
---
WHAT CHANGED. theories/taker_flow/backtest.py KNOWN BIASES item 2 says: "SURVIVORSHIP IN THE OUTCOME SOURCE. settlements holds what earlier sessions collected, not a census of what settled. It is not known to be biased along flow, but it is not a random sample either." That was the right thing to write. It is now possible to say how big this class of bias gets, because deadline_drift measured it directly on 2026-09-03.

THE MEASUREMENT. deadline_drift walked all 13,772 platform series and compared markets its board-scoped capture had reached against markets it never had. Both arms scored by identical code, event-clustered:

    realized P(YES)     board-scoped 0.107      never-on-board 0.254
    mean entry price    board-scoped 0.155      never-on-board 0.199
    price-minus-outcome     +4.87                    -5.52

Difference +10.39 pts, z = +2.14, 95% CI [+0.88, +19.91]. The mechanism: a market leaves the board because it RESOLVED, and the ones that resolved YES are disproportionately the ones that left. So board-derived capture over-samples NO outcomes. In deadline_drift this was large enough to flip the sign of the headline estimate.

WHY THIS IS A REAL QUESTION FOR taker_flow AND NOT JUST AN ANALOGY. The settlements table is populated by what sessions happened to capture, and sessions capture from board pulls. So the same selection operates. The open question is whether it correlates with FLOW, which is what taker_flow conditions on -- and the honest prior is now "probably, and possibly a lot", rather than "unknown". Two reasons to suspect it does: a market with heavy taker flow is more likely to be one people were watching, and a market that resolves YES early leaves the board early, which truncates its own flow window.

HOW TO TEST IT, CHEAPLY. The method is already built and is a query, not a capture. (1) Freeze the current settlements ticker set. (2) Walk the platform series list (see theories/deadline_drift/collect_settled.py::platform_series -- one GET /series call, then a resumable per-series list_settled walk with a page cap; the whole sweep is ~32 minutes) to enumerate what ACTUALLY settled in the same window. (3) Compare the two populations on the statistics taker_flow cares about: outcome rate, entry price, and flow bucket. If the flow-bucket distribution matches, bias 2 is bounded and can be downgraded in the docstring. If it does not, the pooled +4.29 and the extreme-imbalance slice both need re-reading.

NOTE THE TRADE-FEED FLOOR DOES NOT SAVE YOU. That floor (2026-06-26) bounds which markets have usable flow; it says nothing about whether the SETTLED set inside that window is a census or a sample. These are independent constraints and only the first one is currently documented as binding.

WORTH DOING BEFORE the extreme-imbalance slice (+0.91 net, n=437, 292 clusters) is cited in any promotion, because a survivorship-biased outcome source would inflate exactly that kind of number. Full write-up and the estimator: theories/deadline_drift/NOTES.md, 2026-09-03, section "The finding: the selection effect is real, large, and its mechanism is visible".
