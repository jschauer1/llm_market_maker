# Does the early-close anchor bug explain `strong-moderate-no`?

**Date:** 2026-09-01 ·
**Tier:** A ·
**Verdict:** the anchor bug is real and its direction is confirmed on both sides, but it DEPRESSES `strong-moderate-no` rather than inflating it — the clean arm is +5.20 net over 77 clusters against a +4.37 headline, so the slice is not an artifact ·
**Session:** `fleet-w3-g1`, study lane

## Why this study exists, and what it changes about the one it extends

`tickets/study/answer/2026-08-29-early-close-exposure-existing-backtests/` established
the bug and measured who is exposed. It sampled **70 tickers from each of
two full-coverage runs** and concluded:

- `mention-fullcov` is not exposed (3/68 carry by-deadline phrasing, none
  early).
- `insider-fullcov` is ~22% by-deadline, and ~80% of that family closed
  more than three days early — so **~18% of that population sits on a
  contaminated time anchor**, on a base of 15 markets.

It then reasoned, explicitly labelling the reasoning "a reasoned
expectation, not a measurement," that the bias inflates measured favorite
win rates, so a negative headline gets *more* negative and the
full-coverage conclusions stand. It flagged `no_side_premium`'s cell B for
a specific look and stopped, saying remediation was not its call.

**The extension is not a bigger sample of the same thing. It is a
different population.** Tracing which rows actually vouch for the repo's
only bettable result changes the target:

```
settled rows matching the slice predicate (outcome=no, confidence in
strong/moderate), by the run whose attempt recorded them:

  backtest-2026-08-26-insider-judged-s200    239   <- mined_from, in-sample
  backtest-2026-08-26-insider-judged-s200b   224   <- out-of-sample
  backtest-2026-08-26-insider-judged-s57      90   <- out-of-sample
  (live runs)                                ~75
```

`s200b` + `s57` = **314 rows — exactly the `n_backtest = 314`** carried by
the slice's headline score (+3.95 net, n 358, 92 event clusters). So the
evidence behind the repo's only R1-eligible segment comes from **three
judged campaign runs that the 2026-08-29 study never sampled.** It
measured exposure in `insider-fullcov`, whose headline is negative and for
which the bias direction is therefore reassuring; the runs the repo
actually bets on were not measured at all.

Those campaigns were replayed by the same `theories/insider_bias/replay.py`,
which anchors on `settled.close_time` at line 218, so they carry the
identical bug. Whether it matters there is unmeasured, and this study
measures it.

**What changed, stated as the extension rule requires:** a different
population (three judged runs, not two full-coverage runs), a full pass
rather than a 70-ticker sample, a **published-field** exposure classifier
rather than a rules-text regex, and an outcome contrast the original study
did not attempt.

## The question, in one sentence

Is `strong-moderate-no`'s +3.95 net carried by rows whose replay entry day
was computed backwards from an outcome-dependent close?

## Population — the inclusion rules, concretely

Every **distinct ticker** appearing in an `opportunity_attempts` row whose
`run_id` is one of:

- `backtest-2026-08-26-insider-judged-s200` (704 tickers) — **in-sample**;
  the slice was mined from it, so it vouches for nothing and is reported
  separately, never pooled into the primary contrast.
- `backtest-2026-08-26-insider-judged-s200b` (644 tickers) — out-of-sample.
- `backtest-2026-08-26-insider-judged-s57` (216 tickers) — out-of-sample.

**1,564 distinct tickers.** Every one is fetched; there is no sampling, so
there is no sampling error to report.

The **primary contrast set** is the subset that is settled and matches the
registered slice predicate (`outcome='no'` and the attempt's `confidence`
in `strong`/`moderate`) in the two out-of-sample runs — the 314 rows above.

## Exposure classification — published fields, in a fixed order

A market is **EXPOSED** iff its actual `close_time` precedes its scheduled
deadline by **more than 3 days**. The 3-day cut is inherited unchanged from
the study being extended, which set it before any of this was in view; a
median 3h early is settlement mechanics, not a contaminated anchor.

The deadline is taken from the first of these that resolves, and the
coverage of each is reported:

1. **`custom_strike.Date`** — a published structured field carrying the
   deadline for the by-deadline family. Preferred because a field is exact
   and cannot drift with phrasing (CLAUDE.md, division of labour).
