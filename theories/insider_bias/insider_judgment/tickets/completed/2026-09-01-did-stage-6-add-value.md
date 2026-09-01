---
title: Settle whether the removed final review actually added value
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: unknown
author_lane: theory
author_focus: insider_judgment
author_context: Filed while removing stage 6 at v5; the removal argument was structural, and this is the empirical question it deliberately left open.
status: done
closed: 2026-09-01
resolution: Permanently unanswerable as posed, and that is the answer rather than a deferral. interpretation_value is a comparison and its endorsed arm is frozen at 6 settled rows on ONE settlement day -- stage 6 was removed at v5, so no new endorsed row will ever exist, and ruling 14 says under 3 settlement days there is no usable error bar. Waiting grows only the rejected arm (251 still unsettled), which sharpens a number that must still be differenced against one day's board. Directionally stage 6 did look selective (endorsed 6/6 +14.81; rejected -10.05; slice-matching rejected 8/12 at -32.53 vs the slice's +3.76 baseline) but every measurable arm is inside its noise, t=-1.06 and -1.55. Unconfirmed, not disproven, and now unfalsifiable. The live successor is the ticket's own step 4 -- mine the 362 rejected rows' stage-6 rationales for a MECHANIZABLE predicate over recorded fields -- which does not need the endorsed arm and is the same shape as the open single-name-structural-gate ticket, so it is noted there rather than re-filed as a duplicate. Do not re-introduce stage 6 by hand.
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

---

## ANSWERED 2026-09-01 (session llm-market-identifier-d8, theory lane): the question is permanently unanswerable as posed

Not "not yet" — **never**, and the reason is structural rather than a
matter of waiting.

### The cohort today

    ALL interpreted v2-v4 live rows (the frozen cohort):
      endorsed (stage 6 said yes)   n=  6  days=1   6/6    net +14.81   SE undefined
      rejected (stage 6 said no)    n=111  days=8   86/111 net -10.05   SE  9.52

    RESTRICTED to slice-matching rows (outcome=no, strong/moderate) --
    the only subset where the veto changed a bet:
      endorsed & slice-matching     n=  4  days=1   4/4    net +17.52   SE undefined
      rejected & slice-matching     n= 12  days=4   8/12   net -32.53   SE 20.95

    slice baseline: +3.76 net over 90 clusters / 44 settlement days

### Why waiting cannot fix it

The ticket's step 1 says "wait for the remaining unsettled rejected rows
to settle, then recompute `interpretation_value`". 251 rejected rows are
still unsettled, so **that arm will grow.** The endorsed arm will not.

**Stage 6 was removed at v5, so no new `endorsed` row will ever be
created.** The endorsed cohort is frozen at 12 rows, 6 settled, on
**one settlement day**. Ruling 14 says a calibration figure spanning
fewer than three settlement days carries no usable error bar — so the
endorsed arm has no error bar now and cannot acquire one, however long
anybody waits. `interpretation_value` is a *comparison*, and one of its
two arms is permanently unmeasurable.

Growing the rejected side to 362 settled rows would sharpen a number
that still has to be differenced against 6 rows on a single day. That is
not a test.

### What the data does say, at the strength it earns

Directionally, stage 6 looks like it was selecting on *something*: its
endorsed rows went 6/6, its rejections ran −10.05, and among
slice-matching rows the ones it vetoed went 8/12 for −32.53 against a
slice baseline of +3.76. Every one of those is inside its own noise
(t = −1.06 and −1.55 on the two measurable arms), and the endorsed side
is a single day's board.

So: **unconfirmed, not disproven — and now unfalsifiable.** The ticket
was right that v5's removal was structural rather than measured, and
right that the data pointed the other way. It just cannot be settled
this way.

### The part that IS still live, and it is the ticket's own step 4

> "If it holds up at a size that can carry it, the answer is NOT to
> reinstate a session veto. It is to find what stage 6 was reading —
> rules divergence against the chosen side, sibling coherence,
> resolution-source timing — and express it as a recorded field, a gate
> rule, or a registered slice predicate."

That path does not depend on the endorsed arm at all. The **362 rejected
rows carry stage 6's own rationales**, and those are a written record of
what a price-aware reader objected to. Mining them for a *mechanizable*
predicate — one expressible over recorded fields — is a real piece of
work with a real payoff, and it is the correct successor to this ticket.

**Closing this ticket and not re-filing the mining idea as a duplicate:**
it belongs with the `single-name-structural-gate` ticket, which is the
same shape (find a structural, mechanical proxy for what judgment was
doing) and is already open.

**Do not re-introduce stage 6 by hand.** That guidance from the original
ticket stands and is strengthened: there is now no way to demonstrate it
helped, so reinstating it would be adding an unmeasurable veto to a
theory whose one proven result is measured.
