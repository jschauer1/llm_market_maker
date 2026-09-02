---
title: Parlay markup — do Kalshi's cross-game parlays price above the product of their legs?
lane: study
created: 2026-08-30
created_by: migration
---

# Parlay markup — pre-registration, written BEFORE any markup number

**Date:** 2026-08-30 ·
**Tier:** A (no model anywhere) ·
Backlog spec #8, registry slug `parlay-fade`

**This bar was written before a single calibration or markup figure was
computed.** At the time of writing I had looked at exactly four things:
which multivariate series exist, their collection counts, the leg-count
distribution of one 25,000-row sample, and two individual settled
payloads read to learn the schema. No win rate, no price-vs-outcome
comparison, no split by leg count.

That ordering is the whole point. The backlog index's rule 0b was
written after two failures on 2026-08-29 — `calibration_harvest` chose a
two-group collapse after seeing where the sign flipped, and
`series-bias-mining` used series *count* as a power proxy so that "0 of
17 flagged" meant *not measured* rather than *calibrated*. Both were
pre-registrations that named a contrast but not their inclusion rules or
their power floor. This file names all three.

## Why this is a study and not a theory

`Theory` is for things that produce bets. This produces a measurement:
whether Kalshi parlays are mispriced, by how much, and in which
direction. If it survives, the follow-on is a separate theory with its
own pre-registration and its own forward test — never a bet on the data
that selected it.

## What the spec assumed, and what is actually true

The `parlay-fade` spec (2026-08-24) carried one blocking unknown:
*"verify endpoint at implementation"* — whether Kalshi exposes combo
markets at all. Resolved 2026-08-30, and the answer changes the design:

- `/multivariate_event_collections` is **public and unauthenticated**.
- Settled parlays carry `mve_selected_legs` (exact leg tickers **and**
  sides), `last_price_dollars`, `open_interest_fp`, and `result`.
- The population is large: ≥25,000 settled in `KXMVECROSSCATEGORY`
  alone, 24,811 with non-zero open interest, leg counts 2–23.

**The consequence for the design: the spec's central comparison is not
the cheapest way to answer its own question.** The spec proposed parlay
price versus the product of contemporaneous leg prices, which needs a
candlestick fetch per leg per parlay — order 100,000 fetches, and every
one of them a chance to introduce a stale-mark artifact the spec itself
flags as its main lookahead trap.

Every settled parlay already carries **both its traded price and its
realized outcome**. So the primary question — *are parlays overpriced?* —
is answerable by direct calibration, with zero leg fetches and zero
timestamp alignment. Product-of-legs is demoted to a **mechanism** check
(phase 2, on a sample), because it answers a different question: whether
a markup is a product-level phenomenon or just leg miscalibration.

## Population

Settled multivariate markets, collected by
[`collect.py`](collect.py) into `data/collect.db`.

The series name partitions the population mechanically — no judgment, no
LLM, no reading of rules text:

| population | series | legs | product-of-legs is fair value? |
|---|---|---|---|
| `cross_game` | `KXMVECROSSCATEGORY`, `KXMVECROSSCATEGORY-SHARD1`, `KXMVE{NFL,NBA,SPORTS}MULTIGAME*` | across games | **yes** — near-independent |
| `same_game` | `KXMVENBASINGLEGAME`, `KXMVENFLSINGLEGAME` | one game | **no** — genuinely correlated |
| `other` | Grammys, Oscars, mentions, championship | mixed | not used |

`cross_game` is the tested population. `same_game` is the **negative
control** in the sense rule 0c requires — a slice whose answer is already
known. Correlated legs *must* make a same-game parlay deviate from
product-of-legs; if my phase-2 machinery reports same-game as
independent, the machinery is broken, not the market.

**Note the control runs the opposite way from `series-bias-mining`'s.**
There the control was known-fairly-priced and had to come back null.
Here the control is known-*not*-independent and has to come back
deviating. A control that cannot fail is decoration; this one can.

## Inclusion rules (fixed now, before any result)

A parlay row is included only if **all** hold:

