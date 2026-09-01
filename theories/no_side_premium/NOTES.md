# no_side_premium — lab notebook

Append-only. Raw observations, dead ends, data quirks. Distill into
THEORY.md only what changes the claim, the procedure, or the status.

## 2026-08-26 — born as a forward test

Implemented from idea 14's revisit angle after two fullcov measurements
(details in the idea record and THEORY.md). Deliberate choices:

- Cells record at the **fresh ask at scan time**, not the board pull's
  ask — the board can be hours old, and the backtests entered at
  point-in-time asks, so scan-time asks are the honest forward analogue.
- Cell B rows are `rejected`, not `screened`, so the avoid claim is
  tested by the existing control-group machinery instead of polluting
  `roi_all` with rows the theory says are bad.
- First live day (board 108,820): population 807, cell A = 8 (all
  KXTRUMPSAY-26AUG31 strikes), cell B = 59. Cell A being one event's
  strikes today is fine for rows but means early cell-A settlements are
  event-clustered — the n >= 40 interim look must count events, not
  just rows, before believing anything.

## 2026-08-27 — first 12 settlements are a day artifact, not a result

Cell B posted its first 12 settlements today: **12/12 wins**, mean ask
0.845, `calibration_edge_net = +14.59`. Cell B is the *avoid* list —
pre-registered at −3.9 net — so read naively this is a fast, loud
falsification of the theory's core claim.

It is nothing of the kind, and the reason is worth writing down carefully.

All 12 settled on **2026-08-27**. I rebuilt the whole population they were
drawn from — `insider_bias.screen()` at pinned defaults over the
`market_snapshots` capture at 2026-08-27T01:06:07Z, restricted to markets
closing that day, priced before any of them settled — and fetched every
outcome. n=99 settled of 109.

**Every single YES favorite in that population won: 55/55.** The
population's YES-favorite edge that day was +12.15 net. Cell B's 12 rows
are a subset of that 55. They did not beat the day; they *are* the day.

The same control over the two prior close-days shows the side split
reversing outright:

| close day | YES favorites | NO favorites |
|---|---|---|
| 2026-08-25 | n=38, −1.42 net | n=58, +7.98 net |
| 2026-08-26 | n=3, −11.50 net | n=17, −6.55 net |
| 2026-08-27 | n=55, **+12.15** net | n=44, −3.05 net |

Whole-population favorite edge by day: +4.26 / −7.29 / +5.40 net. The
day-to-day swing is ~12 points — wider than the ±3.9 this theory is trying
to resolve. Full writeup and data:
`studies/2026-08-27-settlement-day-clustering/`.

**Why this bites this theory harder than any other.** The quantity
no_side_premium measures *is* the YES/NO split, and the YES/NO split is
precisely what reverses between days. A row-counted sample can hit n=150
while containing four settlement days, and four draws cannot resolve a
2-point side effect.

**What I changed.** The pre-registered bars in THEORY.md now require
settlement-day spread in addition to row count. This is a post-hoc change
to a pre-registration, which is normally the cardinal sin, so the honesty
argument in full:

1. It came from a **control population**, not from this theory's rows — the
   whole screen, 215 markets over three days, none of it selected on
   outcome.
2. It only ever makes confirmation **harder**. No bar was loosened, no
   window widened, nothing that would let a dead cell look alive.
3. Leaving it unchanged would have let cell A confirm at n≥40 on what could
   be two lucky days, which is the failure the bar existed to prevent.

Ruled out as alternative explanations for the 12/12:
- *Cell B mis-implemented (recording the wrong side)* — no; rows are
  `outcome=yes` at asks 0.80–0.89, exactly as specified.
- *Fee/price-band artifact* — no; the effect is present gross.
- *Small n* — that is the point, but the useful statement is stronger than
  "n is small": n=12 rows is n=1 **day**, and `day_clustered_se` is
  undefined at one cluster.
- *Regime change since the backtests* — cannot be ruled out on one day and
  is not needed to explain anything here.

**Status unchanged: `testing`, nothing recommendable, `edge_basis='prior'`
throughout.** Cell B is neither confirmed nor killed; it is unmeasured. Six
of the 12 rows were same-instant 17:00 financial closes (BTC ×2, ETH, SOL,
GOLD) plus an index — one macro direction, six rows — which is the
within-day clustering problem in miniature, one level below the day level.

**Next look:** when `n_days` reaches ~8 for either cell, not when `n` does.
`python -m tools.cli score report no_side_premium` now prints
`settlement_days` with `n_days` and the clustered SE.

## 2026-08-29 — cell B at n=35 / n_days=2: the day amendment earns its keep again

