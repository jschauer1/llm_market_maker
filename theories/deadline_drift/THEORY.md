# Deadline Drift

## Hypothesis

Markets that resolve YES only if a discrete, **unscheduled affirmative
event** occurs by a deadline — charged before D, pardoned before D, traded
before D, manager out before D, IPO confirmed before D — systematically
overprice YES as the deadline approaches with no event. Buy NO in the late
window when the implied hazard exceeds the historical hazard by more than
fees.

**The mistake, and why it persists.** Three mechanisms, two documented:

- **Longshot bias.** Late-window YES on a quiet market *is* a longshot, and
  longshots are overpriced.
- **Capital asymmetry** (Berg, Nelson & Rietz, 500k+ Intrade transactions):
  high-likelihood events underpriced and low-likelihood events overpriced
  specifically at long horizon. NO on a $0.90 favorite locks ~$0.90 to win
  ~$0.10 — a 9:1 capital commitment for a thin return. Unattractive to
  retail, capital-inefficient for professionals, so the correction is slow.
  **This is the answer to "why isn't it arbitraged away": the trade is
  unpleasant, not unavailable.**
- **Anchoring.** The story that made the market interesting keeps the price
  sticky as the clock runs out.

## What would falsify it

Stated before any bin is collected, per the spec's section 7:

- **Implied and empirical hazard agree within fees across all bins.** The
  market prices decay correctly; the theory is dead. Primary kill criterion,
  and the bins measure it directly.
- Positive gross edge that fees consume entirely — NO at $0.40–0.95 locks
  near-full collateral per point of profit, so this is a live risk and must
  be reported as `edge_pts_net`, never gross.
- The effect exists only where liquidity is worst, i.e. it is a spread
  artifact rather than a hazard mispricing.

## Data sources

In-repo only, Kalshi-native — no cross-platform matching needed. Board and
rules text, candlesticks for point-in-time replay, fee math.

## Decision procedure

**Stage 1 only. There is no stage 2 and none is planned.** No LLM anywhere
in the decision path; tier A.

**v2 (2026-09-01) ships DD-1's population.** v1's allowlist is described
below under "Why an allowlist rather than a board-wide screen" and is no
longer what the screen selects; `screen.in_allowlist` survives as a
recorded feature, not a filter.

1. **Population** (`screen.wide_population`): by-deadline phrasing, rules
   stratum `hazard` (i.e. not `threshold`, `scheduled` or
   `multi_destination` — `hazard.stratum`), minus partitions. The
   partition exclusion is one exclusion applied with the three
   instruments each population affords: the **series** set
   `hazard.partition_families` returned over settled history (persisted
   by `population.py`, since that function reads settlements and cannot
   screen a live board), Kalshi's `mutually_exclusive` envelope flag, and
   the price-partition test (>=3 siblings sharing one deadline summing
   $0.90–1.05). **4,404 markets** on the 2026-09-01 board, against 981 in
   70 series for v1.
2. **Candidates**: open, **days to the deadline stated in the rules** <= 21
   (never `close_time` — see correction 1), YES ask in $0.05–0.60, NO ask
   available, volume >= 100. Entry is the **first** qualifying day, which
   the ledger's dedup key enforces by preserving `entry_price` and
   `first_seen_at` from the first sighting.
3. **Edge**: `(1 - P(YES | price bin, days bin)) - no_ask - fees`, with the
   probability from hazard bins over settled history. **`hazard_bins.json`
   does not exist and must not be written until DD-1 clears**, so
   `price()` instead emits **observation rows** — claimed edge 0,
   `disposition='screened'`, a rationale saying outright that they are not
   recommendations — under the 2026-08-30 ruling. Zero is load-bearing:
   `ranked_edge = edge_pts_net × credibility`, so no row this theory
   currently produces can promote to a bet.

