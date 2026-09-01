---
title: Adopt the strong-moderate-no rule now that it is ready at v4
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: setup
status: done
closed: 2026-09-01
resolution: No change needed - this is the anti-pattern. Ruled 2026-09-01: a sub-theory is maintained, not absorbed. The slice being READY at v4 IS the mechanism working: ranking_segment already routes a matching candidate to the slice's own score row and promote ranks it there, so the bet placed is identical whether or not the rule sits in the screen. Folding it in would buy nothing and cost the complement (no way to check the subset is still the part that works) and the out-of-sample split that makes the number trustworthy. There is nothing to promote a sub-theory to. See CLAUDE.md 'A sub-theory is maintained, not absorbed'.
---
The sub-theory is READY at the current version: n=325, 89 event clusters, 43 settlement days, +4.37 net, complement -2.51. It got there when the 2026-08-31 ruling relinked v1-v4 into one evidence chain, which resolved the orphan escalation. Open question this ticket exists for: v4's decision procedure does NOT contain the NO-side rule -- the slice re-weights ranking, it does not change what the screen bets. Decide whether to bump to v5 adopting the rule into the procedure (kind=continues, so the evidence carries), and say in THEORY.md what changed. See theories/insider_bias/insider_judgment/RUNBOOK.md section Sub-theories.
