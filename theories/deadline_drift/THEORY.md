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
in the decision path; `edge_basis="model"`; tier A.

1. **Population** (`screen.py`): allowlist series families, by-deadline
   phrasing, minus the structural guard — Kalshi's `mutually_exclusive`
   flag, and events priced as a partition (>=3 siblings sharing one
   deadline summing $0.90–1.05). **981 markets in 70 series** on the
   2026-08-29 board.
2. **Candidates**: open, days-to-close <= 21, YES ask in $0.05–0.60, NO ask
   available, volume >= 100.
3. **Edge**: `(1 - P(YES | price bin, days bin)) - no_ask - fees`, with the
   probability from hazard bins over settled allowlist history.

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

`proposed` — still, as of 2026-09-01, and now for a better-evidenced
reason than on 2026-08-29. The bins have been collected twice over; what
is missing is a population this theory is entitled to bet.

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

To reach `testing`: widen the population past the allowlist (a version
bump, and the structural-gate decision the notebook left open), then
record. To reach `active`: DD-1 confirmed out of sample.
To `under_review`: n=20 with `calibration_edge_net` <= 0.

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
