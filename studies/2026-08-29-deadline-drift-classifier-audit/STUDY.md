# deadline-drift's rules classifier plateaus at ~15%, above its own kill bar

**Date:** 2026-08-29 · **Status:** complete · **Tier:** A (no model in the
measurement path) · **Verdict:** the theory is viable and the population is
large, but a **regex classifier does not reach the spec's 10% bar** — it
plateaus near 15%, and the residue is semantic, not syntactic

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
sample of 50** over ticker order, at a different offset so the four
samples are disjoint. Every sampled market was classified by hand against
the spec's own definition.

`classifier.py` is the round-4 classifier; `data/round{1,2,3,4}_sample.txt`
are the exact samples judged.

## Results

| round | population | sample | misclassified | rate |
|---|---|---|---|---|
| 1 | 7,613 | 50 (42 series) | 20 | **40%** |
| 2 | 5,155 | 50 (50 series) | 10 | **20%** |
| 3 | 4,792 | 50 (48 series) | 6 | **12%** |
| 4 | 4,792 | 50 (50 series) | 8 | **16%** |

**Round 4 is the answer, and it is not convergence.** Rounds 1–3 looked
like a rate halving toward the bar. Round 4 applied every fix rounds 1–3
implied and came back *worse*. At n=50 the standard error on a ~15% rate
is about 5 points, so 12% and 16% are the same number: the classifier has
**plateaued around 15%**, above the spec's 10% kill threshold.

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

**Round 4 — every previous fix applied, and the same family walks back in
wearing new clothes.** 8 of 50, five of them multi-destination again:

```
"the next club that Cristiano Ronaldo joins is CF Monterrey before D"
"Russia is the first country to launch a manned mission to the Moon before D"
"the next new Secretary of Defense before Jan 20, 2029 is Mike Pompeo"
"leaves ... before any other Pro Football head coach before D"
"a coalition that includes SPD make up the next elected ruling government"
```

Round 3's pattern already covered "next club is", "is the first ... to
declare", "becomes <role> following the <election>". None of these five
match it, and no reasonable extension of it anticipates the next five.
Plus two more thresholds in prose ("orders Meta to pay $10 billion **or
more**", "USD/BRL **rises above** 6.4999").

## What this means

**The theory is viable and its population is real.** 4,792 markets across
859 series survive, 3,079 in the spec's $0.05–$0.60 entry band, and the
survivors are squarely the thesis: traded before D, pardoned before D,
charged before D, IPO confirmed before D, legislation becomes law before
D, manager out before D, cast before D.

**But a regex classifier will not get there, and round 4 is why.** The
question the study set out to answer was whether the decay 40 → 20 → 12
was convergence or a floor. Round 4 folded in every fix the first three
rounds implied and came back at 16%. At n=50 the SE on a 15% rate is ~5
points, so 12% and 16% are one number: **a plateau near 15%**, comfortably
above the spec's 10% bar.

**The reason is that the residue is semantic, not syntactic.** The
irreducible family is multi-destination — "does this market condition on
*which branch* the event takes?" — and Kalshi expresses that question in
unboundedly many ways: a possessive ("X's next team is Y"), a relative
clause ("the next club that X joins is Y"), an ordinal ("is the first
country to launch"), a comparative ("before any other head coach"), a
composition ("a coalition that includes SPD make up the next
government"). These share a *meaning*, not a *string*. A pattern set can
chase them forever and always be one phrasing behind, which is exactly
what four rounds show.

This is the case CLAUDE.md describes for reaching past code: *"Prefer code
when the exclusions follow from resolution mechanics; reach for a model
when they need reading comprehension."* The vendor-panel and sport
exclusions in `insider_judgment`'s gate follow from mechanics and a regex
nails them. "Which branch does this condition on?" does not.

## The decision this leaves the user

**Amended 2026-08-29, after this section was written.** Two repo changes
landed the same day and both bear directly on the options below, so the
original framing — "three options, all trading away the theory's defining
property" — is **no longer correct** and is corrected here rather than
left to mislead.

1. `tools` stopped discarding Kalshi's event envelope (`09a66f7`), so
   **`mutually_exclusive` is now free on every market**. It answers the
   multi-destination question — "does this condition on which branch?" —
   outright, as data.
2. The user amended the tier rule (`0f06265`): tier A now means *no
   **outcome** judgment* in the decision path, so a **structural gate**
   no longer costs tier A. The old rule penalised a gate reading market
   text identically to a model predicting outcomes.

The corrected options:

1. **Take the data.** Use `mutually_exclusive` from the board, plus a
   price-partition test for the residue. Free, exact, instant, no prompt
   and no probe, and unambiguously tier A. CLAUDE.md now names this exact
   field as its worked example of preferring data over a model, with the
   explicit instruction that no prompt should be written to re-derive it.
   **This is the first-choice option and it did not exist when this study
   was written.**

   **It is not yet established that it clears the 10% bar.** The flag
   *alone* catches only **2 of the 5** named round-4 misses; it takes the
   flag **plus** the price-partition test to reach 4 of 5, and the
   resulting projection of ~8% is **in-sample on the very round-4 markets
   that motivated the rule**. What the flag has going for it is
   independent of that: 98% agreement with the regex's 2,687 hand-derived
   exclusions, and it reaches the multi-destination residue the regex
   structurally could not. Strong first instrument; unmeasured out of
   sample. **Round 5 is that measurement**, and it should be run on a
   fresh disjoint sample before anyone records this as solved.
2. **Structural LLM gate.** Under the amended rule it **keeps tier A**
   *if* it meets all four conditions — answerable from
   the market's text at open, payload of rules and title only, decides
   eligibility never direction, and **passes the contamination probe**.
   The first three are plainly satisfiable for "does this condition on
   which branch?"; the fourth is **unrun**, and CLAUDE.md is explicit
   that an unrun probe counts as outcome judgment. So this is *plausibly*
   tier A, not established as tier A — and whether it would clear 10% is
   equally unmeasured, since no LLM gate has been built or run against
   any sample here. It still costs tokens on every
   scan, and it is third in the stated preference order (data, then code,
   then structural gate, then outcome judgment).
3. **Series allowlist** of the ~20 unambiguous recurring families
   (`KXFEDERALCHARGE`, `KXTRUMPPARDON`, `KXNBATRADE`, `KXNFLTRADE`,
   `KXIPO*`, `KXNCAAFCONFLEAVE`, `KXMLBDEBUT`, the `*OUT` families).
   Mechanical and tier A, but a smaller population and the maintenance
   treadmill the 2026-08-29 gate work moved away from.
4. **Drop it.**

The study still has no opinion between the *remaining* choices — but the
old option 1 was framed as a sacrifice it no longer requires, and option
1 as now written is strictly better than the LLM gate on every axis the
repo's own preference order names.

## Next

1. **Amend the spec's non-goals** to name multi-destination /
   which-branch markets as a third excluded family, with the 34% figure —
   **done, 2026-08-29**, in the spec's section 3.
2. **Do not collect hazard bins** under any option until the population is
   settled. They are the expensive, rate-limited step and the one
   misclassification poisons.
3. User decides among the three options above.
