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

---

# Pass 2 — pre-registration for the weather population (written BEFORE looking)

**Committed before any pass-2 number was computed.** Pass 1's failure was
that its power floor was a *count* floor. This pass fixes that, and is
the first thing in the repo to pre-register a power floor.

## Why a separate pass, not a pooled one

`backtest-2026-08-27-calharvest-weather` uses a **different decision
rule** from pass 1 (`calibration_harvest.screen`: both sides eligible,
signed cells, no days-to-close cap, dead middle excluded — versus
`insider_bias.screen`'s favorites 0.65–0.97 at first qualifying day).
Pooling them would make per-series bias partly an artifact of which rule
sampled which series. Pass 1's own Population section said this
population was "a separate future pass"; this is that pass, and its
results are **never pooled with pass 1's**.

## What changes from pass 1 (and only this)

1. **A power floor replaces the count floor.** A series is tested only
   if its minimum detectable effect `MDE = 2.8 × SE` is **≤ 5.0 points**
   — the low end of a theory-grade edge. A series that cannot resolve a
   bettable effect is *excluded from the family entirely*: it can only
   inflate the Holm correction and dilute the result. The number of
   series excluded on this ground is reported, because that count is the
   power story.
2. **The control is measured but excluded from the Holm family.**
   `mention_family` series (none expected in weather, but the rule
   stands) are reported separately.
3. Everything else — the day-clustered gross statistic, split-sample
   same sign, both halves ≥ 1.0 pt, `|t| ≥ 2`, Holm at α = .05 — is
   **unchanged from pass 1**.

Note the power floor is a *rule*, not a peek: it is stated here in
advance and the data decides who passes it. Reporting the MDE
distribution is what makes a null readable.

## What counts as what, fixed now

- **Confirmatory:** a series passing all four gates *and* the power
  floor. Its follow-on may only claim `edge_basis="measured"` after an
  out-of-population or forward test — never on this data.
- **Genuine negative:** ≥ 10 series clear the **power floor** and none
  is flagged. *That* would be evidence the population is calibrated,
  which pass 1 could not claim.
- **Not measured, again:** fewer than 10 series clear the power floor.
  Then weather is as underpowered as pass 1 was and the honest answer is
  the same — recorded now so it cannot be talked up later.

## Pass 2 result — one flag, in a pass my own bar calls "not measured"

```
series seen                 : 57
series clearing floors      : 28
  excluded: underpowered    : 27   (MDE > 5.0 pts)
series TESTED (power floor) :  1
FLAGGED (all gates)         :  1   KXLOWTLV
```

MDE over the 28 admitted: median **10.8**, best 4.9, worst 18.1. Only
**1 of 28** could resolve a 5-point effect; 12 of 28 could resolve 10.

**By the bar fixed above, this pass is "not measured, again"** — a
genuine negative required ≥10 series clearing the power floor, and one
did. The flag arrives inside a pass pre-declared uninformative, and that
framing is not negotiable after the fact.

### The flag, and it is statistically robust in-sample

`KXLOWTLV` (Tel Aviv daily low temperature), n=47 over 38 settlement
days, favorites at mean ask 0.882 realizing **0.957**:

| check | result |
|---|---|
| day-clustered gross | **+9.50** (net +8.83) |
| halves | +8.06 / +10.95 |
| t | **+5.44**, p < 1e-5 |
| days positive | **36 / 38**, sign test p < 1e-6 |
| jackknife (drop any 1 day) | t stays **+5.21 … +8.33** |
| drop 3 most extreme days | t **+8.48** — *stronger* |
| bootstrap over days, 10k | 95% CI **[+5.82, +12.59]**, P(≤0) = 0.0000 |

No single day drives it, it survives trimming, and the two
distribution-free checks (sign test, bootstrap) agree with the t-test.
It also clears Bonferroni over all 28 admitted series (0.05/28 = 0.0018)
by four orders of magnitude, so multiplicity is not the objection.

### Why it is still only a hypothesis — including a flaw in my own floor

1. **It arrives in a pass pre-declared "not measured".** One series is
   not a family, and the pre-registration said so before the run.
2. **The power floor is not outcome-neutral, which I did not anticipate
   when pre-registering it.** For a Bernoulli, variance is `p(1−p)`, so a
   series with an extreme win rate has a low SE and therefore a low MDE.
   The floor *preferentially admits extreme-win-rate series*, which is
   exactly where a large gap can sit if prices lag. Measured in this
   population: mean win rate **0.864** among MDE ≤ 8 series versus
   **0.829** among MDE > 8 — and `KXLOWTLV` at **0.957** is the most
   extreme series in the population *and* has the lowest MDE. Its
   admission to the family was not independent of its outcome.

   This tempers but does not erase it: the other low-MDE series show no
   comparable edge (`KXHIGHCHI` +1.89, `KXHIGHNY` +0.37, `KXHIGHMIA`
   −3.05), so low MDE does not mechanically produce a large gap.
3. **Thin day cells.** 47 rows over 38 days is ~1.2 rows/day, so most
   day-edges are a single Bernoulli draw minus an ask. The sign test and
   bootstrap carry the weight here, not the t.

### Not actionable today

`KXLOWTLV` has 6 markets open on the 2026-08-29 board (close
2026-08-30T08:00Z), and they do not present the trade: five are dust
(volume 5–98, books at 0.01/1.00) and the only liquid one
(`-T84`, volume 806) is at **yes_ask 0.98** — *above* the 0.97 cap of
the very screen that generated the population. There is no position here
at today's prices.

### The forward test, pre-registered now

Per the lesson from pass 1 and the peer's `KXRT` caution, fixed before
looking again:

- **Sign: positive** (favorites in `KXLOWTLV` realize *above* their ask).
  Fixed in advance so a negative result cannot be re-read as "a bias
  exists".
- **Population:** forward `KXLOWTLV` settlements only, entered under the
  same screen (favorite, ask ≤ 0.97).
- **MDE ≤ 5 pts**, day-clustered, which at this series' observed
  between-day SD needs roughly **35–40 settlement days**.
- **Confirmation** requires the day-clustered gross edge > 0 at 2 SE
  *and* ≥ 60% of days positive. Anything less is a failed forward test,
  reported as failed.

### Correction to the checklist advice

Backlog index step 0b (added today) says to pre-register a power floor.
That is still right, but it needs the caveat found here: **an SE-based
floor is not outcome-neutral for binomial data.** State it as a floor on
`n` and `n_days` where possible, or report the win-rate composition of
who passed, so the selection channel is visible rather than silent.

## Pass 3 collection — the combinatorial cap, pre-registered before pricing

The broad walk (`collect.py walk`) surfaced a population problem the
earlier passes never hit, so the rule is fixed here before any price is
fetched or any outcome computed.

`KXBTCD` settled **257,632** markets in the 60-day window — ~4,300 a day,
Bitcoin's price across many strikes times many intraday times. Priced
uncapped it would be 98% of all observations.

**Rule: price only series settling 40–1,000 markets in the window.**
Above the cap a series is a *combinatorial product*, not a recurring
series, and is excluded and **reported by name**. Three reasons, only one
of which is convenience:

1. **Thesis.** The hypothesis is habitual retail flow on a *recurring*
   series with stable behavioural biases. A 4,300/day grid is a different
   object and was never what the spec meant.
2. **Weighting.** One such series would supply the overwhelming majority
   of observations and dominate every pooled figure.
3. **Tractability.** Kalshi serialises candlesticks at ~4–5/s, so pricing
   `KXBTCD` alone is 14+ hours.

**Chosen after seeing the count distribution and before computing any
outcome.** That ordering is the whole point of today's repeated lesson:
an inclusion rule is part of the bar, so it is written down here, with
its reasons, and the excluded series are named rather than silently
dropped. Counts are not outcomes — but a reader is entitled to check
that claim, which is why the exclusions are listed.

## 2026-08-29 (session 3, item 5) — series-bias-mining: not measured, and my own bar was the defect (migrated from RESEARCH_LOG.md)

> Contributed verbatim by the parallel session `llm-market-identifier-4f`,
> which owned this build under the 2026-08-29 session split. Appended by
> `llm-market-identifier-18`, which owns this file for the day.

**Did:** Built backlog spec #4 as a **study, not a theory** (its §3: the miner
produces measurements, not bets). Pre-registered the bar and committed it
before computing any per-series number (`3fd3be5`); built and fixture-tested
the miner before it saw real data (`07291f0`); ran it once (`f826d6c`).
Study: `studies/2026-08-29-series-bias-mining/`. Suite **955** green.

