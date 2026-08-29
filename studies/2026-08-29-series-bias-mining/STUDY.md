# Series bias mining — pre-registration, written BEFORE looking

**Date:** 2026-08-29 · **Status:** complete — **result: not measured** ·
**Tier:** A (no model anywhere) · Backlog spec #4, registry slug
`series-bias-mining`

**This file's bar was fixed and committed before any per-series bias
number was computed.** At the time of writing I had looked at exactly two
things: per-series row counts and per-series price ranges. No win rate,
no edge, no split. That is the whole point — with hundreds of series,
deciding what counts as a hit after seeing the hits is how
`mention_family` died, and the peer session's politics read this morning
showed the subtler version (a contrast chosen post-hoc reported as
pre-registered).

## Why this is a study and not a theory

The spec's own §3: *"The miner produces measurements, not bets — no live
screen of its own. Survivors become separate small theories."* CLAUDE.md
is explicit that `Theory` is for things that produce bets and that a
study produces theories. So nothing here registers a theory, records an
opportunity, or touches the ledger. Survivors become **pre-registered
proposals for a follow-on theory**, never bets on this data.

## Population

Settled rows from **`backtest-2026-08-25-insider-fullcov`** and
**`backtest-2026-08-25-mention-fullcov`** pooled.

Chosen because they are the only two populations that share **one
decision rule** — both are replays of `theories/insider_bias/screen.py`
at its pinned defaults (favorites 0.65–0.97, spread ≤ 0.07, volume ≥ 500,
entered at the first screen-qualifying day) — and they are **disjoint**
(insider-fullcov is explicitly the non-mention residue). Pooling runs
with different decision rules would make a mongrel population whose
per-series bias is partly an artifact of which rule sampled which series;
`backtest-2026-08-27-calharvest-weather` is deliberately **excluded** for
exactly that reason and is a separate future pass.

**Scope honesty:** this is therefore not "every recurring series". It is
*favorites in 0.65–0.97 at first qualifying day*, which is the population
`mention_family` was found in. A bias found here generalizes to that
screen, not to the whole board.

## Per-series inclusion floors (fixed now)

A series is **tested** only if all hold. A series failing these is not
read in either direction.

- `n >= 40` settled rows, and `n_days >= 8` distinct settlement days.
- Alive in **both** halves: `n >= 15` and `n_days >= 3` in each half.
  (Spec §10's survivorship risk: a series delisted mid-window truncates
  and can fake or hide bias.)

## The statistic

Per series, the **day-clustered** calibration edge, net of fees:

- one observation per settlement day = `mean(won) − mean(ask)` over that
  day's rows, in points (**gross** — see the amendment below);
- the series' estimate is the **mean over days**, SE the between-day
  standard error, `t = mean / SE`.

