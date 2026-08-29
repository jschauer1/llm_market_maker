# insider_judgment — notes

Lab notebook: raw, dated, append-only. The format and the distillation rule
are in `theories/_TEMPLATE/NOTES.md`. Nothing here is private — any session
may read any theory's notes.

## 2026-08-25 — Notebook opened; where this theory's history lives

This file starts empty by design. Everything written before today stayed
where it was written, and none of it was migrated:

- **`THEORY.md` Learnings** — the distilled record: the reality-TV stage-2
  heuristic deliberately left unencoded until it is measured against the
  endorsed/rejected split, the `edge_basis='prior'` imported-history
  exception (LLM-introspected `q` values from `kalshi_trader`'s pick stage,
  kept precisely because they are the only dataset that can answer whether
  introspected probabilities realize their claimed edge), and the Big
  Brother correction.
- **`RESEARCH_LOG.md`** — the session narratives: the 2026-08-24 tier A
  backtest of the stage-1 screen, including the 47-minute false start that
  preceded it, and the 2026-08-24 Big Brother / mention-family follow-ups.
- **`theories/insider_bias/replay.py`'s module docstring** (this was
  `insider_judgment/backtest.py` until 2026-08-25; do not confuse it with
  the `backtest_fullcov.py` / `backtest_judged.py` drivers still in this
  folder) — the three constraints that shape
  the replay: combinatorial-series fetch scoping, the category pre-filter's
  status as a fetch-scoping decision rather than a change to the screen
  under test, and per-day versus cumulative candle volume.

From here on, raw findings about this theory land in this file, and
`THEORY.md` changes only when the claim, the procedure, or the status
changes.

## 2026-08-27 — v3's first score (+11.85 net, n=17) measures the screen, on one day

`score report insider_judgment` now shows v3 at `n=17`, win rate 0.941,
`calibration_edge_net = +11.85`. Two things about that number before anyone
banks it.

**1. It is not the theory's product.** All 17 settled rows carry
`disposition='screened'` — raw stage-1 screen output from
`live-2026-08-26-noscan`, recorded but never gated and never judged. 15 of
the 17 are sports (KXARGNACB, KXBOLPDIV, KXCPLMATCH, KXUSLSPREAD/TOTAL,
KXT20MATCH, KXKBOSPREAD, KXFIBAGAME, KXEGYPLGAME), all bought on the **NO**
side. The theory's actual recommendations — `endorsed`, n=8 outstanding —
have **0 settled**, so `interpretation_value` is still `None` and nothing
here says anything about whether the judgment stage adds or destroys value.

**2. All 17 settled on 2026-08-27, and that day flattered everything.**
Whole-population control over the same screen, priced from the
2026-08-27T01:06:07Z snapshot before any of it settled
(`studies/2026-08-27-settlement-day-clustering/`, n=99 settled of 109):
favorites beat implied by +5.40 net that day; 52/52 favorites priced
0.90–0.98 won.

The honest comparison for these rows is the day's **NO-favorite** baseline,
since that is what they are: n=44, **−3.05** net. Against that, 16/17 at
+11.85 is roughly +15 pts of outperformance — the one genuinely interesting
number here, and it is drawn from one settlement day with `n_days=1`, so no
standard error exists for it. Under the naive row-level SE it would look
like ~2σ; it is not.

Worth noting rather than acting on: on 08-25 the population's NO favorites
ran **+7.98** net and its YES favorites −1.42, i.e. the side split reverses
day to day. Whatever these 17 rows show, one day cannot distinguish "the
screen picks good NO favorites" from "NO favorites had a day".

**Nothing changes about the theory.** Status stays `testing`, v3, no
version bump, no claim added or withdrawn — this is a note about how to
read a score, not about the procedure. The lifecycle trigger (n=20 with
net ≤ 0) is not close and would not fire on this anyway.

**What to watch:** the 8 endorsed rows are the ones that matter, and the
GTA video-length ladder (4 legs) plus both Big Brother legs settle tonight —
that is the first real read on the endorsed tier. Track it with
`score report insider_judgment | jq .settlement_days.endorsed` and wait for
`n_days`, not `n`, to grow.