**Learned:**

1. **17 series tested, 0 flagged, largest |t| 1.43 — and that is "not
   measured", not a negative.** Median minimum detectable effect **13.5 pts**
   against a theory-grade edge of 3–6; only 2 of 17 series could resolve a
   5-point effect. Finding nothing was the likely outcome either way.
2. **10 of the 17 tested series were the mention_family negative control**,
   so only seven real series were tested.
3. **My pre-registration was defective, in the same class as the politics
   read hours earlier.** It used *series count* as the power proxy; count
   says nothing about whether a series can resolve a 4-point effect. There
   the unstated rule was "≥3 bins per day"; here "count as power". **Naming
   the contrast is not enough — the power floor and inclusion rules are part
   of the bar.** Recorded in the study rather than re-bucketing the result.
4. **The fixture universe earned its keep before any real data.** Spec §9's
   planted-bias-among-calibrated test caught a genuine design bug: the
   statistic was net of fees, and fees are a ~constant −1 to −3pt offset, so
   a *perfectly calibrated* series scored −1.12 with the same sign in both
   halves and above the magnitude gate — every calibrated series would have
   flagged as persistently negatively biased, waved through by the very
   split-sample guard meant to stop it. Guard now scores gross; net reported
   beside it. Amended in the open.
5. **Three real results:** `KXAPRPOTUS` is genuinely calibrated (−0.06 ±
   0.29, MDE 0.8pts); the negative control behaved (all ten mention_family
   series non-significant on data known to be fairly priced); and `KXRT` is
   a candidate worth a powered test (−4.23 gross, halves −4.68 / −3.86, SE
   2.97) — pre-registered as a hypothesis, not bettable on this data.