Live run `live-2026-08-29`: population 748 → **17 cell A (screened) + 56
cell B (rejected)** = 73 rows recorded at fresh asks. Cell A is no longer
a single event's strike ladder, which was the 2026-08-26 worry.

The settle pass added 95 settlements repo-wide and cell B now has **35
settled rows**. Read naively that is `calibration_edge_net = −12.17`,
which "confirms" the −3.9 avoid claim. **It does not, and the amendment is
why.** Day-clustered: `n_days = 2`, net **−7.78 ± 22.0**.

The two days disagree completely:

| settlement day | n | win rate | implied | net edge |
|---|---|---|---|---|
| 2026-08-27 | 14 | 1.000 | 0.849 | **+14.18** |
| 2026-08-28 | 21 | 0.571 | 0.860 | **−29.74** |

That is the same population swinging 44 points between two consecutive
close-days. The 2026-08-27 note recorded cell B's first 12 settlements as
+14.59 net on one day and refused to read it; the row count has since
tripled and the sign has flipped, which is exactly what the clustering
study predicted a row-counted sample would do. Had the pre-registration
been left at "n ≥ 60 rows" the theory would now be claiming confirmation
of an effect it has measured for two days.

Bars unchanged and both still far off: cell B needs `n ≥ 60` **and**
`n_days ≥ 8`; cell A has 0 settled (its rows close 08-31 onward).
Status stays `testing`; nothing here is recommendable — `edge_basis` is
`prior` on every row by design.

## 2026-08-29 — cell B's -10.44 is three days, and a sharper estimator exists

`score report` today shows cell B (rejected) at **calibration_edge_net
-10.44, n=46**, which reads as the avoid-list being validated hard. It is
not a result. Day-clustered: **n_days=3**, per-day net +14.18 / -29.74 /
-4.93, **day-clustered SE 12.73** — larger than the point estimate. The
2026-08-27 amendment called this exactly: on that date the same cell read
+14.59 on `n_days=1` and looked like a falsification. The sign flipped
with two more days. Neither reading was information.

Cell A still has **0 settled**. Its rows are `KXTRUMPSAY-26AUG31` strikes;
first evidence lands 08-31.

### The paired within-day estimator

Full write-up: `studies/2026-08-29-side-asymmetry-extension/`. Two more
close-days measured on the clean snapshot population (08-28 n=158, 08-29
n=24 partial), composed with the earlier study's three.

This theory's claim is a **side** claim, and the day effect is a common
shock to both sides — so it cancels in `NO_net - YES_net` computed within
a day. That is the same claim with the dominant noise term removed:

| close day | YES | NO | NO-YES |
|---|---|---|---|
| 08-25 | -1.42 | +7.98 | +9.40 |
| 08-26 | -11.50 | -6.55 | +4.95 |
| 08-27 | +12.15 | -3.05 | **-15.20** |
| 08-28 | -26.45 | +6.15 | **+32.60** |
| 08-29 † | +5.11 | +14.60 | +9.49 |

† partial day, 24 of 70 settled; will move.

```
n_days = 5 (amended bar: >= 8)
mean NO-YES = +8.25   day-clustered SE = 7.60   t = +1.08 (4 df)
sign test: 4/5 positive, p = 0.375
```

Per-side day-equal-weighted means vs the pre-registration:

| | measured | claimed |
|---|---|---|
| YES side | **-4.42** | -3.9 (cell B) |
| NO side | **+3.83** | +2.0 (cell A, narrower slice) |

**Both point estimates land within ~1.8 pts of their priors, and 4 of 5
days carry the predicted sign — and none of that is significance.**
`n_days=5 < 8`, `t=1.08`. Two independent estimates agreeing with their
priors is encouraging and nothing more; the bar is unchanged.

### A contaminated control, recorded so it is not repeated

An intermediate pass compared cell B against *other YES favorites in the
ledger* on the same day: deltas +7.32 / +0.25 / +19.27, mean +14.84 — cell
B never underperforming. **Worthless twice over.** The comparison
population is the very population the thesis indicts, and ledger rows are
theory picks, not a sample of the board. The clean snapshot population
gives +8.25. Population-level questions get the snapshot population; never
the ledger.

### Reading recommendation (no version bump)

Report this theory on the paired within-day statistic as the primary
figure, with `compute_score`'s per-disposition numbers alongside.
Decision procedure — population, cells, sides, bands, recording — is
untouched, so this is the same class of change as the 08-27 day amendment,
and like that one it makes confirmation **harder**: the pooled -10.44
flatters cell B, while the paired estimator says there is no result yet in
either direction.

## 2026-08-29 (cont.) — cells registered as slices; machinery agrees with the hand count