## 2026-08-27 (later) — the tier-B judged backtests do not survive day clustering

Follow-on from the settlement-day clustering study. Historical backtests
previously could not be day-clustered at all — the replays recorded
settlements with no `resolved_at`. Recovered from `extra_json`
(`entry_day_iso + days_to_close_at_entry`) with no API call; see
`studies/2026-08-27-settlement-day-clustering/backfill_resolved_at.py`.

| run | n | days | row net | day net | row SE | day SE |
|---|---|---|---|---|---|---|
| insider fullcov (screen only) | 3,195 | 66 | −1.15 | −1.16 | 0.63 | 1.12 |
| judged s200 | 704 | 58 | **+0.67** | **−0.35** | 1.27 | 2.50 |
| judged s200b | 644 | 63 | −0.02 | +0.35 | 1.37 | 2.33 |
| judged s57 | 216 | 30 | **+1.90** | **−1.36** | 2.02 | 4.78 |

**The judged runs flip sign purely on how days are weighted**, and their
clustered SEs swamp either estimate. Row-weighting over-counts busy
settlement days, so a handful of good heavy days lifts the row-weighted
figure — precisely the confound the study documents, appearing in the very
runs that were meant to validate v3's buckets (the s-series completed 100%
judgment coverage of the gate-plausible population and carried
pre-registered cells: strong-NO positive, moderate-NO positive, bucket
ordering).

An estimate that changes sign under reweighting is not evidence in either
direction. It does not say the buckets are wrong; it says these runs
cannot tell us.

**What changes, and what does not.** Status stays `testing` — which
already means "running, claims not demonstrated", so nothing about the
theory's standing moves. No version bump: the procedure is untouched.
What changes is the promotion bar: **v3 must not go `active` on the
s-series**, because day-clustered they show nothing. The stage-1 screen's
own number (−1.16 ± 1.12) is likewise not distinguishable from zero,
though it was never the theory's claim — the claim is that stage-2
judgment adds edge on top of it, and `interpretation_value` is still
`None` because the endorsed tier has no settled rows.

**So the live endorsed tier now carries the weight the backtests cannot.**
First settlements are due tonight/2026-08-28: the GTA video-length ladder
has converged in-market to the endorsed [15,30) view (all four endorsed
legs 187, 188, 9238, 9239 quoted at 1.00), and both Big Brother legs
resolve tonight (TAY looks a win, NO at 0.91; DRE looks a loss, NO down to
0.44 from the 0.82 entry). That would be roughly 5 wins and 1 loss.

**Read it with `settlement_days`, not `n`.** All six settle the same
night, so it will come back `n_days=1` with no computable SE — a first
data point, not a verdict, and the temptation to call a 5-1 start
"validation" is exactly what this whole day's work exists to prevent.

## 2026-08-28 — the `weak` bucket graduated on one day of gate leakage

Live run `live-2026-08-28`, stages 1–6, judged in-session (no subagent
dispatched this session), 216 candidates over 119 events. **Nothing
endorsed.** Funnel: 110,399 board → 767 screened → 321 events → gate
removed 202 → 119 survivors / 216 markets. Gate counts: live sport 58,
aggregate-of-many 43, weather 32, commodity/FX/rates 23, compute
16, crypto 13, scheduled indicator 10, retail price index 7.

**The finding is in the bucket layer, not the board.** `buckets.py`
promoted `weak` from `prior` to `edge_basis='measured'` this run, because
the bucket crossed `MIN_BUCKET_N = 10` on 17 settled rows. All 17 of
those rows:

- settled on **one day**, 2026-08-27 (`n_days=1`), and
- are **NO favorites on live sport** (Argentine basketball, Bolivian
  football, CPL, Egyptian football, FIBA, KBO, T20, USL) plus one diesel
  strike — i.e. every one of them is a `gate.py` leak into a family this
  theory's thesis explicitly excludes.

16/17 won, which is simply what a 0.70–0.96 NO favorite does. The bucket
layer then applied that 94.12% as a **flat win probability to every weak
candidate regardless of its own price**, which mints apparent edge on
anything quoted below 0.94: 150 of 216 rows came back "positive edge",
all of them junk. Stage 3 declined all 190 weak rows on that basis.

