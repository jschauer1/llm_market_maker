# deadline-drift's rules classifier plateaus at ~15%, above its own kill bar

**Date:** 2026-08-29 ·
**Tier:** A (no model in the measurement path) ·
**Verdict:** the theory is viable and the population is large, but a **regex classifier does not reach the spec's 10% bar** — it plateaus near 15%, and the residue is semantic, not syntactic

## Question

[deadline-drift](../../tickets/new-theory/completed/2026-08-24-deadline-drift.md)
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
`theories/retired/calibration_harvest/NOTES.md` 2026-08-29), and pooling the wrong
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

---

# Round 5 — structure instead of wording, and it does not clear either

**Date:** 2026-08-29 (same day, later session) · **Tier:** A (no model in
the measurement path) · **Verdict:** **12%, still above the 10% bar**, and
the reason is more interesting than the number

## What changed

Rounds 1–4 read the *wording*. Round 5 keeps those regexes unchanged and
adds two signals that read the market's *structure*:

1. **Kalshi's event-level `mutually_exclusive` flag** — ground truth for
   "does this condition on which branch?", published by the venue instead
   of inferred from prose. It reached the board in `09a66f7`; before that
   `list_open` fetched it on every pull and discarded it.
2. **A price-partition test** — ≥3 siblings sharing *one* deadline whose
   prices sum ≤1.05. The shared-deadline condition is load-bearing: without
   it the rule kills date ladders (`KXALITOOUT` at four deadlines is nested,
   not exclusive) and cost 88 false positives when first measured.

`classifier_r5.py` was **frozen before the sample was drawn**, and says so.
The two rules were fitted on round 4's misses, so re-tuning them here would
manufacture exactly the in-sample flattery the round exists to detect.

Population: 7,820 by-deadline → **4,135 candidates** in 786 series, 2,623
in the $0.05–0.60 band. The new signals removed 654 markets the regex kept
(336 by flag, 318 by price partition).

## Result

Sample drawn after excluding all 181 tickers judged in rounds 1–4, at a
fresh systematic offset, with asserts on disjointness and size.

| round | population | misclassified | rate |
|---|---|---|---|
| 1 | 7,613 | 20 | 40% |
| 2 | 5,155 | 10 | 20% |
| 3 | 4,792 | 6 | 12% |
| 4 | 4,792 | 8 | 16% |
| **5** | **4,135** | **6** | **12%** |

**6/50 = 12%**, range 12–16% on two recorded judgment calls. SE at n=50 is
~4.6pts, so 12% and round 4's 16% are the same number: **the structural
signals are not a demonstrated improvement.** The in-sample projection was
~8%; measured out-of-sample it is 12%. That gap is the entire reason the
round was run.

## Why — and this is the transferable part

**All six misses carry `mutually_exclusive = False`.**

The flag agreed with **98%** of the regex's 2,687 existing multi-destination
exclusions, which is what made it look decisive. But that measured agreement
on markets **the regex already caught**. On the residue — the only place the
flag was ever needed — it is False every time.

This is the same conditioning trap that produced `structural_arb`'s
all-false flag cache, discovered hours earlier in the same repo: *a signal
validated on the population where the old method already worked tells you
nothing about the population where it failed.* Validating on the easy class
and deploying against the hard one is the error, and it survived two
sessions writing the lesson down.

**The price-partition test fails separately, and it looks harder to fix.**
Exclusive events are not reliably *priced* like partitions:

```
KXSUPERBOWLHEADLINE-27  "Who will headline?"  54 legs, sum 3.64  — exclusive
KXBOND-30               "the next James Bond" 30 legs, sum 1.72  — exclusive
KXACTORSONNYCROCKETT-35 one role              10 legs, sum 1.08  — exclusive
```

Only *tightly priced* partitions sum near a dollar. Illiquid longshot legs
have wide spreads and overstated mids, so a 54-leg exclusive event sums to
3.64. Loosening 1.05 to reach them would swallow the date ladders the
shared-deadline exemption exists to protect — the two failure modes push the
threshold in opposite directions.

## What this leaves

The multi-destination residue has now defeated, in order: four rounds of
rules-text regex, the venue's own exclusivity flag, and a price-structure
test. The population is real (4,135 markets, 2,623 in band) and the thesis
is still untested — **no hazard bins have ever been collected**, which
remains correct under the spec's section 7.

What is now ruled out is that the screen can be made clean *mechanically*.
That is a genuine narrowing, not a failure: it converts the user's original
three-way choice into a two-way one, and it removes the option that looked
free.

Labels were committed (`ca1333a`) **before** a blind second reading was
requested, because the session that wrote the rules under test is a
conflicted auditor. **Session 18 then read the sample blind and converged
on exactly the same six.** It independently returned 7; adjudicating the
three disagreements resolved all three, including 18 withdrawing its unique
call after checking that `KXBERNIEENDORSE`'s 15 siblings are different
*races*, five already resolved at 1.00, summing 7.41 — not a selection.
Two independent readings, one number: **12%**.

---

# Round 5b — the allowlist, audited exhaustively, is clean

Round 5 killed the *broad* mechanical screen. That leaves the series
allowlist, whose premise — "these series are unambiguously in-thesis" —
had never been tested. It is a **series**-level construct, so it can be
audited **exhaustively rather than sampled**: 70 series, no sampling error.

## Result

| | markets | series | in band |
|---|---|---|---|
| naive allowlist (suffix rule, no screen) | 1,036 | 72 | 623 |
| after the round-5 screen | **981** | **70** | **604** |