**Next:** the blocker is data, not method. A dedicated broad settled-history
sweep, then re-run — budgeting for the per-series `list_settled` walk, not
the candlestick fetches. Pre-register a **power floor** (MDE ≤ 5pts), not a
count floor, and keep mention_family out of the Holm family.

## Pass 3 analysis bar — fixed 2026-09-01, BEFORE any per-series number

Pass 3's *collection* rule (the 40–1,000 combinatorial cap) was fixed
above before any price was fetched. This section fixes the *analysis*
bar, and it is written under the same discipline: at the time of writing
I had looked at exactly four numbers, all of them counts —
68,243 priced observations across 642 series, of which **358 clear the
n/n_days floors**, median n 115, median 13 settlement days. No win rate,
no ask mean, no edge, no split, no MDE has been computed on this
population. Counts are outcome-independent; that claim is checkable
because the collector computes `won` but this section quotes none of it.

### Population — and it is NOT passes 1–2's population

`data/collect.db`, phase-2 observations: every settled market in an
eligible series (40–1,000 settlements in the ~60-day archive window),
priced at **25% of scheduled lifetime before close**, favorite side, one
observation per market.

The difference from earlier passes is material and must not be papered
over when results are read:

| | passes 1–2 | pass 3 |
|---|---|---|
| population | `insider_bias/screen.py` survivors | **no screen** |
| price filter | favorites 0.65–0.97 | none — the favorite at whatever it costs |
| liquidity filter | spread ≤ 0.07, volume ≥ 500 | none |
| horizon | ≤ 14 days to close | any |
| decision point | first screen-qualifying day | 25% of scheduled lifetime |

So a bias found here generalizes to **"the favorite side of a recurring
series at 25% of its lifetime"** — not to any tradeable screen. Whether
such a bias is *bettable* is a separate question: it is reported net of
fees beside every gross figure, and it is never what the guard scores.

### Inclusion floors — outcome-neutral, and that is the point

Unchanged from pass 1, because they are pure counts: `n >= 40` and
`n_days >= 8`; alive in both halves at `n >= 15` and `n_days >= 3`.

### No MDE filter on admission — a deliberate reversal of pass 2

Pass 2 admitted only series with `MDE <= 5`, and then found the flaw
itself: **an SE-based floor is not outcome-neutral for binomial data.**
Variance is `p(1−p)`, so an extreme-win-rate series has a low SE and
therefore a low MDE, and the floor preferentially admits exactly the
series where a large price-vs-outcome gap can sit. Pass 2 measured the
channel (mean win rate 0.864 among MDE ≤ 8 versus 0.829 above it) and
`KXLOWTLV`, its one flag, was the most extreme-win-rate series in the
population *and* had the lowest MDE. Its admission to the family was not
independent of its outcome.

Pass 2's own correction says how to fix it: *"State it as a floor on `n`
and `n_days` where possible, or report the win-rate composition of who
passed, so the selection channel is visible rather than silent."*
**Pass 3 does the first, and reports the second.** Admission is by count
alone. This is affordable now and was not before: the power problem that
motivated the MDE floor was really a *breadth* problem, and 358 admitted
series is a different regime from 28.

