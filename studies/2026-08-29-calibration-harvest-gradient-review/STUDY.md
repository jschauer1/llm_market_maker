# Second eyes on calibration_harvest's politics gradient

**Date:** 2026-08-29 · **Status:** complete · **Tier:** A (no model in the
measurement path) · **Author:** session `llm-market-identifier-4f`, at the
request of `llm-market-identifier-18`, who ran the original analysis and
asked for the check before anyone acts on it.

## What was claimed

`calibration_harvest`'s politics population (run
`backtest-2026-08-29-calharvest-politics`, 2,507 series, 1,541 obs, 916
markets) was reported as **"the horizon gradient is real"**, headline
statistic **+7.68 ± 2.20, t = 3.50**, described as *"the pre-registered
contrast, long vs short horizon"*, 29/45 days positive, sign test
p = 0.036.

Reproduced exactly with `python -m theories.calibration_harvest.gradient`.
Nothing below disputes the arithmetic; the question is what the numbers
support.

## Verdict

**The direction survives. "Gradient" does not, and the headline t is the
maximum of three choices rather than a pre-registered one.** None of this
changes the bettable conclusion, which the original read already got right:
all sixteen cells are net-negative at the Wilson bound, so nothing is
recommendable either way.

## 1. The monotonicity violation is noise — this one is fair

The pre-registration (`4a01f9a`) predicts
`1mo+` > `1w-1mo` > `2d-1w` > `<=2d`. Observed: −1.21, −4.26, +5.05,
+9.38 — inverted at the first step.

Paired within settlement day, `2d-1w` − `<=2d` = **−2.19, SE 2.45,
t = −0.90**. The two short bins are statistically indistinguishable, so
the violation is not evidence against the theory. Conceded.

## 2. But there is no gradient — there is one step

Decomposing into adjacent steps, each paired within day (the prediction is
that all three are positive):

| step | Δ pts | SE | t | n_days |
|---|---|---|---|---|
| `2d-1w` − `<=2d` | −2.19 | 2.45 | −0.90 | 50 |
| **`1w-1mo` − `2d-1w`** | **+7.01** | **2.36** | **+2.96** | **41** |
| `1mo+` − `1w-1mo` | +0.06 | 3.03 | +0.02 | 28 |

**The entire effect is one step change at the 1-week boundary.** Flat,
then a jump, then flat. That is a *level shift*, not a gradient.

This matters because of what was predicted and why. The pre-registration
derives (2) from Le 2026's calibration **slopes of 1.48–1.83 from 12h out
to a month** — a compression effect that *grows continuously with
horizon*. A single discontinuity at one bin boundary does not corroborate
a slope; it is equally consistent with something changing about the
markets themselves at ~1 week (different series mix, different liquidity,
different participants). Calling it a gradient imports a mechanism the
data does not show.

## 3. The reported contrast was not pre-registered, and its t is a maximum

**Not pre-registered.** `4a01f9a` fixes a *four-way ordering*. The word
"contrast" in a horizon sense first appears in `9d9526a` — the commit
reporting the result. (`f35948d` also matches a grep for "contrast", but
that is the *domain* contrast, weather vs elections, unrelated.) The
long-vs-short two-group collapse was chosen after seeing where the sign
flipped.

**Its t is the max over the available splits.** Four bins give three split
points, all computable paired within day:

| split after | Δ pts | SE | t | n_days |
|---|---|---|---|---|
| `<=2d` | +0.24 | 2.30 | +0.11 | 51 |
| **`2d-1w`** | **+7.68** | **2.20** | **+3.50** | **45** ← reported |
| `1w-1mo` | +7.33 | 3.29 | +2.23 | 31 |

One of three splits shows nothing at all. The reported split is the
largest. That is a small forking path — three options, not sixteen — but
it is real, and it is the difference between t = 3.50 and a number
honestly labelled as the best of three.

## 4. The split-free statistic, which is what should be quoted

Regress each settlement day's edge on horizon-bin rank and average the
day-level slopes. This uses all four bins, picks no split, and needs no
post-hoc choice:

```
day-level slope of edge on horizon rank
  +3.14 pts per bin,  SE 1.17,  t = +2.68,  42 days,  26/42 positive
```

**This still clears the pre-registered 2 SE bar.** So a positive
horizon effect in politics does survive an honest, choice-free estimator —
at t ≈ 2.7, not 3.5, and described as a level shift rather than a slope.

## Recommendation

1. Quote **+3.14 pts/bin, t = 2.68** (split-free) as the headline, not
   +7.68 / t = 3.50.
2. Drop "pre-registered" from the long-vs-short contrast, or report it as
   "best of three splits, t = 3.50 / 2.23 / 0.11".
3. Replace "gradient" with "a single level shift at the 1-week boundary",
   and note it does **not** corroborate Le 2026's slope mechanism.
4. Keep everything else: `testing` status, the out-of-sample `active` bar,
   and "nothing is bettable" are all correct and unaffected.
5. The pre-registration itself worked. It is the reason this was
   checkable at all — the failure mode it caught is a *reporting* one, not
   a data-dredging one, and the original read flagged the
   non-monotonicity itself rather than hiding it.

## Limits

- In-sample throughout; none of this speaks to out-of-sample behaviour.
- The step at 1 week may be a composition artifact (which series have
  markets a week out vs two days out) rather than anything about horizon.
  Untested here, and worth testing before the level shift is believed as
  a horizon effect at all.
- `n_days` per step falls to 28 at the long end, so the two flat steps are
  the least well measured and a real slope could hide inside them.