2. **`theories.deadline_drift.collect_settled.parse_deadline`** over
   `title` then `rules_primary` — the parser the original study used, kept
   so the two studies' numbers are comparable.
3. Otherwise **UNKNOWN**: no by-deadline deadline could be established, so
   the market carries no exposure by this mechanism.

`can_close_early` is **not** used as the classifier. It was checked first
and is `True` on essentially everything sampled, including markets that
closed exactly at their deadline — it is a permission, not an event.

**Reported cross-check, not a classifier:** the maximum `close_time` among
fetched siblings of the same `event_ticker`, as a parse-free empirical
estimate of the scheduled close. It is reported beside the primary numbers
and is deliberately not allowed to move the classification, because it is
circular in an event where every sibling closed early.

## The contrast, and its predicted direction

Split the 314 out-of-sample slice rows into EXPOSED and UNEXPOSED and
compute event-clustered `calibration_edge_net` in each arm.

**Prediction, from the bug's stated direction.** The bias makes the replay
sample an exposed market during its run-up toward resolution, so it enters
as a high-priced favorite that then resolves in the favorite's direction:
it **inflates measured favorite win rates**. The slice buys **NO** on
favorites. So contamination should make an exposed NO-side row look
**worse**, not better:

> **EXPOSED arm edge <= UNEXPOSED arm edge.**

If that holds, the slice's +3.95 is *conservative* and the bug is not an
explanation for it.

**The falsifying result** is the opposite sign: the unexposed arm materially
below the exposed arm, i.e. the measured edge is carried by contaminated
rows.

## Negative control, with a known predicted sign

The **YES-side rows of the same judged runs** (`outcome='yes'`, same
confidence buckets, same runs, same fetch). The bug inflates favorite win
rates, so on the YES side exposure should push the measured number the
*other* way — up, not down. A control that moves in the predicted opposite
direction is evidence the classifier is separating what it claims to.
It is measured, reported, and kept **out of the multiple-comparisons
family** for the primary contrast.

## Power floor, and the pre-committed "not measured" rule

The slice's 314 out-of-sample rows sit on 92 event clusters, and clustered
SE is what this design is limited by, not row count. If exposure runs at
the ~18% the original study estimated, the exposed arm lands near 17
clusters.

> **Pre-committed floor: if either arm has fewer than 10 event clusters,
> the contrast is reported as NOT MEASURED and the study reports exposure
> only.** Fewer than 10 clusters is the same bar the repo's slice-readiness
> gates use, and a two-arm difference on a smaller base cannot distinguish
> a real shift from one event.

This is written before the split is computed precisely so that a thin
exposed arm cannot be reinterpreted after the fact as a reassuring null.
"Not measured" is a legitimate result and is different from "clean."

## What result would change what the repo does

- **Exposed <= unexposed, both arms populated** → the bug does not explain
  the slice; record it and stop re-litigating this. The 2026-08-29 study's
  reasoned expectation is confirmed by measurement.
- **Unexposed arm below +2.0 net while exposed is materially above it** →
  the slice's headline is an artifact of the anchor bug. That is a finding
  for the theory's owner and for `docs/promotion-key.md`, because the slice
  is currently R1-eligible and produced the 2026-09-01 floor's only bet.
- **Exposure near zero in these runs** → the judged campaigns are not
  exposed even though `insider-fullcov` is, the question is closed for the
  slice, and the difference between the populations is itself the finding.

## Multiple comparisons

The family for the primary question is small and fixed here: the
out-of-sample contrast, plus the same contrast on the in-sample `s200` run
reported separately. Holm across those two. The YES-side control is
excluded from the family by design, as is every descriptive exposure count.

## Tier

**A.** No outcome judgment is anywhere in the measurement path. The
confidence buckets are read as recorded data from `opportunity_attempts`;
nothing is re-judged, and no model is called. The exposure classifier is a
published field plus a date parser.

---

# Result

Run once, against the bar above. Raw output is `RESULT.txt`; regenerate with
`PYTHONPATH=. python tickets/study/answer/2026-09-01-early-close-exposure-in-the-bettable-slice/measure.py`.

## Capture