**Recorded per row, never filtered on** (`screen.features`): `recurring`
and `settled_events` (DD-2's split), `branch_family`, `in_allowlist`,
`event_legs` and `event_ask_sum` (the fixed-k elimination shape),
`open_interest` (kill criterion 3, which the ledger has no column for and
which cannot be recovered after the fact), and `yes_bid_implied` — which
is `1 - no_ask`, the side a NO buyer actually bets against, never the
field named `yes_ask`.

**`no_ask` is `1 - yes_bid`, and that is not a detail.** The step above
was always written correctly; the *measurement* script was not, and
priced the trade off `yes_ask` from 2026-08-29 until 2026-09-01. That
credits the strategy with the whole bid-ask spread, which on this
population runs a 4-point median and a 6-point mean — enough to roughly
double the apparent edge (wide stratum: +10.1 off the ask, +4.6 off the
bid). Anything measuring this theory reconstructs prices from raw
candles, which steps outside the `Market`/`no_ask` types that enforce the
convention everywhere else in the repo. Use `hazard.observe(side="bid")`.

### Why an allowlist rather than a board-wide rules-text screen

Five audit rounds established that a *board-wide* mechanical screen cannot
reach the spec's 10% misclassification bar. Rounds 1–4 tuned regex to a
plateau near 15%; round 5 added Kalshi's exclusivity flag and a
price-partition test and returned **12%** — not distinguishable from round 4
at n=50. The residue is multi-destination "which branch" markets, which are
semantic, and **both structural signals are blind on exactly that residue**
(all six round-5 misses carry `mutually_exclusive=False`).

Round 5b audited the allowlist **exhaustively** — a series-level construct,
so all 70 series were inspected with *no sampling error* — and found
**70/70** genuinely per-subject: every sibling is a different subject, never
a branch of one outcome. 0 carry `mutually_exclusive=True`; 0 are priced as
partitions.

The structural guard is kept on top of the family rule because it is what
removes `KXUKCABOUT` — "who is **next** to leave the Burnham Cabinet", 23
markets, a pure partition the suffix rule would otherwise admit.

## Status

**`testing`, v2, since 2026-09-01.** It records — 46 observation rows on
its first run — and it claims no edge while it does so. Read those two
facts together: the theory is now *accruing DD-1's out-of-sample set*,
which is the only thing that was ever between it and evidence, and it is
doing so without asserting anything it has not earned.

What changed was the population, not the thesis. v1 shipped the
70-series allowlist, recorded nothing, and was therefore unmeasurable;
the widening is argued below and in the version-2 bump justification.

**There is no clean backtest for this theory, and that is a finding
rather than an omission.** The usual advice — history is fetchable, so
run the replay — does not apply here, because the replay has already been
run as analysis (`hazard.py`, `bootstrap.py`) and *the population was
chosen on its results*. Every settled market this theory can reach is
in-sample for that choice. Recording it as a tier A backtest run would
make the data that suggested the population vouch for it, which is
exactly what CLAUDE.md's pairing discipline forbids and what
`mined_from_run_ids` exists to prevent. **The forward test is not the
slow path here; it is the only honest one.** A future session reaching
for `backtest-theory` on this theory should read this paragraph first.

**What 2026-09-01 measured** (`python -m theories.deadline_drift.hazard`
and `.bootstrap`, over **1,908 settled markets in 962 series** — the
entire fetchable by-deadline history, not a sample):

| population | gap at the tradeable price | 95% CI | events |
|---|---|---|---|
| **allowlist — what this theory ships** | **−1.0 pts** | [−9.8, +5.7] | 22 |
| wide by-deadline hazard stratum | **+4.6 pts** | [+1.0, +8.0] | 94 |

Read those two rows together, because neither means much alone:

- **The allowlist result is not evidence against the thesis. It is no
  evidence at all** — 70 series is too thin a slice of the board to
  measure anything inside a 60-day archive window, and its interval spans
  12 points.
- **The wide result is a real signal at the price a NO buyer actually
  pays**, and it survives every cut: it *grows* under tighter spread
  filters (+4.6 → +5.3 at ≤4pts, where a spread artifact must shrink),
  survives removing one-winner partition families (+4.8) and an
  open-interest floor (+5.3).

**So the binding constraint was never the thesis — it was the allowlist**,
adopted to preserve tier A back when a structural LLM gate was thought to
cost it. CLAUDE.md's "Structural gates keep tier A" removed that price on
the same day the allowlist was adopted, and nobody revisited the trade.

**Why this is still not bettable, and `price()` stays inert.** The +4.6
is **post-hoc**: the wide population was chosen and measured in the same
session, after a dozen cuts. CLAUDE.md's pairing discipline makes that a
hypothesis to pre-register, never an edge to bet on the data that
suggested it. It also inherits the audit's ~15% misclassification.

### The pre-registration (written 2026-09-01, before any out-of-sample data)

**DD-1.** On the by-deadline **hazard stratum** (`hazard.stratum() ==
"hazard"`, minus `hazard.partition_families()`), lifetime volume ≥ 100,
entering the first day a market is within 21 days of its **stated
deadline** with YES ask in $0.05–0.60, buying NO at `no_ask = 1 −
yes_bid`: realized P(YES) sits **at least 3 points below** the implied
`yes_bid`, event-clustered, net of fees.

- **Out-of-sample set:** markets settling **after 2026-09-01**. Nothing
  in today's capture counts.
- **Power:** today's estimate rests on 94 event clusters. The same
  population produces roughly that many per two months, so this is a
  ~60-day test, and the standing capture obligation in `RUNBOOK.md` is
  what collects it — that obligation is now the experiment, not
  housekeeping.
- **Kill:** an out-of-sample 95% CI covering zero at ≥ 80 event
  clusters, or a point estimate below **+2 net**. (The bar is +2 rather
  than +3 because the in-sample gross gap is +4.6 and the fee on a NO at
  these prices is ~1.1 pts, so the effect being tested is ~+3.5 net; a
  +3 bar would fail a true effect about half the time.)

- **The entry rule is load-bearing and is part of DD-1, not a detail.**
  Entering the *first* qualifying day gives +3.4 on the hazard stratum;
  averaging over every qualifying day in the window gives **−1.7**. That
  is not a robustness failure, it is the thesis: the overpricing decays
  as the deadline approaches, so entering as early as the window allows
  is where the drift is. But it does mean a test that enters late
  measures nothing, and any implementation must enter on first
  qualification.

**DD-2, a pre-specified split of DD-1** (not a second test to run only if
DD-1 fails). The in-sample effect is **entirely** in series *outside* the
allowlist — allowlist −1.0, CI [−9.8, +5.7], 22 clusters; non-allowlist
**+6.3**, CI [+2.4, +10.0], 72 clusters — and inspecting the
contributors says why. The non-allowlist side is a long tail of **one-off
newsy questions priced $0.25–0.55 that did not happen**: "Will the Senate
vote on the CLARITY Act?", "Will another GTA VI trailer come out before
Aug 2026?", "Will Google release Gemini 3.5 Pro before Aug 21?", "Will
Serbia announce a snap election?". The allowlist side is **recurring
families** — `KXFEDERALCHARGE`, `KXNBATRADE`, `KXMLBDEBUT` — which trade
much cheaper (mean bid 0.04–0.06) and price about right.

Proposed mechanism: **a recurring family teaches its own base rate.**
Traders who have seen forty coach-out markets resolve know roughly how
often one fires; a one-off question about a bill, a trailer or a model
release has no reference class on the board, so the story that made it
interesting sets the price. If that is right, the premium should track
*non-recurrence*, not the subject matter.

So the forward test splits on a property fixed at listing: **is this
market's series recurring** (≥ 3 settled events before the decision date)
**or one-off?** DD-2 predicts the gap concentrates in the one-off arm.
Recorded now, before any out-of-sample data, precisely because it was
found by looking — it is a hypothesis this sample suggested, and it
vouches for nothing until the forward test runs.

**Read DD-2 with its caveat.** The in-sample non-allowlist estimate is
heavy-tailed: 5 series carry 46% of the gap on 13 of 72 clusters, 10 of
the top 12 contributing series are
a single event that did not happen, and `KXBIGBROTHERELIMINATION` (a
one-winner partition, ~6% of the gap) shows the population is still not
clean. The bootstrap prices the sampling uncertainty; it cannot price the
contamination.

**DD-3, a replication on contemporaneous data the population choice never
saw** (written 2026-09-02, while the capture that produces it was still
running, before any number from it existed).

**Why this exists.** DD-1's out-of-sample set is defined by *settlement
date* — markets settling after 2026-09-01 — on the stated belief that
"today's capture" was the entire fetchable history. **That belief was
wrong.** `collect_settled`'s walk took its series list from the live
board (`superset_series`), so it could only ever reach a series that
still had something trading. Measured 2026-09-02: the board-scoped walk
covered **962 series (170 with results)** against **13,733 series on the
platform**. A 200-series probe of the unwalked remainder found
by-deadline settled markets inside the reachable window at ~0.14 per
series, extrapolating to roughly **+700 markets, ~37% on top of the
1,908** the estimate was built from.

**This is a selection correction, not a sample-size win.** A series
leaves the board *because* its question resolved, so board-scoped capture
systematically under-samples families that already finished — precisely
the population a by-deadline theory is about. The direction of that bias
is not obvious a priori, which is why this is worth running rather than
assuming.

**DD-3 is not DD-1 and does not substitute for it.** These markets
settled *before* 2026-09-01, so they are contemporaneous with the
in-sample set, not forward of it. They control for **selection**; they
control for nothing about **regime**. DD-1 remains the forward test and
its clock is unaffected.

- **Population and entry rule:** identical to DD-1, unchanged — hazard
  stratum minus `partition_families()`, lifetime volume >= 100, entry on
  the **first** day within 21 days of the stated deadline, YES ask
  $0.05-0.60, buying NO at `no_ask = 1 - yes_bid`, event-clustered, net
  of fees. Nothing about the rule is re-tuned for this set; if it were,
  this would be another in-sample fit.
- **Out-of-sample set:** exactly those tickers **absent from
  `data/preplatform_seen.json`**, a file frozen from the store *before*
  the platform walk began. That file is the boundary and must never be
  regenerated after the walk — regenerating it would silently convert
  this test to in-sample.
- **Confirmation:** point estimate **>= +2 net** with a 95%
  event-clustered CI excluding zero. Same bar as DD-1, because it is the
  same statistic; +2 rather than +3 for the same fee reason.
- **Failure:** a 95% CI covering zero at >= 80 event clusters, or a point
  estimate below +2 net. Below 80 clusters the result is reported as
  underpowered and settles nothing, in either direction.
- **Reported alongside, as a descriptive control, never as the test:**
  the same statistic recomputed on the seen set with identical code, and
  the DD-2 recurring/one-off split on the unseen arm. A gap between seen
  and unseen is evidence about *selection*, and is explicitly not
  licensed as evidence about the edge.
- **Tier A.** No LLM anywhere in the decision path, so no cutoff applies
  and no contamination probe is owed.

**DD-4 and DD-5, written 2026-09-02 at ~50% capture, before the data
either one is scored on had been fetched.**

**Why these exist: a peek costs something, and this is the price being
paid explicitly.** The DD-3 aggregate was computed and reported at ~45-50%
capture, at the user's request, on 36 event clusters. Those 509 tickers are
frozen in `data/dd3_peeked.json` and are **spent for the aggregate test** —
looking at them again is a second look at the same data, and reporting
whichever look is friendlier is the exact failure pre-registration exists
to stop. What follows fences that off and commits the *unlooked-at*
remainder to tests specified in advance.

**DD-4 — holdout replication of DD-3.** Same population, same entry rule,
same bar, restricted to unseen tickers **absent from `dd3_peeked.json`**
(i.e. captured after the freeze).

- **Read it with its weakness stated up front.** `platform_series` walks
  KX* ordered by category, so the holdout is not an exchangeable random
  half — it is a different category mix (the peeked half skews Politics
  and Financials; the remainder skews Sports, Entertainment and the tail).
  A difference between halves is therefore **confounded with category**
  and is not by itself evidence about the edge. DD-4 can corroborate; it
  cannot arbitrate.

**DD-5 — DD-2's contrast, on the whole unseen arm. This is the one worth
running.** DD-2 predicts the gap concentrates in **one-off** series and
that **recurring** families price about right. That split has **not been
examined on any unseen data**, so the full unseen arm — peeked half
included — is clean for it.

- **Primary statistic: the contrast**, `net(one-off) − net(recurring)`,
  event-clustered. DD-2 predicts it is **positive**. A contrast is chosen
  deliberately over either arm's level: the reported aggregate is a
  weighted average of the two arms, so it constrains the *levels* somewhat
  and the *difference* barely. That residual contamination is the honest
  caveat and it is small, not zero.
- **`recurring` is point-in-time and must be computed as such.** A series
  is recurring for a given market if it had **>= 3 settled events with a
  close_time strictly before that market's own decision date**. It must
  **not** come from a `population_facts.json` rebuilt after this walk —
  that file is regenerated from the whole store, so using it would let the
  test period's own settlements define the test's split.
- **Confirmation:** contrast >= +3 pts with a 95% event-clustered CI
  excluding zero, and the one-off arm positive on its own.
- **Failure:** a CI covering zero with >= 30 clusters in each arm. Below
  that, underpowered, and it settles nothing.
- **What each outcome means.** DD-5 positive rescues a *narrower* theory
  than the one that was claimed: not "buy NO across the hazard stratum"
  but "buy NO on one-off newsy questions". DD-5 null, with DD-3 also
  failing, is the end of the broad thesis — and at that point the
  +4.6 is best read as a survivorship artifact of board-scoped capture,
  which is a result worth having.

**Standing consequence, independent of all three.** The **+4.6 is
withdrawn as this theory's headline number** as of 2026-09-02. It was
measured on a sample that could only contain series still trading, and a
by-deadline series leaves the board *because* its question resolved. No
report should quote it as the theory's edge again; it stands only as the
in-sample estimate it always was, now with a known selection defect.

**Reached `testing` 2026-09-01** by widening the population past the
allowlist (v2, `continues`) and recording. To reach `active`: DD-1
confirmed out of sample.

**`under_review` is NOT reachable from these rows, and the distinction
matters.** The n=20-with-negative-edge trigger reads rows the theory
claims positive edge on, and every row it currently writes claims zero.
Per the 2026-08-30 ruling, the aggregate calibration edge over
observation rows measures *the board*, not this decision procedure, so it
can carry no verdict — a theory with zero settled bettable rows is
**unmeasured**, never `under_review`. The trigger arms when
`hazard_bins.json` is written, which DD-1 clearing is what licenses.

**No LLM gate was built, and the widen-population ticket's step 1 was
deliberately not followed.** That step asked for a series-level
structural gate to remove the residual ~15% multi-destination
misclassification. Three reasons it was dropped: DD-1's population is
defined without one, so adding it would test a population nobody
pre-registered; the ~960 judging calls buy purity the pre-registration
does not ask for; and the same information is now recorded per row as
features, which makes the cleaner subset available later as a registered
slice — data over recorded fields — without changing what DD-1 measures.
If purity turns out to matter, that is a v3 decision made on settled
rows, not a guess made before any of them exist.

## Candidate flow

The population is long-dated by nature, so a snapshot understates it: **41**
markets sit inside the <=21-day window today, but **714 close over the next
12 months**, each passing through that window once. Live scans surface a
handful at a time; the backtest population is the annual flow.

## Version

**v1** (2026-08-29) — initial. Allowlist screen + structural guard, hazard
bins pending.

## Known defects carried forward

The price-partition test here has a **two-sided** band ($0.90–1.05). Round
5's frozen classifier had no lower bound, and session 09 found 281 of its
318 exclusions were spurious — `KXCOACHOUTNFL` is 22 *independent* coach
hazards summing 0.13. That classifier is deliberately left unpatched
(freezing it before the sample was drawn is what made round 5
out-of-sample); the fix lives here instead.

When the backtest is built it must construct the screen payload from the
`market_snapshots` capture at or before the decision point, never a current
fetch: `rules_primary` changes substantively on live markets, and a moved
strike does not merely misjudge one market — it reassigns it to a different
stochastic process and poisons a whole bin. See
`studies/2026-08-29-structural-gate-payload-version/`.