- **70 of 70 series are genuine per-subject hazards.** Every one asks
  "does this discrete unscheduled thing happen to this specific subject by
  this date", and its siblings are *different subjects* — different
  players traded, different officials pardoned, different leaders out —
  never branches of one outcome. The `KXIPO*` families are date ladders.
- **0 of the 981 survivors carry `mutually_exclusive=True`.**
- **0 are in the price-partition set.**
- The contamination flagged earlier is gone: **`KXUKCABOUT` — "who is
  *next* to leave the Burnham Cabinet", 23 markets, pure
  multi-destination — is removed in full.** Both signals fire on it
  (`flag=True`, and 23 legs sharing one deadline summing 0.90).

## Why the signals work here and failed in round 5

This looks contradictory and is not. The price test catches a partition
only when it is **tightly priced**, and that is a property of the
population, not of the rule:

```
KXUKCABOUT-BURNN28JAN01   23 legs, sum 0.90  -> caught
KXSUPERBOWLHEADLINE-27    54 legs, sum 3.64  -> missed
```

On the broad board the exclusive events that slip through are illiquid
longshot ladders whose mids overstate and whose legs sum to 3–4. Inside
the allowlist, the one exclusive family present is liquid and priced to
sum near a dollar. **Narrow the population and the same signal becomes
reliable** — which is the 0e lesson read forwards rather than backwards:
a signal's hit rate is a fact about a population, never about the signal.

## What this settles

The allowlist option is **live, tier A, mechanically clean, and audited
without sampling error** at 981 markets / 604 in the entry band. That is
enough for hazard bins and enough for a backtest.

It is now the strongest option on the board: it ships without a prompt, a
contamination probe, a provenance record, or the point-in-time payload
machinery that 4f's finding
(`docs/2026-08-29-structural-gate-payload-version/`) would require of a
gated version. The LLM gate remains the right instrument for *coverage*
later — 604 in-band versus ~2,600 — but coverage is worth paying for only
once the effect is known to exist, and it is still completely unmeasured.

---

# Limitations and defects (review by session 09, post-hoc)

Session 09 reviewed the execution after the fact — the design request was
overtaken by the blind read landing first. It independently re-verified
disjointness (zero overlap against all four prior sample files), the SE
arithmetic, and the two-reader protocol. Four things it raised, all
recorded here rather than argued:

## 1. 12% does not statistically *prove* failure, and must not be read as if it did

The exact binomial 95% CI on 6/50 is roughly **[4.5%, 24.3%]**, which
**contains the 10% bar**. So round 5 neither demonstrates clearing nor
proves failure.

The verdict rests on two things that are not that interval:

- **The burden is to demonstrate clearing**, and 12% does not. Section 7
  says fix the screen *before* trusting any bin; an unresolved interval
  spanning 4.5–24.3% is not a resolution.
- **The mechanism**, which is not statistical: both structural signals are
  *blind on the residue* — all six misses carry `mutually_exclusive=False`
  and none is caught by the price test.

Likewise "a mechanically clean screen is ruled out" is a **mechanism
claim** — three instrument families defeated in sequence — and not a
statistical one. A future reader should not treat 12% as proof, nor treat
the wide interval as an opening to relitigate without new evidence.

## 2. The price-partition test has no lower bound — a real defect, measured

As coded, **any** ≥3 same-deadline siblings summing ≤1.05 count as a
partition, including three unrelated longshots at $0.10. Measured:

| | events | markets excluded |
|---|---|---|
| price-partition total | 125 | 318 |
| sum ≥ 0.90 (genuine partitions) | 53 | 37 |
| **sum < 0.90 (spurious)** | **72** | **281** |

```
sum=0.13  22 legs  KXCOACHOUTNFL   "Which Pro Football coaches will be out"
sum=0.12   3 legs  KXUSFUNDHEAD-27 "Will Bill Ackman join Trump's fund?"
sum=0.11   6 legs  KXTRUMPWEP-27
```

`KXCOACHOUTNFL` is the clearest case: 22 *independent* coach-departure
hazards, low-priced, summing 0.13 — the exact false positive predicted
when the rule was first built, now confirmed.

**So the rule's real contribution was ~37 markets, not 318, and the
4,135 population figure is an undercount by up to 281 (true ≈4,416).**
This error direction *wrongly excludes in-thesis markets*, so it is
invisible to the round-5 audit, which sampled only what was kept. Its
effect on the rate is to make 12% a slight **over**-estimate — restoring
281 correct markets moves 6/50 to roughly 6/53 ≈ 11.3%, which changes no
conclusion. `≥0.90` is the fix, carried into any production screen.

**`classifier_r5.py` is deliberately NOT patched.** It was frozen before
the sample was drawn and that property is worth more than a corrected
population count; editing it now would retroactively break the one
guarantee that makes round 5 an out-of-sample measurement.

## 3. Round 5b is unaffected — verified, not assumed

**0 allowlist markets were wrongly excluded by the spurious rule.** The
981/604 figures and the 70/70 series verdict stand exactly as reported.
`KXUKCABOUT` sums to 0.90 and so is a genuine partition on either
threshold.

## 4. The two readings shared a frame, even though they were blind to each other's calls

Both readers knew the two rules under test and the round 1–4 error
taxonomy. **No rules-naive reader was ever used.** Given the convergence
and the pre-recorded borderline list this is unlikely to have moved the
number, but the independence claim is about *calls*, not about framing,
and the record should say so.
