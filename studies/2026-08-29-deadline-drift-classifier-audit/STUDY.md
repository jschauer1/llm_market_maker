# deadline-drift's rules classifier: three audit rounds, 40% → 20% → 12%

**Date:** 2026-08-29 · **Status:** incomplete — stopped deliberately ·
**Tier:** A (no model in the measurement path) · **Verdict:** the theory is
viable and the population is large, but the classifier has not yet cleared
its own kill threshold and needs at least one more round

## Question

[deadline-drift](../../docs/superpowers/specs/theories/2026-08-24-theory-deadline-drift-design.md)
(backlog #2, effort M) buys NO on markets that resolve YES only if a
discrete, **unscheduled affirmative event** occurs by a deadline, when the
implied hazard exceeds the historical hazard by more than fees.

Its section 8 says "the rules-text classifier and its audit are most of
the work"; its section 7 makes that a kill criterion:

> Screen misclassification > ~10% on a hand-audited sample of 50 → fix the
> screen before trusting any bin. Misclassified threshold markets pool a
> different stochastic process into the bins and poison the measurement —
> this is the design's known weak joint.

So the classifier was built and audited **before** any hazard bins were
collected. That ordering is the point: the bins cost hours of API time
that Kalshi rate-limits to ~4–5 req/s (see
`theories/calibration_harvest/NOTES.md` 2026-08-29), and pooling the wrong
markets into them would waste all of it.

## Method

The board is this session's shared pull (117,272 markets); no API calls.
Candidates are markets whose `rules_primary` carries a by-deadline
phrasing ("before <date>", "by <date>", "on or before", "no later than").
Each round applies the current exclusions, then draws a **systematic
sample of 50** over ticker order, offset so the three samples are
disjoint. Every sampled market was classified by hand against the spec's
own definition.

`classifier.py` is the round-3 classifier; `data/round{1,2,3}_sample.txt`
are the exact samples judged.

## Results

| round | population | sample | misclassified | rate |
|---|---|---|---|---|
| 1 | 7,613 | 50 (42 series) | 20 | **40%** |
| 2 | 5,155 | 50 (50 series) | 10 | **20%** |
| 3 | 4,792 | 50 (48 series) | 6 | **12%** |

Converging, and not yet under the 10% bar.

### What each round found

**Round 1 — the spec's exclusion list is missing its biggest family.**
The spec names two non-goals: scheduled certainties and continuous
thresholds. The dominant contaminant is neither. It is
**multi-destination "which branch" markets** — 18 of 50:

```
"If Anthony Davis's next team is Houston before Oct 21, 2026 ..."
"If Houston is the first NFL team to announce the sale ... before Jul 1, 2027"
"If Marianne Lake is appointed ... as CEO for JP Morgan before Dec 31, 2035"
```

These resolve YES only if the event happens **and** lands on this specific
branch, so the process is a hazard **times a conditional multinomial**, not
a hazard. Pooling them into hazard bins is exactly the poisoning section 7
warns about, arriving from a direction the spec did not name. At board
scale this family is **2,687 markets — 34% of the whole by-deadline
population**, so it is not a footnote.

Round 1 also found one count threshold (`KXRKLBCOUNT`, "Above 11 launches
by D") and one scheduled release.

**Round 2 — three more families, all prose variants.** 10 of 50:

- count thresholds written as prose rather than as a comparison
  (`"the number of AIPAC-endorsed candidates who lose ... is at least 5"`,
  `"if above 1 federal judges are confirmed"`, `"... is exactly 1"`);
- **role-succession** "which person" markets, the same multi-destination
  objection in different words (`"is the first person confirmed as
  Commissioner of the FDA"`, `"is the first such subject to do so"`,
  `"becomes Prime Minister ... following the next election"`);
- scheduled competition outcomes (`"wins a tennis major before Dec 31"` —
  the majors happen on the calendar, so the question is the outcome, not
  the occurrence).

**Round 3 — still six, and still new phrasings.**

- `"average regular gas prices ... are strictly greater than $5.30"` — a
  price threshold that says "strictly greater than" instead of "above";
- `"scores above 1515 on Arena AI Text Score"` — a score threshold whose
  verb the round-2 pattern did not cover;
- `"combine to win at least 1 championship"` — count **and** scheduled;
- `"is the first individual in this list to publicly declare"` — the
  multi-destination pattern, defeated by an adverb between "to" and the
  verb;
- `"becomes Chief Minister of Isle of Man following the 2026 Manx general
  election"` — role succession without the round-2 boilerplate;
- `"become the second person in the world to reach a net worth of at least
  $1 trillion"` — an ordinal race plus a threshold.

Three further borderline cases were counted as correct but are arguable:
product releases with announced dates (`iPhone 18 Pro`, the next James
Bond film) are scheduled certainties in substance.

## What this means

**The theory is viable.** After three rounds of exclusions the population
is still **4,792 markets across 859 series**, 3,079 of them in the spec's
$0.05–$0.60 entry band, and the surviving markets are squarely the thesis:
traded before D, pardoned before D, charged before D, IPO confirmed before
D, legislation becomes law before D, manager out before D, cast before D.

**But the classifier is a long tail of prose, not a small pattern set.**
The rate is decaying by roughly half per round and every round finds a
family the previous one did not imagine. Two readings, and the study does
not have the evidence to choose between them:

1. *It converges.* One or two more rounds gets under 10% and the work is
   done. The decay so far is consistent with this.
2. *It does not.* Kalshi's rules prose has no fixed grammar, so a
   regex classifier has an irreducible error floor somewhere near
   10%, and the spec's own bar is unreachable this way.

If (2), the honest fix is the one CLAUDE.md already describes: this is the
case where a *model* gate earns its cost, because the exclusions need
reading comprehension rather than resolution mechanics. That would cost
the theory its tier-A status for the live path, which is a real price and
a decision for the user — a cheap LLM gate over ~4,800 markets is not
free, and it puts a model back in the decision path of a theory whose
whole appeal was not having one.

## Next

1. Run round 4 with the round-3 misses folded in. It is cheap — no API,
   one board pull — and it distinguishes reading (1) from reading (2)
   better than any argument.
2. **Amend the spec's non-goals** to name multi-destination /
   which-branch markets as a third excluded family, with the 34% figure.
   Anyone implementing from the spec as written would pool them.
3. Only then collect hazard bins. They are the expensive step and the one
   the misclassification rate poisons.
