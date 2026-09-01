---
title: RUNBOOK still says v4 has no bet path to strong-moderate-no; promote disagrees
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: llm-market-identifier-cc
status: done
closed: 2026-09-01
resolution: Fixed in 5ce5558: the RUNBOOK's Sub-theories section now carries real numbers (n=328, 90 clusters, 44 days, +3.76 net, pooled v1-v4, 314 replayed), plus the 'maintained, not absorbed' rule and a historical note on how the orphan was actually resolved (reclassify_bump relinking the chain, not adoption).
---
Found by the 2026-09-01 floor. theories/insider_bias/insider_judgment/RUNBOOK.md, section 'Sub-theories', still carries:

  '**v4 carries no bet path to this slice** -- the v3->v4 bump was breaking, so v4 is not entitled to v3's evidence. promote raises it as *orphaned evidence* every session until the user rules on adoption. Report it; never quietly rank a v4 candidate on v3's record.'

That is no longer true. The 2026-08-31 ruling relinked v1-v4 into one evidence chain, and `promote --run live-2026-09-01` now ranks a v4 candidate directly on the slice with chain_versions=[1,2,3,4]:

  kalshi_ticker: KXPRESSSECANNOUNCE-26AUG-SEP08
  segment: slice:strong-moderate-no
  rank_inputs: n=90 clusters, calibration_edge_net=3.7568
  chain_versions: [1,2,3,4]

So the orphaned-evidence escalation the RUNBOOK mandates every session is resolved, and a floor session following the RUNBOOK literally would keep escalating a settled question to the user. Also stale in the same section: 'At v3 the slice is READY out of sample -- n=321, 89 event clusters, 43 settlement days, +4.31 net' -- current pooled figures are n=328, 90 clusters, +3.757 net.

Fix: rewrite that section against the relinking ruling, and check whether the same 'breaking bump' language appears in THEORY.md. Note this is adjacent to the open ticket 2026-09-01-adopt-strong-moderate-no (which asks whether to bump to v5 adopting the NO rule into the procedure) but is not the same question -- this one is purely that the doc contradicts the code.
