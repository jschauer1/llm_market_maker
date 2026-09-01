---
title: Fixed-k elimination families are in the population and no detector catches them
lane: theory
theory: deadline_drift
created: 2026-09-01
created_by: fleet-w1-g1
author_lane: theory
author_focus: deadline_drift
author_context: Found on 2026-09-01 while inspecting v2's first live candidate set; recorded as fields rather than acted on, because the settled sample cannot yet distinguish the two shapes.
status: open
---
WHAT. KXAGTELIMINATION supplied 4 of v2's first 46 candidates and is not a per-subject hazard. It is 11 legs with 2 settled events paying SEVEN YES each -- a fixed-k elimination ('exactly 7 of these 11 acts go'), so the legs are negatively correlated and P(YES) is structurally ~k/n rather than a hazard rate. All three partition detectors miss it: hazard.partition_families requires exactly ONE winner; screen.partition_events requires siblings summing 0.90-1.05 and these sum to 6.67; the rules regex misses it because the shape is semantic, not syntactic.

WHY IT WAS NOT FIXED NOW. The obvious rule -- 'flag families whose settled events pay a tightly constrained number of winners' -- cannot be fitted on the evidence available. KXTRUMPSAY is the same superficial shape (34 legs, many YES per event) and IS genuinely independent: Trump saying 'Antifa' does not preclude 'Uranium'. The distinguishing feature is VARIANCE in the YES count across events (TRUMPSAY: 7,12,15,17,19,21 -- real spread; AGT: 7,7 -- n=2). Two events is not enough to fit that threshold, and guessing one now would bake a rule into the population that DD-1 is being measured on. This is precisely the failure the backlog's rule 0b names: choosing an inclusion rule after seeing which value helps.

WHAT TO DO, AND WHEN. Wait for more settled elimination events, then decide it on data. The inputs are already being recorded on every row -- extra_json carries event_legs and event_ask_sum, and hazard.py has the settled per-event YES counts -- so this is a query, not a new capture. Two candidate rules to test against each other: (a) variance of the per-event YES count below a threshold, over series with >= 4 settled events; (b) YES count per event tightly clustered relative to leg count (k/n stable across events). Check both against KXTRUMPSAY and KXBIGBROTHERELIMINATION as the labelled positive and negative.

IF IT MATTERS ENOUGH TO ACT ON, IT IS A v3 POPULATION CHANGE, NOT A SLICE. Excluding a contaminated family narrows the population; it does not re-weight the parent's output, which is what a slice does. That means a version bump and an explicit note that DD-1's population changed mid-test -- so weigh it against just letting DD-1 finish on the population it pre-registered. The honest default is to let DD-1 run and treat contamination as a known, quantified caveat: these families are a small minority of rows and are identifiable after the fact from the recorded fields.
