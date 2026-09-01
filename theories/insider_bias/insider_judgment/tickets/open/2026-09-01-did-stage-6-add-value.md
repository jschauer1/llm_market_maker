---
title: Settle whether the removed final review actually added value
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: unknown
author_lane: theory
author_focus: insider_judgment
author_context: Filed while removing stage 6 at v5; the removal argument was structural, and this is the empirical question it deliberately left open.
status: open
---
v5 removed stage 6 (the main session's price-aware final review) on a STRUCTURAL argument: it was never part of the procedure that generated any of this theory's 3,759 backtest rows, and it was rejecting 72 of the 79 live rows the strong-moderate-no slice's record entitled, each landing on R6 and so unbettable.

It was NOT removed because it was measured and found harmful. The opposite, weakly: on settled live rows its endorsed cohort went 6/6 at +14.81 net, against -8.06 for its 109 settled rejections. On slice-matching rows, 4 endorsed went 4/4 (+18.5 gross) and 11 rejected went 63.6% (-25.4 gross).

That is n=6 over 2 event clusters. It clears no gate in this repo -- the endorsed cohort cannot reach even R3's three-day floor -- so it is unconfirmed, not evidence. But it points the wrong way for the change that was made, and it deserves an answer rather than being quietly dropped.

The data to answer it is preserved and will not grow: the 456 interpreted live rows (9 endorsed, 447 rejected) at v2-v4 stay exactly as recorded. What to do:

1. Wait for the remaining unsettled rejected rows to settle, then recompute score.interpretation_value on the frozen v2-v4 cohort. The 447 rejections are the large side and will carry the power.
2. Compare like with like: restrict to slice-matching rows (outcome='no', confidence in strong/moderate) so the comparison is not confounded by stage 6 correctly rejecting weak/YES rows the slice would never have bet anyway. That subset is the only one where the removal changed a bet.
3. Watch for the survivorship trap. Stage 6 rejected 91% of slice rows; if it was selecting on something real, the endorsed cohort should keep beating the slice's own +3.76 baseline out of sample, not merely beat the rejections.
4. If it holds up at a size that can carry it, the answer is NOT to reinstate a session veto. It is to find what stage 6 was reading -- rules divergence against the chosen side, sibling coherence, resolution-source timing -- and express it as a recorded field, a gate rule, or a registered slice predicate. That is mechanizable and testable; a session's felt sense is neither.

Do not re-introduce stage 6 by hand in the meantime. Endorsing this theory's rows manually buys no different bet (key v3's R4 gate reads the bucket, not the disposition) and fabricates a control group that measures nothing.