- `population = 'cross_game'`
- `result` in (`yes`, `no`) — genuinely settled, not voided
- `open_interest > 0` — somebody actually held it. Zero-OI rows are
  minted-but-never-traded quotes and are not evidence about pricing.
- `last_price` strictly inside (0, 1) — a price of exactly 0 or 1 is not
  a forecast.
- `n_legs` between 2 and 12. Above 12 the price is so close to zero that
  a one-tick minimum increment dominates the arithmetic; 13+ is reported
  separately and never pooled into the headline.

Rows failing these are counted and reported by reason, never silently
dropped.

## The statistic

**Day-clustered calibration edge, gross**, in percentage points:

- one observation per **settlement day** = `mean(won) − mean(last_price)`
  over that day's included parlays;
- the estimate is the mean over days, SE the between-day standard error,
  `t = mean / SE`.

Day-clustered because parlays are the *worst* case for row-level
independence in this repo: they settle in tight clumps by game slate,
**and they share legs with each other** — hundreds of parlays on one
Sunday can all contain the same team's moneyline. Row-counted errors
here would be meaningless, and this repo has already been bitten by
exactly that four times (`buckets.py`, `no_side_premium` cell B,
`insider_judgment`'s pooled scores, `calibration_harvest`'s Wilson
bound).

Scored **gross**, per `series-bias-mining`'s amendment: fees are a
near-constant negative offset, so scoring a *bias* net of fees would
manufacture a consistent negative sign in both halves of any split and
sail through the very guard meant to catch it. Net is computed and
reported beside it for the separate question of whether the bias is
bettable.

**Shared-leg dependence is not fully handled by day clustering**, and I
am recording that limit now rather than discovering it later: two
parlays on the same slate sharing four of five legs are nearly the same
bet. Day clustering treats a slate as one observation, which is the
right unit for *time* correlation but still understates within-slate
leg-sharing. The honest reading is that the reported SE is a **lower
bound** on the true uncertainty. A leg-overlap-aware bootstrap is the
follow-up if the headline is significant.

## Pre-registered direction

**Parlays are overpriced: realized win rate is BELOW the traded price,
so the calibration edge is NEGATIVE, and its magnitude GROWS with leg
count.**

Fixing the sign in advance matters more than anything else here. Without
it, a result in *either* direction reads as "a bias exists" and the
hypothesis becomes unfalsifiable — the exact failure the
`series-bias-mining` revisit note called out. A positive edge
(parlays *under*priced) is a **failed** prediction, not a discovery,
and will be reported as such.

The leg-count gradient is a **secondary** prediction and is reported
separately with its own test. It does not get to rescue the headline if
the headline fails: a rejected primary with a surviving secondary is a
hypothesis for a new population, never a finding.

## Power floor (stated before running, per rule 0b)

The headline runs only if the design can resolve a **3-point** effect —
the low end of a theory-grade edge in this repo. Concretely: report the
minimum detectable effect (≈ 2.8 × SE) for the pooled cross-game
estimate and for each leg-count bucket, **before** interpreting any
point estimate. A bucket whose MDE exceeds 3 points is reported as *not
measured*, never as *calibrated*.

**The caveat from the backlog index applies and is not solved by this
floor.** Bernoulli variance is `p(1−p)`, so an MDE floor preferentially
admits low-priced buckets — and high-leg parlays are exactly the
low-priced ones. That means an MDE floor would *select for* the leg
buckets where the thesis predicts the biggest effect, which is a
selection channel pointed straight at my own secondary prediction. So:
the floor is applied **only** to the pooled headline, leg buckets are
reported at whatever power they have with the MDE printed beside each,
and the outcome composition of every bucket is shown so the channel is
visible rather than silent.

## What counts as what

- **Confirmatory:** pooled cross-game calibration edge is negative,
  `|t| ≥ 2`, and MDE ≤ 3 pts. Then the markup is real in this
  population, and the follow-on theory is about *capturing* it — which
  is a separate and much harder question (see kill criterion below).
- **Failed prediction:** edge is positive, or indistinguishable from
  zero at adequate power. Recorded as a failure of the spec's thesis on
  Kalshi, which is a real result: the arXiv finding would not have
  replicated here.