The cost is paid honestly: a large family makes Holm severe
(0.05/358 ≈ 1.4e-4). That is the true price of testing hundreds of
series and it is not negotiable downward. For calibration, pass 2's
`KXLOWTLV` at p < 1e-5 would still clear Holm over a family this size —
so the correction does not, by construction, exclude a real effect of
the magnitude this study is looking for.

**The power-floored view is still reported, second and labelled.** The
`MDE <= 5` cut is run as a *secondary* view beside the primary, marked
as outcome-correlated in admission, so pass 2's numbers stay comparable.
The primary result is the outcome-neutral one.

### The Holm family, and the control

The family is **every admitted non-control series**. mention_family
series are excluded from the family and measured separately as the
negative control — spending correction budget on series nobody would
promote only dilutes the result, and their behaviour is the check on
whether the guard is too loose (pass 1: all ten non-significant, as they
should be on data known to be fairly priced).

### When this pass counts as "measured"

Fixed now, because passes 1 and 2 both had to declare themselves
uninformative *after* running and that is only credible when the bar
predates the data:

> This pass is **informative** iff at least **30 non-control series**
> clear the floors **and** the median MDE over admitted series is
> **≤ 8 points**. Otherwise it is "not measured" again, whatever it
> flags.

The count condition is already met on the partial collection (358); the
MDE condition is not yet knowable and is deliberately left as a real
gate rather than a formality.

**This is the first pass able to state a genuine negative.** If ≥30
series are tested at median MDE ≤ 8 and nothing flags, that is evidence
*against* persistent per-series bias in recurring Kalshi series at this
decision point — a real finding, not an absence of one. Passes 1 and 2
could never have said that.

### The flag — four gates, unchanged

Split-sample same sign; both halves ≥ 1.0 pt **gross**; `|t| >= 2`;
survives Holm-Bonferroni over the family. Gross, not net, per the
2026-08-29 amendment: fees are a ~constant −1 to −3 pt offset, so a
net-scored guard flags every calibrated series as negatively biased.

### Pre-registered signs for the two carried candidates

Both arrive from earlier passes and are genuinely out of sample here —
different population, different decision point, different screen. Their
signs are fixed **now**, so that a result of the opposite sign cannot be
re-read as "a bias exists":

- **`KXRT`** (Rotten Tomatoes): **negative** — pass 1 gave −4.23 gross,
  halves −4.68/−3.86. Pass 1's own caution stands and is repeated: those
  halves came from the same 11 settlement days, so the split guarded
  against regime change, not against noise.
- **`KXLOWTLV`** (Tel Aviv daily low): **positive** — pass 2 gave +9.50
  gross, t +5.44, 36/38 days positive.

Confirmation for either requires the pre-registered sign, `|t| >= 2`,
and Holm survival in the pass-3 family. A flag of the opposite sign is
reported as a **failed** forward test for that series, not as a finding.

### What is deliberately NOT decided here

Nothing in this pass promotes anything to a theory. Survivors become
pre-registered proposals for follow-on theories, on a forward or
out-of-sample population — never bets on the data that suggested them.

### Robustness views — declared now, still before any per-series number

Two strata exist in the collected data for free, and *choosing to look at
them after seeing the headline would be exactly the post-hoc move this
study keeps catching itself in*. Both are therefore fixed here. Again the
only numbers consulted are counts: 69,236 observations, of which 51,604
carry the alternative decision point across 611 series, and 47,497
(**68.6%**) are flagged `early_settled`.

1. **The alternative decision point.** `collect.py` priced every market
   at *both* 25% of scheduled lifetime and the original pre-registered
   24h-before-scheduled-close, from the same candles at no extra API
   cost — deliberately, so the 2026-08-29 amendment could be *measured*
   rather than argued. A flag that survives at both decision points is a
   property of the series; one that appears at only one is a property of
   the timing choice, and must be reported as such. `ask_24h` is NULL
   where the market lived under 24h, so this view runs on a subset and
   its family is re-corrected over that subset, never borrowed.

2. **Early settlement.** 68.6% of observations come from markets whose
   observed close ran ahead of the scheduled one. The decision point is
   already anchored to *scheduled* close precisely so the information
   state is not a function of the answer — that is the lookahead bug
   that flipped `deadline_drift`'s sign (−3.4 → +4.7) and it is fixed
   here by construction, not by inspection. What is still open is
   whether the measured bias *differs* between early- and on-time
   settling markets. Reported as a split, on the pre-registered reading
   that **a flag driven only by the early-settling stratum is suspect**
   and is reported as such rather than as a find.