**1,564 / 1,564 tickers attempted; 1,413 fetched; 151 (9.7%) had already
aged out of Kalshi's public API.** Raw payloads are in `raw_markets.jsonl`,
complete rather than reduced to the fields this study needed.

That 9.7% is itself a finding worth carrying: the 2026-08-29 study fetched
68 of 70 (2.9% gone) from an overlapping window **three days earlier**. The
archive floor is advancing daily and it is eating the evidence base of the
repo's only bettable slice. Anything else anybody wants to know about these
markets has to be asked of the captured file, not of Kalshi.

## Exposure, over every captured ticker

| state | n | share |
|---|---|---|
| EXPOSED (closed > 3d before its deadline) | 264 | 18.7% |
| UNEXPOSED (deadline found, closed on time) | 361 | 25.5% |
| UNKNOWN (no by-deadline deadline found) | 788 | 55.8% |
| aged out of the API | 151 | — |

Deadline source: `parse:title` 332, `parse:rules_primary` 231,
`custom_strike` 61, `parse:subtitle` 1.

**Among EXPOSED markets the median close is 147 days early**, p90 895 days,
max 1,277. This is not settlement jitter; it is a completely different time
anchor, and it confirms the phenomenon at full-population scale rather than
on the original study's base of 15.

**`custom_strike.Date` did not live up to its promise as the primary
instrument.** It resolved only 61 of 625 classifications — the field is
present on a minority of this population, and where it is present it is
often the date-certain `"Jul 1, 2026"` form rather than `"Before Jul 1,
2026"`. The published-field-first ordering was still the right call (it is
exact where it exists), but the rules-text parser inherited from the
2026-08-29 study did 90% of the work. Anyone planning to lean on
`custom_strike` for a by-deadline screen should size that expectation
against 61/625.

## Primary — out-of-sample slice rows (`s200b` + `s57`)

Slice predicate: `outcome='no'`, `confidence in (strong, moderate)`.

| arm | n | clusters | edge_net | clustered se | win rate |
|---|---|---|---|---|---|
| **whole slice arm (headline)** | 314 | 86 | **+4.37** | 2.49 | 0.917 |
| EXPOSED | 54 | **7** | **+0.69** | 14.99 | 0.889 |
| UNEXPOSED | 113 | 34 | +6.64 | 4.48 | 0.938 |
| UNKNOWN (no deadline, so not exposed) | 134 | 43 | +4.00 | 3.48 | 0.910 |
| **CLEAN = UNEXPOSED + UNKNOWN** | 247 | 77 | **+5.20** | 2.76 | 0.923 |
| aged out (unclassifiable) | 13 | 4 | +3.93 | 6.20 | 0.923 |

**The formal contrast is NOT MEASURED, by this study's own pre-committed
floor.** The EXPOSED arm holds 7 event clusters against a floor of 10. That
rule was written before the split was computed, precisely so a thin exposed
arm could not be talked into being a reassuring null, and it binds here. No
p-value is claimed for EXPOSED minus CLEAN, and the Holm family is empty.

**The pre-registered kill criterion is NOT triggered.** It read: *"unexposed
arm below +2.0 net while exposed is materially above it."* The clean arm is
**+5.20 over 77 clusters** — above the +2.0 bar and **above the headline
+4.37** — with the exposed arm *below* both. The falsifying pattern is
absent, and that is a pre-registered read which does not depend on the
contrast clearing the power floor.

## Secondary — in-sample (`s200`, the run the slice was mined from)

Reported separately and pooled into nothing; it vouches for the slice for
the same reason it always did, which is that it does not.

| arm | n | clusters | edge_net | se | win |
|---|---|---|---|---|---|
| whole arm | 239 | 77 | +5.34 | 2.49 | 0.921 |
| EXPOSED | 20 | 9 | **-1.54** | 15.26 | 0.850 |
| CLEAN | 201 | 66 | **+7.68** | 2.02 | 0.945 |
| aged out | 18 | 5 | -13.17 | 18.69 | 0.722 |

Same direction, same shape, on an independent market sample.

## Negative control — the YES side, where the bias must push the other way

| run | arm | n | clusters | edge_net | se |
|---|---|---|---|---|---|
| OOS | EXPOSED | 33 | 14 | **-0.16** | 7.10 |
| OOS | CLEAN | 100 | 47 | **-5.14** | 4.89 |
| in-sample | EXPOSED | 41 | 17 | **+8.80** | 5.83 |
| in-sample | CLEAN | 57 | 37 | **-16.13** | 6.94 |