Day-clustered, not row-counted, because rows are not independent draws
and this repo has now been bitten by that four separate times in one day
(`buckets.py`, `no_side_premium` cell B, `insider_judgment`'s pooled
scores, `calibration_harvest`'s Wilson bound). A recurring series is the
*worst* case for it: its markets settle in tight clumps by construction.

### Amendment, 2026-08-29 — the guard scores GROSS, not net

**Found on fixture data, before the miner had seen a single real row.**
The clause above said "net of fees". That is wrong, and wrong in a way
that would have manufactured findings: fees are a roughly constant −1 to
−3 pt offset, so a **perfectly calibrated series** scores ≈ −1.12 net,
with the *same sign in both halves* and a magnitude above the 1.0 pt
gate. Every calibrated series in the population would have flagged as
persistently *negatively* biased, and the split-sample guard — the
study's central protection — would have waved them all through, because
a constant offset is perfectly consistent across halves by construction.

So the guard (sign, half-magnitude, `t`, Holm) is scored on the **gross**
calibration edge `(realized rate − ask)`, which is the bias itself. The
net edge is computed and reported beside it for the separate question of
whether a real bias is *bettable*.

Why this is a legitimate amendment and not a moved goalpost:

- it was found by `tests/test_series_bias_mining.py`'s fixture universe
  (spec §9: calibrated series among a planted one), **not** by looking at
  results — no real series' bias had been computed when it was made;
- it makes the guard strictly **harder**, removing a systematic
  false-positive channel rather than opening one;
- it is recorded here, in the file the bar lives in, rather than applied
  silently.

The same commit also fixes an inverted edge case found by the same
fixture: zero between-day variance produced `se = 0` and therefore
`t = 0`, treating a perfectly consistent effect as maximally
*insignificant*. It now reads as maximally significant.

## The multiple-comparisons guard — the central constraint

Hundreds of series means dozens look biased by chance. **All four are
required to flag a series:**

1. **Split-sample same sign.** Split the series' settlement days
   chronologically at its median day. Both halves must have the same
   sign. (Spec §4's guard.)
2. **Both halves individually non-trivial:** each half's day-clustered
   edge at least 1.0 pt from zero in that shared direction.
3. **Full-series day-clustered `|t| >= 2`.**
4. **Holm–Bonferroni across every series tested**, α = 0.05, family =
   the full set of tested series. Reported alongside the uncorrected
   count, and alongside the **expected number of false positives under
   the null** (`α × n_series`) so a reader can see the multiplicity
   directly.

**One test per series. No price-bin subdivision in v1** — that is what
multiplies the comparison count, and spec §10 says resist it until the
guard is proven. Bins are a follow-on for a series that already survived.

## What counts as what

- **Confirmatory:** at least one series passing all four gates. Its bin
  table becomes a *pre-registered proposal* for a follow-on theory, and
  the follow-on's `edge_basis` may be `measured` **only** after a
  forward or out-of-population test — never on this data, which is the
  data that selected it.
- **Valuable negative (spec §7):** nothing survives → the recurring
  series in this population are calibrated at the family level. Record it
  and say the miner's premise did not generalize beyond
  `mention_family` — which itself later died at full coverage, so this
  outcome is genuinely likely.
- **Uninformative:** fewer than ~10 series clear the inclusion floors.
  Then the population is too thin to test the guard at all, and the
  answer is "not measured", not "nothing there". Recording that
  expectation now so a thin result is not talked up later.

## Known limits, fixed now

- `mention_family`'s series are in the population. They are measured for
  comparison but **never re-promoted** (spec §3), and their known
  full-coverage failure (−1.53 net, n=3,441) means a positive flag on
  them is evidence the guard is *too loose*, not evidence of edge. This
  is the built-in negative control.
- Single decision point (first qualifying day), inherited from the
  screen. The spec's 7d/3d/1d points would triple the comparison count
  and are not used.
- In-sample throughout. The split-sample test is out-of-sample in *time*
  within a series, which is weaker than a fresh population.


---

# Result (run 2026-08-29, after the bar and the miner were both committed)

```
series seen              : 461
series tested (floors)   :  17
expected false positives : 0.9
pass split-sample guard  :   4
  ... and |t| >= 2       :   0
survive Holm-Bonferroni  :   0
FLAGGED (all four gates) :   0
```

Largest |t| anywhere is **1.43**. Nothing is flagged.

## This is NOT the pre-registered "valuable negative". It is "not measured".

The bar above says nothing surviving means "the recurring series in this
population are calibrated at the family level". **That conclusion is not
supported, and the fault is in the bar, not the data.**

Minimum detectable effect per series (≈ 2.8 × SE, the effect this test
would catch 80% of the time at α = .05):

```
median MDE           13.5 pts      best 0.8      worst 28.8
MDE <= 10 pts         7 of 17 series
MDE <=  5 pts         2 of 17 series
```

A theory-grade edge in this repo is **3–6 points**. The median series
here could only have detected an effect **two to four times larger than
anything worth betting**. Finding nothing was the overwhelmingly likely
outcome whether or not bias exists.

**And the population is mostly the control.** 10 of the 17 tested series
are `mention_family` (the built-in negative control, which is *known* to
be priced fairly at full coverage). Only **7 non-control series** were
actually tested. "Mine every recurring series" became "mine seven".

## The defect in my own pre-registration

The bar used **series count** as its power proxy — "fewer than ~10 series
clear the floors → uninformative". 17 cleared, so by the letter this
lands in the "valuable negative" bucket. That is wrong: series count says
nothing about whether any individual series could resolve a 4-point
effect, and `n >= 40 / n_days >= 8` admits series whose SE is 6–10
points.

**This is the same class of error I criticised in the peer session's
politics read a few hours earlier** — an inclusion rule that was never
stated as a claim, silently spanning the conclusion. There it was
"≥3 bins per day"; here it is "series count as power". Pre-registering
the *contrast* is not enough; the *power floor* and the *inclusion rules*
are part of the bar and have to be written down as such.

Recording it rather than quietly re-bucketing the result.

## What was actually learned

1. **One clean per-series measurement.** `KXAPRPOTUS` has an MDE of
   **0.8 pts** and a measured gross edge of **−0.06 ± 0.29**. That series
   really is calibrated, to within a point. It is the only series here
   where "calibrated" is a measurement rather than an absence.
2. **The negative control behaved.** All 10 `mention_family` series came
   back non-significant, consistent with their known full-coverage
   failure (−1.53 net at n=3,441). The guard did not manufacture a hit on
   data known to be fairly priced — which is the one thing this run does
   establish about the guard.
3. **One candidate worth a powered test.** `KXRT` (Rotten Tomatoes
   scores): gross **−4.23**, halves **−4.68 / −3.86**, SE 2.97 over 11
   days, t = −1.43. Exactly the size of effect this study could not
   resolve. **Pre-registered here as a hypothesis for a powered
   population**, not a finding, and explicitly not bettable on this data.

   **Do not read the split consistency as evidence.** −4.68 / −3.86 looks
   compelling and is the shape that fools people: both halves come from
   the *same 11 settlement days*, so the split guards against **regime
   change**, not against the effect being noise. Two halves of one noisy
   sample agree about as often as not. The only thing that resolves this
   is new data.

   So the powered re-test must pre-register, before looking: **the sign
   (negative — favorites in this series realize below their ask), the
   MDE (≤ 5 pts), and the population**. Fixing the sign in advance
   matters most: without it a *positive* result could be read as
   confirmation of "a bias exists", which would make the hypothesis
   unfalsifiable.

## Revisit angle

The blocker is data, and it is the collection I deferred earlier in the
session rather than anything about the method:

1. **Collect broadly first.** The 461 series seen collapse to 17 tested
   because the existing populations were fetched for other theories.
   A dedicated sweep (budget for the per-series `list_settled` walk, not
   the candlestick fetches — the peer measured 2,507 politics series of
   which 2,180 had zero fetchable markets) is the prerequisite.
2. **Pre-register a power floor, not a count floor.** Test only series
   whose MDE is ≤ some stated value (5 pts is the natural choice, being
   the low end of a theory-grade edge), and report how many series that
   excludes. A series that cannot resolve a bettable effect should not be
   in the family at all — it only inflates the Holm correction and
   dilutes the result.
3. **Exclude the control from the tested family.** `mention_family`'s
   series should be measured and reported separately, not carried in the
   Holm family where they consume correction budget for series nobody
   would promote anyway.
4. `KXRT` first when power exists.
