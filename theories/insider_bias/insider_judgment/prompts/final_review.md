<!--
insider_bias — stage 3 final review, performed by the main research session
itself rather than a subagent. Part of the versioned decision procedure:
editing this file changes what the theory decides and bumps the version.

Recorded per run in `judgment_runs` with the main session's model id, so a
later session can tell whether a change in results came from a change in
procedure or a change in model.
-->

> **RETIRED AT v5 (2026-09-01). This stage no longer runs.**
>
> This file is kept on disk because eleven `judgment_runs` rows name it as
> the prompt that judged, and a recorded prompt path that stops resolving
> turns a reproducibility record into a dangling pointer
> (`tests/test_conventions.py::test_every_recorded_prompt_path_still_resolves`).
> It is history, not procedure. **Do not run it.**
>
> Why it went: this stage was never part of the procedure that earned this
> theory's evidence. All 3,759 backtest rows -- including the 314
> out-of-sample rows behind the `strong-moderate-no` slice at +3.76 net --
> were generated without it, so the live path was running a six-stage
> procedure while the measured record described a five-stage one. Meanwhile
> its veto was rejecting 72 of the 79 live rows that slice's evidence
> entitled, each landing on R6 CONTROL and so unbettable forever. What a
> bucketed candidate is worth is now decided by its segment's measured
> record through the promotion key (key v3), which is the mechanism built
> for that call. See `THEORY.md` Version 5 and `RUNBOOK.md`.
>
> What this does NOT claim: that the stage was measured and found harmful.
> Its endorsed cohort settled 6/6 at +14.81 net, against -8.06 for its
> rejections -- suggestive, but n=6 over 2 event clusters clears no gate in
> this repo. The 456 interpreted live rows stay as recorded so that question
> stays askable; a ticket carries it.

# Stage 3 — final review

A subagent verdict is an **initial recommendation**, never a bet. Nothing from
this theory reaches the user as a suggested bet unless the main research
session reviews it and recommends it in its own right.

Work the whole batch at once. The defects this stage exists to catch are
visible only across candidates, which is precisely what a per-candidate
subagent cannot see.

## Per candidate

1. **Re-read the `rules_note`. Ask which *side* the divergence favours**, not
   merely that one exists. A rule broader than its title makes YES easier,
   which damages a NO favourite — and this screen picks NO on roughly 70% of
   candidates, so a divergence usually cuts against the leg the screen chose.
2. **Does the informed group know something the public does not?** A group
   that knows a fact already carried by the mainstream press supplies no
   asymmetry. The thesis is asymmetry, not expertise.
3. **Has the decision actually been made?** Nobody can know an unmade
   decision, however small the deciding group. "Considering", "in talks",
   "expected to" are unmade.
4. **Check siblings on a strike ladder.** Confirm the recommended legs are
   jointly coherent, and identify which survive *every* live reading of the
   rules. Recommend only those.
5. **Verify post-cutoff factual claims** a subagent relied on before relying
   on them yourself.
6. **Can the resolution source publish before close?**

## Authority

This stage may **lower** a bucket — the warning-sign rules apply to it exactly
as to the subagent — and may decline a candidate whose bucket implies positive
edge. It must **not raise** a bucket: the subagent judged blind to price and
this stage has not.

## Recording

`disposition='endorsed'` means *the main research model recommends this bet*,
not that arithmetic produced a positive number. Every opportunity carries
`extra_json.final_recommendation` with `decided_by`, `subagent_model`,
`subagent_bucket`, `final_bucket`, `action`, and a `note`.

**Name the deciding model when reporting to the user.** They are entitled to
know whose judgment they are being asked to act on.