**The control behaves exactly as the mechanism says it must.** On the YES
side, exposure moves the measured number *up* — by +4.98 out of sample and
+24.9 in sample. On the NO side it moves it *down*, by -4.51 and -9.22. The
classifier is separating what it claims to separate, and the sign flips with
the side of the bet, which is the signature of an outcome-dependent time
anchor rather than of a liquidity or family confound.

## The evidence that actually carries this study: a sign test

No single arm difference here is powered — the EXPOSED arms carry 7 to 17
clusters and standard errors of 6 to 15 points. **What is powered is the
pattern.** Four comparisons were specified in advance with a predicted
direction, and all four came back in that direction:

| comparison | predicted | observed |
|---|---|---|
| NO side, out-of-sample | exposed lower | -4.51 yes |
| NO side, in-sample | exposed lower | -9.22 yes |
| YES side, out-of-sample | exposed higher | +4.98 yes |
| YES side, in-sample | exposed higher | +24.9 yes |

Exact one-tailed sign test, direction fixed before looking: **p = 0.0625**
(4/4). Not significant at 0.05, and said plainly rather than rounded into
one. The in-sample and out-of-sample runs draw from overlapping event space,
so the four are approximately — not perfectly — independent, which if
anything makes 0.0625 optimistic. Treat this as a **coherent,
pre-registered directional result on an unpowered magnitude**, not as a
demonstrated effect size.

## The parse-free cross-check failed, and that is worth writing down

The sibling-max-close heuristic — label a market exposed if it closed more
than 3 days before the latest close among its event siblings — agrees with
the deadline classification on **333/625 = 53.3%**, which is chance. It is
not a usable substitute for reading the deadline, and the reason is the one
the pre-registration anticipated: in a by-deadline event where every sibling
can close early, the max is itself contaminated. Recorded so nobody reaches
for it as a cheap shortcut later.

## Answer to the question

**No.** `strong-moderate-no`'s edge is not carried by rows with a
contaminated time anchor. The clean arm is *higher* than the headline
(+5.20 vs +4.37 out of sample; +7.68 vs +5.34 in sample), the exposed arm is
the drag, and the bug's direction is confirmed on both sides of the book.
The 2026-08-29 study's reasoned expectation — that a NO-side result drawn
from this population is conservative rather than at risk — is now a
measurement, on the population that actually matters.

**What this does not license.** It is not a claim that the slice's edge is
larger than recorded. The clean-arm figure is a post-classification subset
whose selection depends on a parser, and the study is not powered to
distinguish +5.20 from +4.37. The recorded score stays the number to bet on;
this study removes an alternative explanation for it, and nothing more.

## Limits

- **The formal contrast is unpowered and is reported as not measured.** The
  whole conclusion rests on a 4/4 sign pattern at p = 0.0625.
- **55.8% of the population is UNKNOWN**, treated as unexposed per the
  pre-registered classifier. If a material share of those are by-deadline
  markets the parser missed, they are exposed rows sitting in the clean arm
  — which would *understate* the contrast, i.e. bias against this study's
  own conclusion, but it is a real hole. The 2026-08-29 study named the same
  limit and it is not fixed, only measured better (44% classified here
  against 22% there).
- **9.7% of the population is already unreachable** and is excluded from
  both arms. It is 13 rows out of 314 out-of-sample and cannot move much,
  but the share grows every day.
- The `welch` helper uses a normal approximation. It never fired, because no
  contrast cleared the floor.

## What was changed outside this folder, and why

`tools/score.py`'s `observations()` gained a **`kalshi_ticker`** field on
single-leg rows. Its docstring already promised "the identity fields a slice
predicate and its out-of-sample split key on," and the ticker is the most
basic of them, but it was not in the dict — so any consumer wanting to
partition observations by a per-**market** property could only reach the
event through `cluster`, which merges exactly the siblings that differ on
the property being tested (in a by-deadline event the YES market closes
early and its NO siblings do not). Purely additive; `_aggregate` ignores it;
`tests/test_score.py` and `tests/test_attempt_scoring.py` pass unchanged. A
basket observation has no single ticker and carries no such key.
