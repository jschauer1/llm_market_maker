# Round 5 — labels by session 78, committed BEFORE any second reading

> **Converged.** Session 18 read the sample blind, locked its calls before
> opening this file, and independently returned 7. Adjudicating the three
> disagreements landed on **exactly these six — 12%**. 18 conceded [13]
> (an earthquake is a marked arrival, a point process, not the
> level-crossing the threshold exclusion targets), conceded [40] vs [33]
> (the spec's criterion is "launches with *fixed dates*", so a scheduled
> NASA rotation and an indefinitely-slipping New Glenn split), and
> withdrew its unique call [7] `KXBERNIEENDORSE` after checking the
> siblings: 15 *different races*, five already resolved at 1.00, sum 7.41
> — not a selection at all. Two independent readings, one number.

Locked deliberately. Session 78 wrote the two structural rules under test
and is therefore a conflicted auditor; these labels are committed before a
blind second reader sees the sample, so the comparison is meaningful and
these cannot be quietly adjusted afterwards.

Judged against the spec's definition: a discrete, **unscheduled affirmative
event** by a deadline. Out of thesis = scheduled certainty, continuous or
count threshold, or multi-destination (hazard x conditional selection).

## Misclassified — kept by the screen, not the thesis (6)

| # | ticker | why it is not the thesis | flag | sibs | price sum |
|---|---|---|---|---|---|
| 4 | KXACTORSONNYCROCKETT-35-GLE | one actor plays Sonny Crockett; role named in the series ticker, not the rules text | False | 10 | 1.08 |
| 6 | KXANTHROPICBANKPUBLIC-28JAN01-ROTHX | needs the IPO to happen **and** this bank selected — hazard x conditional | False | 15 | 3.65 |
| 8 | KXBOND-30-JACO | "the **next** James Bond" — one role | False | 30 | 1.72 |
| 35 | KXOPENAIBANKPUBLIC-28JAN01-QATAX | same as 6 | False | 15 | 3.39 |
| 40 | KXSPCXLAUNCH-CREW13-26DEC01 | NASA crew rotation flies on a schedule; the question is the date, not the occurrence | False | 8 | 5.37 |
| 41 | KXSUPERBOWLHEADLINE-27-BAC | "**Who** will headline" — exactly one headliner | False | 54 | 3.64 |

**6 / 50 = 12%.** SE at n=50 on 12% is ~4.6pts.

## Judgment calls resolved as IN thesis, recorded so they can be disputed (2)

- **13 KXEARTHQUAKEM-26AUG-79** — a magnitude ladder looks like a threshold,
  but a large earthquake is a *point process*, not the level-crossing of a
  continuous variable that the spec's threshold exclusion targets. Sibling
  sum 5.08 confirms it is not a partition. Counted correct.
- **33 KXNEWGLENN-262-OCT** — the spec excludes "launches with fixed dates";
  New Glenn has no fixed date and slips repeatedly, and the 7 siblings
  summing 1.17 are a date ladder. Counted correct. Contrast 40, which is a
  scheduled NASA mission.

Counting both as misses instead gives 8/50 = 16%; the honest range is
**12%–16%**, and the bar is 10%.

## The finding that matters more than the rate

**Every one of the six misses has `mutually_exclusive = False`.** The flag
agreed with 98% of the regex's 2,687 existing multi-destination exclusions
— but that measured agreement on markets the regex *already caught*. On the
residue, which is the only place it was needed, it is False every time.

This is the same conditioning trap that produced `structural_arb`'s
all-false flag cache: a signal validated on the population where the old
method already worked says nothing about the population where it failed.

**The price-partition test fails for a separate and unfixable-looking
reason: genuinely exclusive events are not always priced like partitions.**
"Who will headline the Halftime Show" is exclusive by construction and its
54 legs sum to 3.64, because illiquid longshot legs have wide spreads and
mids that overstate. Only *tightly priced* partitions sum near 1. Loosening
the 1.05 threshold to catch them would swallow the date ladders the
shared-deadline exemption exists to protect.
