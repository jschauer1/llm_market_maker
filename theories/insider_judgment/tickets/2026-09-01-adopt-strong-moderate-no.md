---
title: Adopt the strong-moderate-no rule now that it is ready at v4
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: setup
status: done
closed: 2026-09-01
resolution: ANSWERED NO -- do not bump to v5, and do not fold the rule into the screen. The ticket's premise was superseded within hours of filing, by 5ce5558 ('docs: a sub-theory is maintained, not absorbed') and its CLAUDE.md section of the same name.

The ticket asked whether to adopt the NO-side rule into v4's decision procedure, on the reasoning that 'the slice re-weights ranking, it does not change what the screen bets'. That reasoning is now explicitly the wrong turn: a ready sub-theory is ALREADY the decision point for the rows its predicate matches. slices.ranking_segment routes a matching candidate to the slice's own score row and promote ranks it there, so THE BET PLACED IS IDENTICAL EITHER WAY. There is nothing to promote a sub-theory to.

Absorbing would have cost two irrecoverable things: the complement (-2.51 net) stops accruing, so nobody could check again whether the slice is still the part that works -- a subset that quietly stops working then looks exactly like a healthy theory; and registered_at / mined_from_run_ids collapse into ordinary parent rows, taking the out-of-sample discipline that makes the slice's number mean anything.

VERIFIED AT CLOSE (2026-09-01): `slices report insider_judgment` gives strong-moderate-no ready=True, n=328, 90 event clusters, 44 settlement days, +3.76 net, 314 of it backtested, pooled v1-v4. It is already ranking its own candidates on its own record. No action needed.

WORTH KNOWING, because it is why this ticket looked urgent: the same peer session found the reader was lying. `slices report` defaulted to pool='version' and returned ready=False, oos n=1 -- wrong by a factor of 328 -- a leftover from when `breaking` was the default bump kind. Fixed in c59d6f8 (default is now pool='chain'). A session that saw a slice it knew was proven reported as not-ready would reasonably conclude the sub-theory mechanism was broken and reach for folding the rule into the parent. So the tool bug plausibly CAUSED the temptation this ticket records. If a future session feels that same pull, check what `slices report` is actually saying first.

The two legitimate exits for a sub-theory, neither of which applies here: orphaned evidence is fixed by relinking the version chain (theories.reclassify_bump -- already done for v1-v4, which is what made this slice ready), and a sub-theory whose parent is RETIRED is proposed as its own theory at n=0 citing the subset as founding evidence.
---
The sub-theory is READY at the current version: n=325, 89 event clusters, 43 settlement days, +4.37 net, complement -2.51. It got there when the 2026-08-31 ruling relinked v1-v4 into one evidence chain, which resolved the orphan escalation. Open question this ticket exists for: v4's decision procedure does NOT contain the NO-side rule -- the slice re-weights ranking, it does not change what the screen bets. Decide whether to bump to v5 adopting the rule into the procedure (kind=continues, so the evidence carries), and say in THEORY.md what changed. See theories/insider_bias/insider_judgment/RUNBOOK.md section Sub-theories.