Three separate defects stacked here, worth separating:

1. **`MIN_BUCKET_N` counts rows, not settlement days.** This is the exact
   confound the 2026-08-27 clustering study measured, and the amendment
   `no_side_premium` adopted (`n_days >= 8`). `buckets.py` has no
   equivalent, so one lucky settlement day can graduate any bucket.
2. **A flat bucket rate ignores the candidate's own price.** A single
   `win_rate` applied across a 0.65–0.97 band is not a calibration; it is
   a constant, and it is mechanically guaranteed to claim edge on the
   cheap end of the band and negative edge on the expensive end.
3. **Gate leakage contaminates the bucket rates, not just the scan.**
   `gate.py` misses FIBA, KBO, CPL, T20, USL, Argentine/Bolivian league
   football and `KXEURUSDAW`; those leak to the deep stage, get judged
   `weak`, settle at sport-favorite base rates, and then *define* what
   `weak` is worth. The gate's known failure mode was "a false
   elimination is invisible" — this is the mirror: a false *survival*
   silently becomes the theory's own yardstick.

Rejecting all 190 is also the repair path: they span many future
settlement days and many families, so once they settle the weak bucket's
rate is measured on something other than one night of football.

**Also recorded, and separately useful:** the Big Brother week-7 legs
(`KXBIGBROTHERELIMINATION-26AUG27-{DRE,MAL,TAY}`) were priced on a
168-minute-old board and the episode aired inside that window — Drew won
the Block Buster and came off the block, Mallory was evicted. A re-quote
showed 0.99/0.01/0.01. The board freshness window
(`DEFAULT_MAX_AGE_MINUTES = 240`) is far too loose for a market that
resolves during it; the general rule stands that a re-quote is mandatory
before recommending, and this is the concrete case that proves it.

