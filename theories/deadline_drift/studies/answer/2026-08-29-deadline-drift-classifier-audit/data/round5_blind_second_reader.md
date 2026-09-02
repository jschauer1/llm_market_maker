# Round 5 — independent blind pass by llm-market-identifier-18

Recorded BEFORE opening `data/round5_labels.md`. Definition applied: is
this a discrete **unscheduled affirmative event** by a deadline? Out of
thesis = scheduled certainty | continuous or count threshold |
multi-destination (hazard x conditional selection).

Every market in the sample is one the classifier KEPT, so "out of thesis"
= misclassification.

## Verdict: 7 of 50 out of thesis = **14%**

## Out-of-thesis calls (7)

| # | ticker | reason |
|---|---|---|
| 4 | `KXACTORSONNYCROCKETT-35-GLE` | multi-destination — one role (Sonny Crockett), one actor |
| 6 | `KXANTHROPICBANKPUBLIC-28JAN01-ROTHX` | multi-destination — which bank leads the IPO |
| 7 | `KXBERNIEENDORSE-26NOV03-JTUR` | multi-destination — which candidate Sanders endorses in one race |
| 8 | `KXBOND-30-JACO` | multi-destination — one role (James Bond), one actor |
| 13 | `KXEARTHQUAKEM-26AUG-79` | threshold — magnitude ladder; max magnitude crossing 7.9 is a level-crossing process, vol-crossing's math |
| 35 | `KXOPENAIBANKPUBLIC-28JAN01-QATAX` | multi-destination — which bank leads the IPO |
| 41 | `KXSUPERBOWLHEADLINE-27-BAC` | multi-destination — one headliner |

## In-thesis (43)

1, 2, 3, 5, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40, 42, 43, 44,
45, 46, 47, 48, 49, 50

## Borderline calls, flagged in advance

These are where I expect disagreement, and I want them on record as
genuinely uncertain rather than reconstructed as confident after seeing
the other labels:

- **[30] `KXMOVIECAST-XMAN29-KEL` — called IN**, deliberately splitting it
  from [4] and [8]. Being cast *in a film* admits many actors
  simultaneously; being cast *as Sonny Crockett* or *as James Bond* is one
  role, one person. The distinction is whether the branches are mutually
  exclusive, not whether the word "cast" appears.
- **[33] `KXNEWGLENN` and [40] `KXSPCXLAUNCH-CREW13` — both called IN.**
  The spec names "launches with fixed dates" as scheduled certainties, and
  Crew-13 is a scheduled NASA rotation. But slip *is* the question at a
  deadline, which is a hazard. Decided consistently rather than splitting
  them; if either is out, both are.
- **[23] `KXJUDGMENT-NPS29` — called IN.** A SCOTUS merits disposition is
  unscheduled, but the market is about which way it goes, not merely that
  it happens. Two-outcome branch, not a many-way selection, so I kept it.
- **[43] `KXTRAVELDOWNGRADE-27JAN01-RUS` — called IN.** "Level 3 or lower"
  is ordinal, but the resolving act is one discrete administrative
  publication.
- **[46] `KXTRUMPSAYCOMPANY-26SEP01-MU` — called IN.** A discrete
  utterance by a deadline. Note `insider_judgment` excludes the mention
  family as aggregate-of-many, but that is *that* theory's exclusion and
  not `deadline-drift`'s.

## Prediction, recorded before comparison

Their stated bar is 10% and they say their number is above it. Round 4
measured 16% on n=50. At n=50 the SE on a ~15% rate is about 5 points, so
14% and 16% are the same number. **My expectation: the structural signals
are not a demonstrated improvement, and this sample cannot show one.**

---

# Adjudication, written AFTER reading `round5_labels.md`

Their six: 4, 6, 8, 35, 40, 41. Mine: 4, 6, 7, 8, 13, 35, 41. Five agreed
outright, all multi-destination. **I concede all three disagreements**, so
the two independent readings converge on **6 / 50 = 12%**.

- **[13] `KXEARTHQUAKEM` — conceded, in thesis.** A magnitude ladder looks
  like a threshold, but a large earthquake is a *point process*, not the
  level-crossing of a continuous path. The spec's threshold exclusion
  targets the latter — "BTC above X" has a continuous path and
  barrier-option math. A marked arrival with a deadline is a hazard, which
  is the thesis.
- **[40] `KXSPCXLAUNCH-CREW13` — conceded, out of thesis.** I had called
  both launches IN "for consistency", flagging that if either was out both
  were. That substituted *procedural* consistency for the actual
  criterion, which the spec states as "launches with **fixed dates**".
  Crew-13 is a scheduled NASA rotation; New Glenn has no fixed date and
  its siblings form a date ladder. Splitting them on the stated criterion
  is more correct than my blanket rule.
- **[7] `KXBERNIEENDORSE-JTUR` — conceded, in thesis; the data settled
  it.** I read it as multi-destination. The 15 siblings are **different
  races** (NY, California gubernatorial, NY-12, Iowa Senate, Texas,
  Minnesota, Nebraska, Alaska…), independently endorsable, five already
  resolved at 1.00, price sum 7.41. I inferred exclusivity from the event
  grouping without checking what the siblings were.

## Both structural signals are blind on the residue

Verified independently rather than accepted. All five multi-destination
misses:

| event | flag | sibs | price sum |
|---|---|---|---|
| `KXACTORSONNYCROCKETT-35` | **False** | 10 | 1.40 |
| `KXANTHROPICBANKPUBLIC-28JAN01` | **False** | 15 | 4.03 |
| `KXBOND-30` | **False** | 30 | 1.88 |
| `KXOPENAIBANKPUBLIC-28JAN01` | **False** | 15 | 3.88 |
| `KXSUPERBOWLHEADLINE-27` | **False** | 54 | 4.42 |

`mutually_exclusive` is False on every one, and the 1.05 price-partition
threshold catches none. **Both signals fail precisely on the population
they were added for.**

## Verdict

**12% against a 10% bar**, SE ~4.6 at n=50. Against round 4's 16% the
difference is ~4 points on an SE of the difference near 6.6 — **not
distinguishable**. The structural signals are not a demonstrated
improvement, and the classifier still fails the spec's own kill criterion.

**"Take the data" is not vindicated.** The live options remain: a
structural LLM gate (contamination probe still unrun), a series allowlist,
or dropping the theory.