`cell-a-no-favorite` ({outcome: no, entry_price >= 0.85}) and
`cell-b-yes-avoid` ({outcome: yes, entry_price 0.80–0.90}) are now
registered slices, registered_at backdated to the documented 2026-08-26
pre-registration. Validation: `slices report no_side_premium` reproduces
the status section's numbers from the ledger independently — cell B
forward n=46 / n_days=3 / −10.44 net pooled, day-weighted −6.83 ± 12.72,
not ready (day gate); cell A 0 settled. Every row lands OOS because this
theory's own ledger only began after registration; the fullcov evidence
that motivated the cells sits in sibling theories' ledgers and never
enters these segments. Nothing about the decision procedure changed.

One reading note: when cell B's slice goes ready, a *negative* OOS
record is the claim CONFIRMING (avoid validated), and ranking will
correctly zero its rejected rows — do not read a ready-and-negative
cell B as the theory failing.

## 2026-08-29 (session 3, item 2) — no_side_premium: a sharper estimator, and a contaminated control caught (migrated from RESEARCH_LOG.md)

**Did:** Diagnosed `no_side_premium`'s headline `calibration_edge_net =
-10.44 (n=46)`. Extended the settlement-day-clustering study by two clean
close-days and built the paired within-day estimator the theory's claim
actually calls for. Study:
`studies/2026-08-29-side-asymmetry-extension/`; theory detail in its
`NOTES.md`; `THEORY.md` status updated. Suite **900** green.

**Learned:**

1. **The -10.44 is three days, not 46 draws.** Per-day net +14.18 /
   -29.74 / -4.93, day-clustered SE **12.73** — larger than the point
   estimate. The 08-27 amendment predicted this precisely: the same cell
   read +14.59 on one day and looked falsified; the sign flipped with two
   more days. Neither reading was information.
2. **The claim is a side claim, so measure it paired.** The day effect is
   a common shock to both sides and cancels in `NO_net - YES_net` within
   a day. Over the clean snapshot population across 5 close-days: **mean
   +8.25 pts, SE 7.60, t=1.08, 4/5 days positive.** Right sign,
   not significant, bar is `n_days >= 8`.
3. **Both pre-registered point estimates are close to measured.** YES side
   -4.42 vs -3.9 claimed; NO side +3.83 vs +2.0. Two independent estimates
   agreeing with their priors is encouraging and is *not* significance —
   worth saying twice because it is the tempting misread.
4. **I built a contaminated control and caught it.** Comparing cell B to
   *other YES favorites in the ledger* gave +14.84 and "cell B never
   underperforms". Worthless: the comparison population is the one the
   thesis indicts, and ledger rows are theory picks, not a board sample.
   Clean population says +8.25. **Population-level questions get the
   snapshot population, never the ledger** — recorded in the study so it
   is not repeated.
5. **A silent trap in replaying any snapshot:** `screen()` filters on
   days-to-close and defaults `now` to the wall clock, so without
   `now=<capture time>` it drops the entire settled population and returns
   ~0 rows without erroring. Cost one confused run; now documented.

**Next:** re-run `measure.py` with a new (close day, snapshot) pair each
session — the series hits the `n_days >= 8` bar around 2026-09-01. Cell A's
first settlements land 08-31. `deadline-drift`'s three-way user decision is
still open.

## 2026-08-25 — pointer: founding evidence (migrated entry lives in mention_family's notebook)

The side-asymmetry pattern-mining pass that founded this theory (idea
14, registered 2026-08-25) is recorded in full under `## 2026-08-25 —
Pattern-mining the fullcov rows: timing and price-level dead, but a side
asymmetry survives every stress and feeds no-side-premium (migrated from
RESEARCH_LOG.md)` in `theories/insider_bias/mention_family/NOTES.md`,
not here.

## 2026-08-26 (cont.) — no_side_premium forward test implemented and running; polymarket whale filter fixed (migrated from RESEARCH_LOG.md)

**Did:** Second backlog implementation this session: `no_side_premium`
v1 (idea 14, spec priority 6/22) — the pre-registered forward test of
the optimism-tax finding, exactly as the idea's revisit angle states
it. Cell A: mention-family NO favorites ask>=0.85, screened, prior
+2.0 net. Cell B: non-mention YES favorites 0.80-0.90, recorded
REJECTED as an avoid-list so settlements test "these lose" as a free
control. Population imported from insider_bias.screen (the exact
screen both fullcov measurements drew from; parameters pinned by
test). Live asks refreshed before recording. First run: population
807 -> 8 A + 59 B -> 60 recorded at fresh asks (run
live-2026-08-26-nsp). Confirmation/kill bars pre-registered in
THEORY.md. All edges edge_basis='prior' — nothing recommendable until
the cells' own settlements measure them. Also fixed
tools/polymarket/trades.py: filterAmount without filterType=CASH
filters on share count, not dollars (live-contract test caught it).

**Learned:** Cell A today is entirely one event's strikes
(KXTRUMPSAY-26AUG31) — early cell-A reads will be event-clustered;
NOTES.md flags that the interim look must count events. Cell B is 30+
distinct series — healthier immediately.

**Next:** Both new theories accrue settlements automatically via the
session settle pass. Nothing to do but run each session and wait.

## 2026-08-31 (UTC) - 106 cell-B attempts were mislabeled screened; repaired

Found while reconciling the score CLI's screened pool (n=19 settled)
against the cell-a slice (n=2): 17 of the 19 were YES-side avoid-cell
rows. Mechanism, pinned in git: the attempt INSERT hardcodes
disposition='screened' and relies on finish() calling ledger.interpret()
to stamp non-screened rows - but interpret only started stamping the
attempt at commit 37f0f2a (2026-08-29T02:29Z). Rows recorded between the
attempt-table migration (2026-08-28T23:45Z) and that fix - run
live-2026-08-29 (recorded 00:13Z) and part of the generic 'live' run -
kept rejected positions over screened attempts. The rows' own rationale
text says "Recorded rejected", and confidence='yes_fav_8090_avoid' marks
the cell deterministically, so all 106 were repaired to rejected
(ledger backed up 2026-08-31T00:43Z before today's settle). Corrected
saved pools: screened n=2 +7.02 net (1 day), rejected n=64 -8.00 net
(4 days) - now identical to the slice partition. Slice evidence was
never affected (predicate-based); only the disposition pools misread.

## 2026-09-01 — the n_days>=8 bar is reached; the paired claim is null, and the paired estimator was the wrong one

Session `llm-market-identifier-57`, theory lane. Full write-up and data:
`studies/2026-08-29-side-asymmetry-extension/` ("Pass 2").

**The bar the 08-27 amendment set is met.** `n_days = 8`, and the answer
is **null**: mean `NO - YES` = **+2.91 pts**, day-clustered SE 5.51,
t = +0.53 on 7 df, 95% CI **[-7.89, +13.72]**, sign test 5/8 positive
(p = 0.727). Per-side day-equal-weighted: YES **-2.16** (cell B claims
-3.9), NO **+0.75** (cell A claims +2.0).

Pass 1 at 5 days read +8.25 with sides at -4.42 / +3.83 and called it
"right sign, not significant". **Three more days moved every one of those
numbers toward zero.** The two-point-estimates-agree-with-their-priors
observation, which pass 1 was careful not to call significance, did not
survive. Worth remembering as the concrete instance: it *felt* like
converging evidence and it was noise settling.

### How the 8 days were assembled, including a temptation refused

Days measured: 08-24, 08-25, 08-26, 08-27, 08-28, 08-29, 08-30, 08-31.
Excluded: **2026-09-01, 27 of 148 settled (18%)**.

- **Inclusion rule fixed before the numbers: >= 90% settled.** 08-29 is
  why — it entered pass 1 at 24-of-70 reading **+9.49** and reads
  **+4.10** complete. Early settlers are finished sports.
- That rule left **7** days against a bar of **8**, and admitting 09-01
  at 18% would have reached the bar. It was not admitted. Instead
  close-day **2026-08-24** was added — a complete day (155/156) the
  series had never used, from the earliest capture on disk
  (`2026-08-24T01:34:44Z`), same method. **The decision to add it was
  written down before its number was computed** (+14.11).
- **All 8 days re-measured at one vintage.** Not cosmetic: 08-28 moved
  +32.60 -> +28.97 and 08-27 -15.20 -> -19.56 as their stragglers
  settled. 08-25 (+9.40) and 08-26 (+4.95) reproduced the 2026-08-27
  study exactly, which is the check that the method is unchanged.

### A silent data defect that had to be fixed first

`measure.py` rebuilt its point-in-time board with `WHERE captured_at = ?`.
**Dedup-on-write (spec 5.2 phase 2, 2026-08-30) makes that wrong**: a pull
writes no row for an unchanged market, so an exact-stamp filter returns
"markets that moved at this pull" — correlated with liquidity, hence with
price and side, which is exactly what this study measures. No error, just
a plausible board of the wrong markets. It costs **46% of the 2026-08-31
board** (53,613 rows vs 99,064 markets) and 24% of 09-01's.

Fixed by `tools.snapshot.board_as_of(conn, platform, at)`, promoted to
`tools/` under the caller-count rule (three study probes had open-coded
the broken query). Six tests in `tests/test_snapshot_store.py`. The
reconstruction returns exactly 105,104 for the 09-01 capture, which is the
market count that floor reported pulling. Suite 1,287 green.

### The finding: pairing was the wrong instrument, and it is measured now

Pass 1 adopted `NO - YES` because "the day effect is a common shock to
both sides, so it cancels". Eight days let that be tested:

```
paired NO-YES, all bands : between-day SD 15.59 -> 477 days to detect +2.0
NO 0.90-0.97, single side: between-day SD  5.64 ->  62 days
NO all bands,  single side: between-day SD  6.90 ->  93 days
YES all bands, single side: between-day SD 12.46 -> 304 days
```

The paired estimator is the **worst of the four**. Independent sides would
give SD sqrt(6.90^2+12.46^2) = 14.24; observed is 15.59, so the sides are
if anything negatively correlated day to day. **Differencing imports the
YES side's variance rather than cancelling it.**

Obvious in hindsight, and that is the point: the YES favorites and NO
favorites in this screen are *different markets on different subjects*,
not two sides of one contract. There is no shared shock. Pass 1's
reasoning would have been right for a long/short pair on one market.

**Consequence: the pooled paired claim cannot be resolved on any practical
horizon** — 477 settlement days against a ~60-day Kalshi archive window.
Report this theory on the **single-side NO 0.90+** figure instead; same
claim, ~8x less data.

### Where the structure is — and what starves it

Day-clustered over the 8 days (868 settled favorites):

| cell | n | days | mean | SE | t | sign |
|---|---|---|---|---|---|---|
| YES 0.65-0.80 | 97 | 8 | -0.09 | 6.96 | -0.01 | 4/8 |
| NO 0.65-0.80 | 124 | 8 | +1.31 | 5.73 | +0.23 | 4/8 |
| YES 0.80-0.90 (cell-B mech) | 90 | 7 | **-0.86** | 5.64 | -0.15 | 4/7 |
| NO 0.80-0.90 | 125 | 8 | -8.30 | 11.48 | -0.72 | 5/8 |
| YES 0.90-0.97 | 157 | 8 | -0.80 | 3.69 | -0.22 | 5/8 |
| NO 0.90-0.97 (cell-A mech) | 275 | 8 | **+1.70** | **1.99** | +0.85 | **7/8** |

1. **`NO 0.90-0.97` is the only cell that looks like anything** — +1.70
   against a +2.25 fullcov measurement and a +2.0 prior, 7/8 days positive
   (p = 0.070), tightest SE on the board by 2x. Not significant (t=0.85),
   and one of 13 cells inspected — but unlike the other 12 it was
   *pre-registered* (idea 14's mechanism, the cell both fullcov backtests
   measured). It is the one place where size, sign and stability all agree
   with a prior fixed before the data.
2. **Cell B's -3.89 prior is not reproduced**: YES 0.80-0.90 reads -0.86
   +/- 5.64. Consistent with the ledger's cell-B drift (-8.00 at n=64 ->
   -0.98 at n=109).
3. **Cell A's population is 15 rows on 2 of 8 days.** The mention family
   barely appears in this screen — 15 NO rows, zero YES rows. Its own bars
   (`n>=40`, `n_days>=8`) are far off, and its +3.72 at 2 days is exactly
   the one-cluster non-result the 08-27 amendment exists to refuse. **The
   band carries the signal; the family restriction starves it** —
   `NO 0.90-0.97` across the whole screen is 275 rows over 8 days, 18x the
   population, at a comparable point estimate.

### What was deliberately NOT done

**Cell A was not widened.** Dropping the mention-family restriction
because the narrow cell is thin, *after* seeing that the wide one looks
better, is precisely the move the pre-registration exists to prevent. It
is filed as a separate pre-registered theory instead (ticket + idea
`no-favorite-high-band`), which is how this theory came off
`mention_family` in the first place.

**No retirement proposed.** Neither cell is killable by its own rule:
cell A kills at `<= 0` with `n >= 150` and sits at n=20 / +4.33; cell B
kills at `>= 0` with `n >= 150` and sits at n=109 / -0.98 (negative =
claim confirming). The pre-registration governs, not the null pooled
number.

**No new slice registered.** Cell A and cell B already exhaust what this
theory records; the band structure was measured on the clean snapshot
population precisely because the ledger holds only those two cells. There
is nothing further to partition here that would not be post-hoc mining of
109 rows.

**Status stays `testing`, `edge_basis='prior'`, nothing recommendable.**

### Next

- Re-run `measure.py` each session; 09-01 enters by itself once it clears
  90% settled.
- Read the theory on single-side NO 0.90+, not paired.
- The live question is now `no-favorite-high-band`, not this theory.

### Robustness, run after the headline — and it matters in both directions

**1. The day added to reach the bar was not carrying the result.** 08-24 was
added to reach `n_days=8` without admitting a partial day, and it is also the
one day that could overlap the window the founding fullcov backtests were run
over (they ran 2026-08-25). Dropping it makes the result **more** null, not
less:

| | 8 days | without 08-24 |
|---|---|---|
| paired NO-YES | +2.91, SE 5.51, t=0.53 | **+1.31, SE 6.09, t=0.22** |
| NO 0.90+ single side | +1.70, SE 1.99, t=0.85 | **+1.22, SE 2.23, t=0.55** |

So the null conclusion does not depend on it, and if anything 08-24 flattered
the thesis. (The overlap is in any case at most a handful of rows — the
mention family supplies 15 NO rows across all 8 days.)

**2. Leave-one-out says the paired statistic is one day.** Drop 08-28
(+28.97) and the pooled paired mean goes **negative**, -0.81. Nothing else
moves it much. An 8-day mean that flips sign on one day is not a measurement,
which is the same thing the power calculation says in another language.

**3. The NO 0.90+ cell, per day — and a weighting trap caught in the act.**

| close day | n | wins | win rate | mean ask | net |
|---|---|---|---|---|---|
| 2026-08-24 | 47 | 47 | 1.000 | 0.946 | +5.05 |
| 2026-08-25 | 29 | 28 | 0.966 | 0.950 | +1.19 |
| **2026-08-26** | **6** | **5** | 0.833 | 0.945 | **-11.53** |
| 2026-08-27 | 26 | 26 | 1.000 | 0.945 | +5.18 |
| 2026-08-28 | 71 | 70 | 0.986 | 0.944 | +3.82 |
| 2026-08-29 | 24 | 24 | 1.000 | 0.938 | +5.80 |
| 2026-08-30 | 27 | 26 | 0.963 | 0.950 | +1.00 |
| 2026-08-31 | 45 | 44 | 0.978 | 0.943 | +3.10 |

Seven of eight days sit between +1.00 and +5.80. The single negative day is
a **6-row day** whose whole deficit is one loss.

Day sizes run 6 to 71, so the weighting choice moves this cell a lot:

```
row-pooled (n=275)              +3.32
day-equal weighted              +1.70   SE 1.99   t=0.85     <- reported
days with >= 10 rows (7 days)   +3.59   SE 0.73   t=4.93
```

**The third line is not a finding and must not be quoted as one.** A >=10
rows/day floor drops exactly one day — the only negative one — and the only
reason to reach for that floor is having already seen that the negative day
was the small one. That is precisely the failure the calibration_harvest
gradient review caught on 2026-08-29 (`studies/2026-08-29-calibration-harvest-
gradient-review/`, peer review by llm-market-identifier-4f): **the inclusion
rule was the result.** It is recorded here because it was tempting, not
because it is evidence.

The honest reading: **+1.70 +/- 1.99 is the number**, and this cell is *not
yet weighting-robust* — a spread of +1.70 to +3.59 across defensible
weightings, driven by one thin day. The correct response is to fix a
minimum-rows-per-day rule **before** collecting more, which is now part of
what `no-favorite-high-band` must pre-register.

### Considered and declined: a `NO >= 0.90` sub-slice on cell A

It is expressible over recorded fields (`{outcome: no, entry_price: {min:
0.90}}`), it is a genuine subset of what this theory records, and the
0.90+ band is where the structure sits — so registering it as a slice was
the obvious move and it was declined on purpose.

Why: cell A holds **20 settled rows across 2 event clusters**, so the
0.90+ subset of it is a handful of rows accruing at ~2-4 per session from
a family that appeared on 2 of the last 8 close-days. Registering it would
start an out-of-sample clock that cannot reach the 10-cluster / 5-day
gates on any horizon that matters, and would put a third segment into
every report of this theory carrying no information. The same predicate
over the **whole screen** is 275 rows in 8 days — which is not a slice of
this theory, because this theory does not record that population. It is
`no-favorite-high-band`, filed as its own pre-registered theory.

The rule this follows: a slice re-weights output the parent already
produces. Where the population the mechanism needs is one the parent never
records, a slice is the wrong instrument no matter how well the predicate
is expressed.

## 2026-09-01 (cont.) — the 60-day out-of-population test: the side gap replicates, and it is composition

Same session. Answers the ticket `llm-market-identifier-0e` filed against
this theory mid-session (`tickets/open/2026-09-01-side-split-on-series-bias-obs.md`).
Full write-up: `studies/2026-09-01-side-split-60day-obs/`.

**The prize was real: 72,010 priced settled markets over 61 close days,
already on disk** in `studies/2026-08-29-series-bias-mining/data/collect.db`,
with a `side` column nobody had split. This theory's own series has 8 days.
Worked on a *copy* — a peer session is running a multi-hour backfill against
the live file.

### It replicated, and it replicated everywhere

Cell `ask in [0.90, 0.97)` — the band `insider_bias.screen` itself caps at,
so not a cap chosen here:

```
NO   n=9831  days=61   -6.66  SE 0.80  t -8.33
YES  n=2821  days=61  -10.61  SE 1.35  t -7.88
PAIRED NO-YES         +3.95  SE 1.31  t +3.03   41/61 days positive
```

and it survived every robustness view the ticket asked for:

| view | NO-YES |
|---|---|
| full window, 61 days | **+3.95** |
| close < 2026-08-20 (51 days, clean of the mining window) | **+3.94** |
| on-time settling stratum | **+8.62** |
| early-settled stratum | +1.34 |
| alternative decision point (24h pre-close) | **+11.02** |
| every band except 0.50-0.65 | positive |

Out-of-sample identical to in-sample. *Stronger* in the on-time stratum,
which is the direction the source study's pre-registered caution wanted.
Present and larger at an independent decision point. Monotone in price.
**I was ready to write this up as the strongest evidence the theory had.**

### Then the composition control killed it

NO favorites outnumber YES **5:2** here and the two sides are largely
**different series**, so a pooled gap can be a fact about which markets
happen to be NO-favorite. Of 584 series in the cell, 140 carry >= 5 rows on
both sides. Restrict to those, then difference within (series, close day):

```
all series, pooled by day              +3.95   t +3.03
both-sides series only, pooled by day  +1.92
WITHIN SERIES, WITHIN DAY              -1.85   SE 1.31  t -1.40   29/61 days+
```

Robust to weighting and to dropping any series:

```
day-clustered          k=61   -1.85  SE 1.31  t -1.40
series-equal-weighted  k=138  -1.04  SE 1.89  t -0.55
pair-equal-weighted    k=790  -1.68
leave-one-series-out          -2.58 .. -1.23   (base -1.85)
series leaning positive: 61/138  -- a coin flip
```

**The entire +3.95 is which series sit on which side.** Same failure the
calibration_harvest gradient review found on 2026-08-29 (38% of its
one-week step was composition); here composition is more than 100% of the
effect.

### Two things that are NOT findings, recorded so they are not re-read as ones

1. **Every level is deeply negative** — every band, both sides, -3.7 to
   -40. That is a board-wide sweep where much of the "ask" is a quote
   nobody would fill, not a signal to sell favorites. Only the *contrast*
   is readable here.
2. **The liquidity control is unusable and its apparent sign reversal
   means nothing.** Only 11% of cell rows carry backfilled spread/OI, the
   backfill has reached 59 of 659 series **in collection order**, so the
   subset is series-selected rather than random; and its YES arm is 71
   rows with 71 wins (21 from one boxing series), which is what produced
   the "t = +23.59". Open question, not an answer. Completing the backfill
   is what settles it.

### What it changes

- This is the strongest single piece of evidence about this theory to
  date and it is **negative** — 61 days and 72,010 observations against
  the 8 days of its own series.
- It does **not** kill the theory by its own rules: out-of-population, and
  the pre-registered kill bars are about its own cells on its own screen.
  A strong prior against, not a verdict. Status stays `testing`; no
  retirement proposed.
- **The composition control is now mandatory for any side comparison
  here**, including the proposed `no-favorite-high-band` — whose 8-day
  +1.70 has never had it applied. Added to that ticket as a
  pre-registration requirement, and it must be run *before* anything is
  pre-registered, not after.

## The same control on the SCREEN population — it does not reverse there

Run immediately after, on `studies/2026-08-29-side-asymmetry-extension/data/`
(868 settled favorites, 132 series, the 8 complete close days). Same
estimator: difference NO minus YES within (series, close day).

```
ALL BANDS (868 rows)
  >= 1 row/side:  65 series,  94 pairs, 8 days   NO-YES = +15.02  SE 14.55  t +1.03   6/8+
  >= 3 rows/side: 17 series,  51 pairs, 7 days   NO-YES =  +4.71  SE  8.18  t +0.58   3/7+

