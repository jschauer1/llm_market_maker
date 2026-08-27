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