- **Not measured:** MDE > 3 pts. The answer is "underpowered", not
  "calibrated" — the mistake `series-bias-mining` made and named.

## The kill criterion that likely decides this — measured 2026-08-30

The spec's own kill criterion #7: *"If the observed gap is
quoted-but-never-traded, the edge is theoretical; measure fill-side
volume before claiming anything."*

**Measured, and it is flashing.** Across all three currently-open
collections, `active_quoters` is **0 on all 2,134 associated events**
(6,402 event slots total). There is no resting fade-side liquidity to
sell into.

So even a confirmed markup may be **unbettable by this user**, who
places orders manually and cannot respond to an RFQ within seconds. This
is recorded here, in the bar, so a positive result cannot later be
written up as a live opportunity without confronting it. A measurement
that a market is mispriced and a claim that the user can profit from it
are different claims, and this study only ever produces the first.

## Known limits, fixed now

- **`last_price` is not necessarily an executable price**, and is
  certainly not an ask. It is the last trade. Calibration against it
  measures whether *transacted* parlay prices were fair, which is the
  right question for "is there a markup" and the wrong one for "what
  would I have paid." Entry-price realism belongs to the follow-on
  theory, not here.
- **Survivorship:** Kalshi ages settled markets out at ~60 days, so the
  window is recent by construction and cannot be extended backwards. The
  collection is a snapshot of what was reachable on 2026-08-30.
- **In-sample throughout.** Any pattern found is a hypothesis for a
  forward test, and the forward test is the follow-on theory's job.

---

# Result — phase 1 (run 2026-08-30, after the bar was committed at `e5514a2`)

```
POPULATION: cross_game  (partial collection: 503,000 rows, sweep still walking back)
  included        : 395,692
  excluded        : n_legs>12 46,910 | open_interest<=0 3,657 | result='scalar' 1,741

  settlement days : 18
  mean last_price : 0.1732
  realized win    : 0.1444
  edge (gross)    : -5.19 pts
  SE / t          :  4.09 / -1.27
  MDE (2.8*SE)    : 11.44 pts     (pre-registered power floor: 3.0)
  VERDICT         : NOT MEASURED
```

The point estimate is signed the way the bar predicted (parlays
overpriced) and is not close to significant. Every leg-count bucket is
noise: `|t|` never exceeds 1.58, and bucket MDEs run 7.7–20.4 pts.

**This is "not measured", exactly as the bar defines it — not
"calibrated", and not "the markup is absent".** Recording it under the
pre-registered label rather than the more interesting one is the whole
reason the label was fixed in advance.

## The finding is not the point estimate. It is that this design cannot work.

395,692 rows produced **18 clusters**. The row count is an illusion of
power: on any given slate, every parlay shares legs with hundreds of
others, so when the favorites win, they nearly all win together. That
common shock is the dominant term, and day-clustering — correctly —
refuses to count it more than once.

The between-day standard deviation is **17.35 pts**. Turning that into a
requirement:

| target MDE | settlement days needed |
|---|---|
| 3 pts (the pre-registered floor) | **262** |
| 5 pts | 94 |
| 6 pts | 66 |

