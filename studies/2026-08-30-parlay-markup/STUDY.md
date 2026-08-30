# Parlay markup — pre-registration, written BEFORE any markup number

**Date:** 2026-08-30 · **Status:** collecting · **Tier:** A (no model
anywhere) · Backlog spec #8, registry slug `parlay-fade`

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
