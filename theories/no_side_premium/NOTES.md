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