**Rules divergences found this run** (9 events), all of which cut against
the NO side the screen picks: `KXCABLEAVE` (rules resolve YES on merely
*announcing* a departure), `KXGEMINI-GEMI35P` ("Gemini 3.5 Pro **or
greater**"), `KXTRUMPMEET` (phone calls count as a "meet"), `KXUAPFILES`
(any *federal government* UAP release, not just Trump). Narrower-than-
title, therefore helping NO: `KXGTATRAILER` (≥30s), `KXMAMDANIEO`
(non-emergency only), `KXPIRROOUT` (actually leaves, not announces),
`KXITALYBORDERCHECK` (not replaced by equivalent checks),
`KXBIGBENDRESUME` (agency-reported).

## 2026-08-29 — the same three bucket defects, reproduced live; first endorsed settlements land

Live run `live-2026-08-29`, stages 1–6, judged in-session by
claude-opus-5 (no subagent dispatched). Funnel: 117,272 board → 740
screened → 328 events → gate removed 198 → 130 survivors / **232
markets**. Gate counts: live sport 59, aggregate-of-many 40, weather 28,
compute/collectible 21, commodity/FX/rates 17, crypto 15, scheduled
indicator 15, retail price index 3.

**Verdicts: 122 weak, 9 moderate, 0 strong** (131 events judged; the
screen re-ran a few minutes after the payload was built and 130 of the
131 survived the moving days-to-close boundary). **Nothing endorsed —
second consecutive run.**

### The bucket layer failed the same way, one bucket over

Last session's three stacked defects were diagnosed on a `weak` bucket
graduated by 17 rows from a single night of gate-leaked football. The
settle pass this session added 95 settlements and the bucket is now
`weak` n=67, win rate 0.7761 — a much broader base. **The defect did not
go away; it moved.** A flat 0.7761 applied across a 0.65–0.97 band still
mints "positive edge" on everything priced below 0.776 and nothing above,
which is defect 2 (a constant is not a calibration) surviving untouched
by a 4× larger sample. This run it produced 16 weak-bucket "positive
edge" rows: Taça de Portugal football, a T20 cricket match, Hulu app
downloads, South Africa GDP, US PPI, a Creed Aventus retail price. Every
one is a family the thesis explicitly excludes.

Defect 3 (gate leakage contaminating the rate, not just the scan) is
likewise still live and is *why* the rate reads 0.776: the weak bucket's
settled rows remain dominated by live-sport NO favourites, so what the
theory calls "weak" is being defined by a population its own thesis
excludes.

Defect 1 (`MIN_BUCKET_N` counts rows, not settlement days) is unchanged
in `buckets.py`. Day-clustered, the live record is `n=74, n_days=2`,
calibration_edge_net **−0.96 ± 12.9** — indistinguishable from zero
either way. The row-weighted −7.89 that the same report prints is the
confound, not the finding.

The `moderate` bucket (n=5, below MIN_BUCKET_N) still pays its declared
prior of +2.0 net **regardless of price**, which is the same defect in
its other form: it claimed +2.00 on a NO leg quoted at 0.97 as readily as
on one at 0.77.

### Stage 6 declined all 232, in two groups

- **214 weak rows** — declined as an arithmetic artifact, per the above.
- **18 moderate rows across 9 events** — declined individually:
  - `KXTRUMPMEET` (8 legs): rules count **phone calls** as a meeting,
    broader than the title, cutting against every NO leg the screen
    chose.
  - `KXCABLEAVE`: rules resolve YES on merely **announcing** a departure
    — same direction, against NO at 0.95.
  - `KXPRESSSECANNOUNCE`: rules count an **acting/interim** naming —
    again broader, against NO at 0.83.
  - `KXAKDROPOUTAUG` (3 legs): researched. Alaska Public Media
    (2026-08-17) reported the two leading Democrats are *discussing*
    whether one should quit if both make the top four; Begich sat 2nd at
    20.0% on the 08-26 count. That fails two final-review tests at once —
    the group's knowledge is already in the press (no asymmetry) and
    "discussing" is an unmade decision.
  - `KXGTATRAILER` (NO 0.97), `KXHEARNCHARGE` (NO 0.97),
    `KXNEWDRUGAPPLICATIONCMPS-360` (NO 0.96), `KXCLAUDE-NXTMYTH` (NO
    0.77), `KXGROK-GROK47` (NO 0.86): the thesis genuinely applies to
    each — a company knows its own ship date, prosecutors know their own
    charging decision — but the claimed edge is a **prior**, not a
    measurement, and at 0.96–0.97 the fee consumes most of a 2-point
    claim.

### Researched, and worth recording as a correction

**AGT is not a pre-taped-TV case.** `KXAGTELIMINATION` looked like the
thesis's strongest sub-case on its face. Season 21's quarterfinals are
**live** performance and results shows (round 3 airs Sep 1–2, 2026)
decided by America's public vote — an aggregate of millions of
independent voters, i.e. the exclusion, not the thesis. Judged `weak`.
Reality-TV tickers are not interchangeable: the distinction that matters
is taping-already-in-the-can versus a live audience vote, and only the
resolution timing tells them apart.

**`KXALBUMDEBUT` carries a source-timing risk worth reusing.** Rod Wave's
album released 2026-08-28, so the chart-tracking week was one day old at
judgment; industry projections become privately known mid-week, but not
today. Separately, the Billboard 200 dated Sep 12 publishes around Sep 8,
**after** this market's Sep 7 close.

### First endorsed settlements — read them as one day, not six rows

Six of the nine queued endorsed positions settled, **all six won**: the
GTA video-length ladder (187 YES-10 @0.93, 188 YES-15 @0.87, 9238 NO-30
@0.85, 9239 NO-45 @0.94) and both Big Brother legs (192 NO-DRE @0.82,
9134 NO-TAY @0.65). The 2026-08-27 note predicted DRE a loss with NO down
to 0.44; it resolved NO. **All six settled on 2026-08-28 — `n_days=1`,
no computable SE.** `interpretation_value` is now +34.4 (endorsed n=3 at
100%, rejected n=51 at 68.6% against 84.5% implied), which is a first
data point and emphatically not validation: the endorsed tier is three
rows on one night.