BAND 0.90-0.97 (333 rows)
  >= 1 row/side:  30 series,  45 pairs, 7 days   NO-YES =  +7.69  SE  4.38  t +1.75   5/7+
  >= 3 rows/side:   5 series, 19 pairs, 6 days   NO-YES = +11.44  SE  5.65  t +2.03   5/6+
```

**The sign does not flip.** On the screen population the within-series
contrast is positive at every cut, where on the sweep population it went
from +3.95 to −1.85. The two datasets disagree about the same question.

**Do not read the magnitudes.** These rest on 5 to 30 series over 6 to 7
days; the ≥3-rows/side line in the band is **five series**. The t of +2.03
is not significance after the number of cuts taken across this session, and
the estimator is the paired one that the 8-day pass measured to be the
noisiest available. Treat this as "the control does not kill it here",
nothing more.

**The likely reason the populations disagree is the obvious one, and it is
testable.** `insider_bias.screen` filters on `spread <= 0.07` and
`volume >= 500`; the board-wide sweep filters on neither, which is why
every level in it is −3.7 to −40 and why 23% of it sits at 0.98+ realizing
0.801. If the sweep's side gap is composition among *unfillable* quotes and
the screen's is not, both results are true and they are about different
populations.

**That makes the peer's backfill the decisive experiment, not a chore.**
Once `spread`/`open_interest` are populated across all 659 series rather
than the current alphabetically-reached 59, the sweep can be filtered to
the screen's own liquidity bar and the composition control re-run on it.
That single run decides between:

- the gap is composition everywhere, and the screen result is small-sample
  noise -> `no-favorite-high-band` should not be built; or
- the gap survives within series once quotes are fillable -> the screen
  result is the real one, on 61 days instead of 8.

Nothing should be pre-registered until that is known, and the cost of
waiting is a few hours of someone else's already-running job.

## 2026-09-01 — that run happened, at 100% coverage: the unconditional band effect is ZERO, so cell A is now the only thing that could resurrect it

Session `fleet-w1-g2`, study lane. The note directly above says one run
decides `no-favorite-high-band`, and that the cost of waiting is a few
hours of someone else's already-running job. The job finished, the run
was made twice, and this is what it returned. **This is context for cell
A, not a result about it** — the study measures a different population
and says so explicitly in its "What this study does NOT license".

**The answer to the question posed above: composition everywhere.**
`studies/2026-09-01-liquidity-filtered-side-split`, completion re-run at
99.95% backfill coverage (72,010 obs / 659 series / 61 close days, vs
26,941 / 227 at run 1). NO minus YES **within (series, close day)**,
inside `spread <= 0.07 AND open_interest >= 100`:

```
+0.05 pts   t=0.04   22/56 days positive   275 pairs over 114 series
LOO over 114 series: -0.61 .. +0.51, negative in 22/114
out-of-sample (close < 2026-08-20, clear of the mining window): -1.01  t=-0.76
```

Idea 33 is `dead`; the `new-theory` ticket is closed. Board-wide, the
+3.95 pooled side gap in the 0.90–0.97 band is composition, not a side
effect.

**Read the number as zero, not as negative.** Run 1 of that study, on a
37% alphabetical prefix, reported −1.02 and called the thesis actively
harmful on two checks — "significantly negative out of sample" (t=−2.13)
and "the OI ladder is monotone in the wrong direction". **Neither
survives full coverage.** The prefix was disproportionately soccer and
combat-sport totals. If you read run 1 and came away thinking the
opposite bet had promise, it does not: at 100% coverage no price band
has a mid-relative gross mispricing clearing |t| > 2.

### What this does and does not do to cell A

**It does not falsify `cell-a-no-favorite`, and it must not be used to.**
That cell screens `insider_bias.screen`'s population, which carries a
lifetime-volume bar this sweep does not, and its rows are forward
settlements at a live decision point rather than one historical anchor
per market. Different population, different entry, different data.

**What it does change is what a positive cell A would MEAN.** Before
today the honest reading of a positive cell A was ambiguous between
"NO favorites at 0.90–0.97 are underpriced" and "…and specifically so
inside this screen". The unconditional version is now measured and
absent on 659 series, so **only the conditional reading survives**: if
cell A clears its gates positive, the effect is a property of the
screen — its volume bar, its category mix, its event families — and not
of the price band. That is a materially narrower and more falsifiable
claim than the one the cell was registered under, and it is the version
to write up if the cell ever comes in.

The corollary matters for how the cell is defended. "The band effect is
real, we measured it board-wide" is **no longer available** as
supporting argument. Cell A now stands or falls on its own 5-day /
10-cluster gates, with nothing behind it.

Its revisit angle is recorded on idea 33 in exactly those terms.

### One field-level fact this theory should absorb

The liquidity filter's work is done by **`spread`, not
`open_interest`** — a 0.3-point gap between `oi==0` and `oi>=100` rows at
full coverage (−1.46 vs −1.14), against 2.9 points on the 37% prefix,
and an open-interest ladder inside the band that is not monotone in any
direction. If any future cell or slice here reaches for a liquidity
predicate, reach for spread first; open interest looks load-bearing and
measurably is not, at least on settled history at a single anchor.