Neither view can promote anything on its own. They exist to say whether
a headline flag is robust, and a flag that fails both is reported as
fragile.

### The population is whatever the sweep has finished

Phase 2 is resumable and per-series atomic: a series is either fully
priced and recorded in `progress`, or absent. So the family grows by
*adding series*, never by revising one — but a larger family means a
harsher Holm divisor, so two runs over two collection states are two
different tests. To keep that from becoming a choice made after seeing
both, the rule is fixed here: **the reported primary result is the run
on the collection state at the moment the sweep stops**, whether it
stopped by completing or by running out of session. Any earlier
execution is a smoke test of the pipeline, and its per-series numbers
are not reported.

### The family is size-truncated, and that is disclosed, not discovered

`eligible_series` walks **ascending by settled-market count**, on the
collector's own reasoning: phase 2 is ~174k candle fetches at Kalshi's
~4–5/s, so it *will* be interrupted, and cheapest-first maximises the
number of **complete** series at any stopping point — a series is the
miner's unit of analysis and half of one is worth nothing to it.

The consequence for pass 3, stated before the run: **the tested family is
the smaller half of the eligible population.** Settlement count is not an
outcome, so this does not admit on the answer the way pass 2's MDE floor
did — but it is not neutral with respect to *kind*, because a series
settling 800 markets in 60 days is typically a daily or intraday product
and one settling 50 is typically weekly or event-driven. So a pass-3
result generalizes to **lower-frequency recurring series**, and the
high-frequency tail is *unmeasured*, not measured-and-null.

The stopping point is recorded with the result, and the remaining series
stay on disk in `progress` for a later pass to extend rather than redo.

## Pass 3 result — NOT MEASURED, and the negative control is why

Run 2026-09-01 against `data/pass3-frozen.db`, a snapshot taken while the
sweep continued: **658 series priced, 69,874 observations, 648 series
with usable rows.** One run, on one frozen population, per the rule
above.

```
series clearing floors      : 358   (of which 11 mention control)
series TESTED (Holm family) : 347
expected false positives    : 17.4
median MDE over tested      : 12.16 pts

PRE-REGISTERED 'MEASURED'?  : NO -- not measured
                              (needs >=30 tested AND median MDE <=8.0)
FLAGGED (all four gates)    : 9
```

**The count gate passed and the power gate failed.** 347 tested against a
floor of 30 — the breadth problem is solved, and this is the first pass
with a real family. But median MDE is **12.16** against a bar of 8.0, so
by the criterion fixed before the data this pass is *not measured*, for
the third time running. Breadth was necessary and was not sufficient:
the median series here still cannot resolve a theory-grade 3–6 point
effect.

### Nine flags, and none of them is a finding

The four gates fired on nine series, most of them enormous:

| series | n | days | gross | t | p |
|---|---|---|---|---|---|
| KXNFL4Q | 141 | 10 | −10.18 | −12.48 | 5.5e-07 |
| KXNPBRFI | 204 | 38 | **−40.85** | −11.46 | 1.0e-13 |
| KXATPCHALLENGERDOUBLES | 276 | 15 | −26.09 | −8.02 | 1.3e-06 |
| KXUELFTTS | 162 | 10 | −24.74 | −7.45 | 3.9e-05 |
| KXT20TEAMTOTAL | 113 | 13 | −33.54 | −7.25 | 1.0e-05 |
| KXKBORFI | 188 | 42 | −25.47 | −6.67 | 4.9e-08 |
| KXNFL2H | 141 | 10 | −9.69 | −6.53 | 1.1e-04 |
| KXCPLTEAMTOTAL | 93 | 16 | **−44.97** | −5.95 | 2.6e-05 |
| KXATP | 77 | 36 | +5.91 | +5.46 | 3.9e-06 |

A −45 point systematic bias is not a bias. **The negative control says so
independently**: 5 of the 11 admitted mention_family series trip the
split-sample and t gates. Pass 1 ran the same control on the screened
population and *all ten* came back non-significant. Same series, same
statistic, different population — so what changed is the population, and
a flag here cannot be read as a property of a series.

This is the control earning its keep. Pass 1 wrote that a flag among the
control means "the guard is too loose"; this is the first pass where that
sentence has had to be cashed.

### The mechanism: without a liquidity filter the ask is not a price

The gap grows monotonically with the ask, across all 69,874 observations:

| ask band | n | mean ask | realized | gap |
|---|---|---|---|---|
| 0.50–0.70 | 15,799 | 0.606 | 0.581 | −2.6 |
| 0.70–0.80 | 11,528 | 0.746 | 0.713 | −3.3 |
| 0.80–0.90 | 11,395 | 0.845 | 0.801 | −4.4 |
| 0.90–0.95 | 7,668 | 0.922 | 0.863 | −5.9 |
| 0.95–0.98 | 7,238 | 0.961 | 0.883 | −7.7 |
| **0.980–0.995** | **16,075** | **0.987** | **0.801** | **−18.6** |
| 0.995–1.01 | 171 | 0.999 | 0.988 | −1.1 |

**23% of the population sits in that 0.980–0.995 band**, priced at 0.987
and realizing 0.801. That is not a market that is wrong by 18 points; it
is a market with no offer, whose top-of-book ask is a placeholder. Thin
history says the same thing from another angle: markets with under 10
candles show −16.9, against −3.0 for those with 500+.

Passes 1–2 never saw this because their population came through
`insider_bias/screen.py`, which requires **spread ≤ 0.07 and volume ≥
500**. Pass 3 dropped the screen to widen the population and dropped the
liquidity filter with it. Capping the ask confirms the direction and also
its limits:

| ask cap | admitted | tested | flagged | control tripping |
|---|---|---|---|---|
| none | 358 | 347 | 9 | **5 / 11** |
| ≤ 0.98 | 322 | 311 | 7 | 6 / 11 |
| ≤ 0.95 | 288 | 279 | 4 | **2 / 9** |
| ≤ 0.90 | 269 | 260 | 3 | 2 / 9 |

So the extreme-ask band explains roughly *half* the problem and not all
of it: at a 0.95 cap the control still fires on two series. **The residue
cannot be diagnosed from what was collected**, because a price cap is a
poor proxy for a liquidity filter and the real fields were never stored.

### The defect, and it was a data-conventions failure

`tools/kalshi/history.candlesticks` returns `yes_bid_close`, `volume` and
`open_interest`. `collect.py` fetched all three, used the bid to pick the
favorite side, and **persisted only the derived ask** — distilling at
write time and discarding the fields that turned out to decide whether
the distillate meant anything. CLAUDE.md's rule is raw payloads over
distillates precisely against this, and the cost is not theoretical:
re-deriving them means re-fetching candles Kalshi archives ~60 days after
close.

Fixed the same day (`3cc5317`): `spread`, `volume`, `open_interest` and
`spread_24h` are captured at the decision point. The running sweep was
**stopped mid-flight** to land it, since every further series priced
without the fields would have been another to re-fetch inside a window
that closes. Additive migration; the 660 series already priced read NULL
and are a backfill ticket, not a silent rewrite.

### The carried candidates

- **`KXRT`**, predicted **negative**: −2.76 gross, t −0.76, p 0.47, n=262
  over 9 days. Right sign, nowhere near significance — **not confirmed**,
  and pass 1's caution stands. It remains a hypothesis.
- **`KXLOWTLV`**, predicted positive: **not in the admitted family** this
  pass — it does not clear the count floors in this population. Untested,
  not refuted.

Neither prediction is resolved, and neither is re-read in light of the
result.

### What pass 3 actually establishes

1. **The breadth problem is solved.** 347 tested versus pass 1's seven
   and pass 2's one. The collector works, is resumable, and the family is
   now large enough that Holm is the binding constraint rather than
   sample size.
2. **Breadth alone does not make a population measurable.** Median MDE
   12.16 says the median recurring series still cannot resolve a
   theory-grade effect at 60 days of history. More series did not fix
   that and more series will not; only longer per-series history will.
3. **A population without a liquidity filter cannot be mined for bias**,
   and the negative control detects that on its own. This is the most
   useful thing the pass produced, and it is a *method* result rather
   than a market result.
4. **Nothing here is promotable.** No follow-on theory is proposed on
   these nine flags. Any of them may be real; none can be told apart from
   the artifact with the fields on hand.

### Pass 4, pre-registered now

Same bar as pass 3 with one addition, fixed here before the data exists:
**observations must carry a tradeable book at the decision point** —
`spread <= 0.07` and `volume >= 500`, the same thresholds
`insider_bias/screen.py` uses, so pass 4's population is the broad sweep
under passes 1–2's liquidity standard rather than a third thing. The
negative control is the acceptance test: **if mention_family still trips
the gates under that filter, the population is still wrong and pass 4 is
not measured either**, whatever else it flags.