| days available | achievable MDE |
|---|---|
| 20 | 10.9 pts |
| 60 (Kalshi's retention ceiling) | **6.3 pts** |

**Kalshi ages settled markets out of the public API at ~60 days.** So the
best this design can ever do on this data source is an MDE of ~6.3
points — twice the low end of a theory-grade edge, and it would still be
reported as "not measured" under this study's own bar.

Outcome-based calibration of parlays is therefore **structurally
underpowered on Kalshi**, and no amount of additional collection fixes
it. That is a property of the population, not an accident of this
sample. Collecting the remaining history is still worth doing (the data
is perishable and feeds phase 2), but it will not rescue this statistic.

## Correction: my design change was wrong, and the spec's instinct was right

The bar above demoted product-of-legs to a "phase 2 mechanism check" on
the grounds that calibration answers the primary question more cheaply.
Cheaper, yes. Able to answer it, no.

The reason is one the spec never stated and I did not see until the
variance appeared: **product-of-legs is an outcome-free measurement.**
Comparing a parlay's price to the product of its legs' contemporaneous
prices never touches a realized result, so the day-level common shock
that destroys the calibration statistic — did the favorites win today —
cannot enter it at all. Its precision is limited by leg-price
availability, not by how many days happened to settle.

So the ordering is inverted from what this file pre-registered:

- **Primary (phase 2):** markup = `parlay_price − Π(leg prices)` at
  matched timestamps. Outcome-free, high precision, tier A.
- **Secondary:** calibration against realized outcomes — retained only as
  a sanity check on whether product-of-legs is itself fair value, and
  reported with its MDE so it is never read as a null.

This is recorded as a correction rather than applied silently, and it
does not touch the pre-registered *direction* (parlays overpriced) or
the inclusion rules, both of which carry over to phase 2 unchanged. What
changes is which statistic is the headline — and it changes because the
data showed the chosen one cannot resolve a bettable effect, which is
the resize-before-you-run response rule 0b asks for, arriving one step
late.

**Phase 2 is tractable, and much cheaper than the spec assumed.** The
naive cost is ~400k parlays × ~4 legs of candlestick fetches. But
parlays on one slate draw from a small shared pool of underlying game
markets, so the distinct-leg count is bounded by the slate (order
thousands, not millions). Fetch each distinct leg's candles once, then
price every parlay that references it.

## Fixture note (rule 0d)

The fixtures caught a defect — in the fixture, not the estimator. The
first version gated a single simulated draw at ±1.5 pts when the
between-day SE at that size is ~1.05 pts, so it fired on a genuine
3-sigma draw and reported FAIL. A single-draw tolerance test is itself
an underpowered test: the same class of error as judging a series by
count instead of power. Replaced with an unbiasedness check across 60
seeds (mean −0.177 pts) plus a detection-rate check on a planted −8 pt
effect (recovered −8.04, detected 100%).

One residual, recorded rather than fixed: the calibrated fixture trips
`|t| ≥ 2` about **10%** of the time, not the nominal 5%. The t
approximation runs liberal at these cluster counts and skewed per-day
distributions, so `|t| ≥ 2` is a slightly weak bar. It did not matter
here — nothing came close — but a phase-2 result near the threshold
should use a cluster bootstrap rather than the t.

---

# Phase 2 pre-registration — written BEFORE any markup number

Phase 1 established that outcome-based calibration cannot resolve a
bettable effect on this data source (262 settlement days needed, ~60
reachable). Phase 2 is the outcome-free measurement that replaces it as
the headline. **Written and committed before any leg price was
fetched.**

## The statistic

For each parlay, at its own `created_time`:

```
markup_pts = 100 * ( parlay_last_price  -  PROD(leg_mid_i) )
```

- **Leg price is the mid**, `(yes_bid_close + yes_ask_close) / 2`, from
  the hourly candle at or before `created_time`. Mid-to-mid is the
  spec's own choice and is the right one here: `last_price` on the
  parlay is a *traded* price, so comparing it to leg *asks* would charge
  the parlay side a spread the leg side never paid and manufacture a
  markup out of bid-ask asymmetry alone.
- **A leg's side is honoured.** `mve_selected_legs` carries `side`; a
  `no` leg contributes `1 - mid`, not `mid`. Ignoring side would
  scramble the product entirely.
- **Never a candle after `created_time`.** The candle used is the last
  one ending at or before it. This is the spec's named lookahead trap
  (stale leg marks manufacture fake gaps), and it is the only place
  phase 2 can leak.

## Inclusion (in addition to phase 1's rules, which carry over unchanged)

- Every leg must have a candle at or before `created_time` with both
  `yes_bid_close` and `yes_ask_close` present. A parlay with **any**
  unpriceable leg is excluded whole — never priced on a subset of its
  legs — and excluded parlays are counted and reported.
- Leg mid must be strictly inside (0, 1).
- The candle must be no more than **24 hours** before `created_time`.
  A staler mark is not a contemporaneous price.

## Clustering

Report **both**, always as a pair, never one alone:

- **day-clustered** — one observation per creation day;
- **slate/leg-aware** — parlays sharing legs are not independent even
  within a day, so also report the markup aggregated to one observation
  per distinct **leg-set signature** before averaging.

Phase 1's lesson is that the row count is an illusion of power; phase 2
must not repeat it just because its statistic is quieter.

## Pre-registered direction (unchanged from phase 1)

**Parlays are overpriced relative to the product of their legs:
`markup_pts > 0`, growing with leg count.** A negative markup is a
FAILED prediction, not a discovery.

## Power floor

Same 3-point floor, same MDE reporting. Phase 2's precision is not
limited by settlement days, so if this design is also underpowered, the
thesis is unanswerable with Kalshi data and the study says so.

## The control, and what it is for

`same_game` parlays (`KXMVENBASINGLEGAME`, `KXMVENFLSINGLEGAME`) have
genuinely correlated legs, so product-of-legs is **not** fair value
there and they **must** show a large positive markup for a reason that
is not a markup at all — it is correlation. Running them through the
identical machinery is the check that the machinery works: if same-game
comes back at zero, the pipeline is broken. It is **not** evidence about
the thesis, and it is kept out of the headline entirely.

## Known limits, fixed now

- `last_price` is the parlay's last *trade*, whose timestamp is not
  necessarily `created_time`. For a market minted via RFQ and traded
  immediately, the two are close; for one that traded later, the leg
  prices may be stale relative to the trade. This is the largest
  unquantified error in phase 2, and it biases in an unknown direction.
  A follow-up should restrict to parlays whose trade and creation are
  provably close once a timestamp for the trade is available.
- Hourly candles, not minute. A leg that moved sharply inside the hour
  is mispriced by up to that hour's range.

---

# Result — phase 2, first slate (2026-08-11 creations)

```
1,200 parlays sampled -> 1,083 priced, 117 excluded (no candle at or before created_time)
1,084 distinct legs fetched, 26,110 hourly candles, 0 fetch errors

  mean parlay price    : 0.1646
  mean product-of-legs : 0.0861
  markup               : +7.85 pts
  legset-clustered     : +7.85 pts, t=+15.92, k=1083, MDE=1.38
  day-clustered        : k=1 -- no SE obtainable from one day
```

Every leg-count bucket is positive and individually significant.

## The spread confound, tested and survived

A +7.85 pt markup on a mean price of 0.16 means parlays trade at nearly
**twice** the product of their legs. An effect that large should be
attacked before it is believed, and the obvious suspect is that leg
bid-ask spreads **compound multiplicatively**: a product of *mids*
understates what replication actually costs, by more and more as legs
are added.

Tested directly on the cached quotes, repricing each parlay against the
side you would actually pay (YES legs at their ask, NO legs at
`1 − yes_bid`):

| benchmark | markup |
|---|---|
| product of leg **bids** | +8.20 pts |
| product of leg **mids** | +7.85 pts |
| product of leg **asks** (conservative) | **+7.44 pts** |

`product(asks) / product(mids)` averages **1.116** — so spread
compounding is real but accounts for only **0.41 pts** of the 7.85. The
finding survives its most conservative benchmark.

## What this is NOT yet

**One creation day. `k = 1`.** The leg-set clustering reports k=1083 and
t=+15.92, and that number should not be trusted on its own: leg-sets
within a single day share underlying legs heavily, so they are not 1,083
independent observations of anything. Phase 1's entire lesson was that a
large row count can be one cluster wearing a crowd's clothes, and
repeating that mistake here — with a *quieter* statistic and a much
more attractive result — would be the same error in a more tempting
costume.

Ruling 14 (recorded 2026-08-30: a calibration figure spanning fewer than
three settlement days triggers no lifecycle action) applies here in
spirit. Until several creation days are pooled and the **day-clustered**
number holds, this is a promising single slate, not a measurement.

Additional limits still outstanding, unchanged from the phase-2 bar:

- `last_price` is the last *trade*, whose timestamp need not equal
  `created_time`; leg marks may be stale relative to the trade in an
  unknown direction. This remains the largest unquantified error.
- 117 of 1,200 (~10%) were excluded for an unpriceable leg. If those are
  systematically the illiquid ones, the surviving sample is biased
  toward liquid legs — direction unknown.
- Selection: a parlay exists because somebody asked for it. This
  measures the markup on parlays people *wanted*, which is the right
  population for "is retail paying a markup" and the wrong one for "is
  every possible parlay overpriced".

---

# Result — phase 2 pooled (4 creation slates)

```
3,231 parlays priced across 4 creation days

  markup vs product-of-MIDS
    day-clustered    : +7.06 pts   t=+17.47   k=4   MDE=1.13
    legset-clustered : +7.09 pts   t=+24.81   k=3231 MDE=0.80

  markup vs product-of-ASKS (buy every leg at the side actually payable)
    day-clustered    : +6.64 pts   t=+16.10   k=4   MDE=1.15

  per-day: 2026-08-06 +6.87 | 08-07 +6.01 | 08-09 +7.51 | 08-11 +7.85
```

`k=4` gives 3 df, where the two-sided 95% critical value is 3.18. The
day-clustered `t` of 17.47 clears it by a wide margin, the MDE of 1.13
pts is well inside the pre-registered 3-point floor, and **all four days
are positive with a tight range (6.01–7.85)**.

## VERDICT: CONFIRMATORY on the primary prediction

Kalshi cross-game parlays trade materially above the product of their
legs. The effect survives the benchmark that would most easily have
manufactured it — leg bid-ask spreads compounding multiplicatively — at
+6.64 pts when every leg is priced at the side you would actually pay.

## VERDICT: FAILED on the secondary prediction, as literally written

The bar said the markup's *magnitude* **grows** with leg count. In
percentage points it does the opposite, and strongly:

| legs | n | parlay | product | markup pts | ratio |
|---|---|---|---|---|---|
| 2 | 354 | 0.3531 | 0.2481 | **+10.50** | 1.42x |
| 5 | 439 | 0.1634 | 0.0711 | +9.23 | 2.30x |
| 8 | 212 | 0.0716 | 0.0269 | +4.47 | 2.66x |
| 12 | 95 | 0.0268 | 0.0093 | **+1.75** | 2.87x |

`corr(legs, markup in points) = −0.920`. The pre-registered claim was
positive. **It failed, and it is recorded as failed.**

In *ratio* terms the gradient does run the predicted way
(`corr = +0.682`; buyers pay 1.42x fair value on a 2-leg and ~2.9x on a
12-leg). That framing is **not** what this study pre-registered, so it
is a hypothesis for a separate pre-registered test, not a rescue of the
failed one. Recording the distinction rather than quietly switching
units is the whole discipline — swapping the metric after seeing the
sign is exactly what `calibration_harvest` was retracted for on
2026-08-29.

**And the points reading is the economically relevant one for a fader.**
What a seller captures is points per contract, not a ratio. So the
usable form of this result inverts the spec's expectation: the largest
absolute edge sits in **short (2–5 leg) parlays**, not the long
lottery-ticket ones the thesis and the source paper emphasise.

## What would still have to be true for this to become a theory

The measurement is not the bet, and on current evidence the gap between
them is the whole problem.

1. **There is no fade side.** `active_quoters` is 0 across all 2,134
   associated events in all three open collections. Capturing a markup
   means *selling* parlays to the people paying it, which means
   answering an RFQ within seconds — a workflow this user (manual,
   human-hours) does not have. The spec's own kill criterion #7
   anticipated exactly this.
2. **The `last_price` timing gap is still unquantified.** `last_price`
   is the last *trade*; leg marks are taken at `created_time`. For an
   RFQ minted and immediately traded these coincide, but nothing here
   proves they do, and it remains the largest unmeasured error.
3. **~10% of parlays are dropped** for an unpriceable leg. If those are
   the illiquid ones, the measured population is biased toward liquid
   legs by an unknown amount.
4. **The control was never run.** `same_game` parlays were specified as
   the machinery check and only `cross_game` was collected. Note the
   control is weaker than hoped in any case: positively correlated legs
   make `P(all legs win) > Π(legs)`, so same-game *should* show a large
   positive gap for a reason that is not markup — meaning it cannot
   cleanly separate "machinery works" from "correlation". A better
   validation is a leg-count-1 case, which the exchange does not offer
   (`size_min = 2`).

So the honest status is: **a real, robustly measured mispricing that
this user probably cannot trade.** That is a valuable thing to know and
a poor basis for a theory, and it should not be dressed up as the
latter.

---

# Correction (2026-08-30, from session `8e`) — two products, not one

My write-up said parlays are "almost certainly untradeable". That is
right for one product and **wrong for the other**, and stated flatly it
would send the next session past the one venue with real depth.

- **RFQ multivariate parlays** — where the +7.06 pt markup lives.
  `mve_selected_legs` appears on **0 of 104,304** board markets: these
  are not on the standard board at all, which is consistent with
  `active_quoters = 0`. Untradeable by a manual bettor: correct.
- **The 86 listed `*COMBO` markets** — where the arbitrage test was run.
  These are the opposite of untradeable: **71 of 86 two-sided**, all 86
  with non-zero volume and open interest, **median spread 4c**, 53 at
  ≤5c, and `KXBALANCEPOWERCOMBO-27FEB-RR` at **4.17M lifetime volume /
  2.73M open interest on a 1c spread**.

**The edge and the liquidity are in different products.** That is the
accurate one-line summary of this study.

`8e` also corroborated the arb result by an independent route — the
within-partition sum, where `{DD,DR,RD,RR}` is mutually exclusive and
exhaustive so YES prices must sum to 1: asks sum to 1.033 (buying loses
3.3c), bids to 1.002 (selling nets 0.2c gross, dead after four legs of
fees). My cross-event synthetic identity and that within-partition sum
are independent tests and agree. Recorded in
`theories/structural_arb/NOTES.md` (`db9efaa`), where it is a stronger
negative than this repo's usual "edge existed, died on depth": here the
depth is genuinely real and the edge is simply absent.

# Operational note — I over-collected, and the convention needs a budget

`collect.py` stored the full `raw_json` payload per row, per the repo's
"save as much as you can, while you can" rule. Left running it reached
**4,199,000 rows / 23.6 GB**, of which **16.3 GB was `raw_json` that no
analysis in this study reads**. Two harms, one of them not obvious:

1. It took the machine to **100% disk** (7.9 GB free).
2. **This repo lives inside OneDrive, and `.gitignore` does not stop
   OneDrive syncing.** A 23.6 GB file in `studies/` is a 23.6 GB cloud
   upload nobody asked for. The existing
   `theories/insider_bias/mention_family/studies/investigation/2026-08-29-series-bias-mining/data/collect.db` has the same
   exposure at 172 MB.

Deleted with the user's approval; the computed results were never in it
(they live in `legs.db`, 17 MB, plus the numbers committed here).

**The rule that was missing:** "save as much as you can" is a default,
not a licence — a collector needs a **size budget checked as it runs**,
and raw payloads should be opt-in when the analysis does not read them.
`collect.py` now defaults to **not** storing `raw_json` (`--keep-raw`
re-enables it) and refuses to continue past a `--max-gb` ceiling.

---

# FINAL — phase 2 pooled over 6 creation slates

```
4,808 parlays priced across 6 creation days

  markup vs product-of-MIDS
    day-clustered    : +6.60 pts   t=+14.20   k=6   MDE=1.30
    legset-clustered : +6.63 pts   t=+29.32   k=4808 MDE=0.63

  markup vs product-of-ASKS (every leg at the side actually payable)
    day-clustered    : +6.16 pts   t=+12.82   k=6   MDE=1.35

  per-day: 08-06 +6.87 | 08-07 +6.01 | 08-09 +7.51
           08-11 +7.85 | 08-12 +6.69 | 08-13 +4.69
```

Six creation days, 5 df, two-sided 95% critical value 2.57 — `t` of
14.20 clears it comfortably. MDE 1.30 pts sits well inside the
pre-registered 3-point floor. **All six days positive**, range
4.69–7.85.

**Status: the primary prediction is CONFIRMED. The secondary prediction
(magnitude grows with leg count) FAILED as written and is recorded as
failed. The edge is in a product with no fade-side liquidity; the
product with real liquidity (`*COMBO`) is flat.**
