# No-Side Premium

## Hypothesis

Retail flow buys YES. At equal prices the affirmative side of a question
underperforms the negative side — an "optimism tax" paid by hope-driven
takers that nobody's hope pushes into NO. Where that flow concentrates,
NO favorites are underpriced and YES favorites overpriced, independent
of the price-level bias a calibration theory would capture.

Why it persists: the tax is a behavioral flow imbalance, not a
mispricing anyone can see on one market; and at favorite prices the
per-contract profit is small enough that pros don't queue to collect it.

Full design rationale: `tickets/new-theory/completed/2026-08-24-no-side-premium.md` (registry idea
`no-side-premium`); external evidence (Becker microstructure; Reichenbach
& Walther 2025) cited there.

## Evidence so far (why this is a forward test, not a bet)

Two full-coverage tier-A backtests measured the asymmetry:

- mention fullcov (`backtest-2026-08-25-mention-fullcov`, n=3,441): NO
  favorites at 0.90+ underpriced, **+2.25 net**, stable across
  partitions; YES favorites overpriced everywhere.
- insider fullcov non-mention (`backtest-2026-08-25-insider-fullcov`,
  n=3,181): YES favorites 0.80–0.90 **−3.89 net** (−5.80 in the
  gate-plausible slice); every NO band ≥ its YES counterpart below
  $0.90. But the mention cell did **not** replicate here (+1.04,
  p=0.09), and this population's best NO cell (0.65–0.80, +4.32) was
  negative on the mention population.

Band structure moves between populations; only the side-level direction
is consistent. Per the pairing discipline, the durable claim was
pre-registered (idea 14 revisit angle, 2026-08-26) and nothing is bet
until forward settlements measure it.

## Decision procedure (fully mechanical, v1)

Population: `theories.insider_bias.screen.screen()` — favorites
0.65–0.97, spread ≤ 0.07, volume ≥ 500, ≤ 14 days to close — the exact
screen both backtests drew from (imported, not copied; parameters
pinned by `tests/theories/test_no_side_premium.py`). Live runs refresh
every candidate's ask (batched quotes) and record the scan-time ask; a
row whose fresh ask leaves its cell is dropped, because the cell
definition is the pre-registration and does not stretch.

Two cells, disjoint by construction:

| cell | population slice | recorded as | claimed edge |
|---|---|---|---|
| A | mention-family series, NO favorite, no-ask ≥ 0.85 | `screened`, outcome=no | +2.0 net, `prior` |
| B | non-mention, YES favorite, yes-ask ∈ [0.80, 0.90] | `rejected`, outcome=yes | −3.9 net, `prior` |

Cell B is an avoid-list: rejected rows settle as a free control, which
is exactly what testing "these lose" needs. `edge_basis="prior"`
everywhere — **nothing this theory emits is a recommendable bet in v1**,
and any session reporting its output must say so.

Scoring separates the cells with no extra machinery: `disposition=
'screened'` scores cell A, `'rejected'` scores cell B
(`interpretation_value` is meaningless here and ignored — the
dispositions encode cells, not judgment).

## Stage 2 — none

No gate, no judgment, no prompts. Tier A by construction.

## Pre-registered outcomes (2026-08-26)

- **Cell A confirms** if its forward `calibration_edge_net` > 0 at
  n ≥ 40 settled (interim look; ~±4.7 pts SE) and stays positive at
  n ≈ 150 (~±2.4 pts, enough to resolve a +2 claim). On confirmation:
  version bump, `edge_basis` moves to `measured`, rows become
  recommendable.
- **Cell B confirms** (avoid validated) if its forward
  `calibration_edge_net` < 0 at n ≥ 60. On confirmation the tradeable
  mirror (NO at 0.10–0.20 against these favorites) becomes a *new*
  pre-registered cell — the mirror is not automatic, fees are paid both
  ways.
- **Kill cell A** if ≤ 0 at n ≥ 150. **Kill cell B's claim** if ≥ 0 at
  n ≥ 150. Both dead → propose retirement, record against idea 14 that
  the side effect did not survive out-of-population forward testing.

### Amendment, 2026-08-27 — every bar above also requires `n_days ≥ 8`

Rows are not independent draws. The settlement-day clustering study
(`studies/2026-08-27-settlement-day-clustering/`) measured this screen's
whole population over three consecutive close-days and found the
day-level favorite edge swinging +4.26 / −7.29 / +5.40 net, with the
YES/NO split *reversing* between days (08-25: YES −1.42, NO +7.98;
08-27: YES +12.15, NO −3.05). This theory measures exactly that split,
so a row-counted sample spanning three settlement days cannot resolve a
2-point side effect however many rows it holds.

So each bar above now reads "**and** `n_days ≥ 8`", where `n_days` comes
from `score.settlement_day_clusters()`, and the interim look additionally
requires the day-clustered SE to be reported alongside the point estimate.

This is a post-hoc amendment to a pre-registration, which is normally
exactly the wrong thing to do. Why it is admissible here: it was derived
from a **control population** (215 markets, whole screen, none selected
on outcome), not from this theory's own rows; and it makes confirmation
strictly **harder** in both directions — no bar was loosened. It does not
bump the version because the decision procedure — population, cells,
sides, price bands, recording — is untouched; only the evidentiary bar
for reading the results moved.

**Worked example of why it was needed:** cell B's first 12 settlements
came in 12/12 (+14.59 net), which read naively falsifies its −3.9 claim.
All 12 settled on 2026-08-27, a day on which **all 55** YES favorites in
the population won. Cell B did not beat that day; it was a subset of it.
Under the amended bar that sample is `n_days=1` — one draw, no computable
SE, no reading either way. See `NOTES.md` 2026-08-27.

## Slices (2026-08-29)

Both cells are **registered slices** (`cell-a-no-favorite`,
`cell-b-yes-avoid`; `cli slices report no_side_premium`), backdated to
the 2026-08-26 pre-registration above. The slice machinery reproduces
this theory's status numbers independently (cell B forward: n=46 /
n_days=3 / −10.44 net, day SE 12.7 — unmeasured, matching the day
amendment's reading) and adds the segment bookkeeping: every row is OOS
by settlement date because the motivating fullcov evidence lives in
sibling theories' ledgers. The bars in "Pre-registered outcomes" remain
the confirmation criteria — slice readiness (10 clusters / 5 days)
gates only how ranking reads the cells, and cell B is an avoid-list
whose ready state should show a *negative* record. Registration changed
no procedure; no version bump.

## How to backtest

The tier-A measurements above are the backtest; they are recorded in
`backtest_runs` and the idea registry. Nothing in the forward procedure
uses an LLM. Replaying the two cells over stored snapshots adds no
information beyond the fullcov runs (same window, same data) and is not
planned.

## Status

`testing` — 2026-08-26: forward test running; rows accrue each session.
2026-08-27: cell B has 12 settled rows across **1** settlement day; under
the day amendment above that is unmeasured, not a result. Cell A has 0
settled (its rows are KXTRUMPSAY-26AUG31 strikes, closing 08-31).
2026-08-29: cell B at n=46 / **n_days=3** reads -10.44 net pooled, but its
per-day net is +14.18 / -29.74 / -4.93 with a day-clustered SE of **12.73**
— still unmeasured, now in the other direction. Cell A still 0 settled.
Measured instead on the **paired within-day** statistic the claim actually
makes (`NO_net - YES_net`, which cancels the day effect) over the clean
snapshot population: **mean +8.25 pts, n_days=5, SE 7.60, 4/5 days
positive** — right sign, not significant, bar is 8 days. Per-side day means
land at YES **-4.42** (claimed -3.9) and NO **+3.83** (claimed +2.0). Full
write-up: `studies/2026-08-29-side-asymmetry-extension/`; report this
theory on the paired statistic first, `compute_score` alongside.

**2026-09-01 — the `n_days >= 8` bar is reached, and the paired claim is
null.** `n_days=8` (close days 08-24 through 08-31; 09-01 excluded at 18%
settled under a >=90% rule fixed before the numbers). Mean `NO - YES` =
**+2.91 pts**, day-clustered SE **5.51**, t = +0.53 on 7 df, 95% CI
**[-7.89, +13.72]**, sign test 5/8 (p=0.727). Per-side: YES **-2.16**
(claimed -3.9), NO **+0.75** (claimed +2.0). Pass 1's +8.25 at 5 days, and
both of its per-side estimates, moved toward zero as days were added.
**Unconfirmed, not disproven** — the CI still contains +2.

**And the paired estimator turns out to be the wrong instrument, measured
rather than argued.** It was adopted because the day effect "is a common
shock to both sides, so it cancels". It is not: the YES and NO favorites
in this screen are different markets on different subjects, not two sides
of one contract. Between-day SD, and days needed to detect +2.0 at 80%
power:

| estimator | SD | days |
|---|---|---|
| paired NO-YES, all bands | 15.59 | **477** |
| NO 0.90-0.97, single side | **5.64** | **62** |
| NO all bands, single side | 6.90 | 93 |
| YES all bands, single side | 12.46 | 304 |

The pooled paired claim is therefore **unresolvable on any practical
horizon** (477 settlement days against a ~60-day archive window). **Report
this theory on the single-side `NO 0.90+` figure first**, `compute_score`
alongside; the paired statistic is retained only as the 5-day-vintage
comparison. Like the 08-27 day amendment this changes the reading, not the
procedure — population, cells, sides, bands and recording are untouched —
so there is no version bump.

Where the structure sits, day-clustered over 868 settled favorites:
`NO 0.90-0.97` (**cell A's mechanism, pre-registered**) reads **+1.70 +/-
1.99, 7/8 days positive** against a +2.25 fullcov measurement and a +2.0
prior — the tightest cell on the board and the only one whose size, sign
and stability all match a prior fixed before the data, but t=0.85 and *not
significant*. `YES 0.80-0.90` (cell B's mechanism) reads **-0.86 +/- 5.64**
— the -3.9 prior is not reproduced.

**Cell A's population is 15 rows on 2 of 8 days** (zero mention-family YES
rows at all). Its own bars (`n>=40`, `n_days>=8`) are a long way off, and
**the band carries the signal while the family restriction starves it**:
`NO 0.90-0.97` across the whole screen is 275 rows over 8 days, 18x the
population, at a comparable point estimate. Cell A is **not** widened in
response — that is the move a pre-registration exists to prevent — and the
wide version is filed as its own pre-registered theory (idea and ticket
`no-favorite-high-band`), exactly as this theory came off `mention_family`.

Neither cell is killable by its own rule (cell A kills at <=0 with n>=150,
sits at n=20/+4.33; cell B kills at >=0 with n>=150, sits at n=109/-0.98),
so no retirement is proposed. Status stays `testing`, `edge_basis='prior'`,
nothing recommendable. Full write-up:
`studies/2026-08-29-side-asymmetry-extension/` "Pass 2".

## Version

1 — initial: the two pre-registered cells exactly as idea 14's revisit
angle states them; population pinned to insider_bias screen defaults;
live ask refresh before recording.

**2026-09-01 (cont.) — the largest test of this theory's direction claim
ever run, and it is negative on its own terms.** A 61-close-day,
72,010-observation out-of-population dataset (the series-bias sweep) was
split by side for the first time. In band 0.90–0.97 the pooled gap
replicated hard — **+3.95 pts, t=3.03, 41/61 days**, identical
out-of-sample (+3.94 over 51 clean days), stronger in the on-time stratum
(+8.62), larger at an independent 24h decision point (+11.02), positive in
every band but the cheapest. **All of it is composition:** NO favorites
outnumber YES 5:2 there and the sides are largely different series, so
differencing within (series, close day) gives **−1.85 (t=−1.40)**, robust
across weightings (−1.04 to −1.85) and to dropping any series (−2.58 to
−1.23), with 61/138 series leaning positive.

**But the same control on this theory's own screen population does not
reverse** (+7.69, t=1.75 in the same band; 30 series, 7 days — too thin to
read as a magnitude). The populations disagree, and the candidate reason is
that `insider_bias.screen` filters `spread ≤ 0.07` and `volume ≥ 500` while
the sweep filters neither — every level in the sweep runs −3.7 to −40,
which is a book nobody would fill rather than a mispricing.

Consequences: the sweep result is **out-of-population**, so it does not
trigger this theory's own kill bars — a strong prior against, not a
verdict, and status stays `testing`. **A composition control is now
mandatory for any side comparison in this repo**, this theory's included.
The deciding experiment is the series-bias liquidity backfill completing,
after which the sweep can be filtered to the screen's own bar and the
control re-run. Write-up: `studies/2026-09-01-side-split-60day-obs/`.

**2026-09-01 (cont., `fleet-w1-g3`) — both cells measured CLEAN of the
early-close anchor bug, and cell B is two settlement days from its own kill
bar.**

`studies/2026-08-29-early-close-exposure-existing-backtests` named this
theory as needing a specific look and then reasoned rather than measured
("Both look safe, but that is a reasoned expectation, not a measurement").
It is now measured. Over all 281 tickers this theory has ever recorded —
**281/281 fetched from Kalshi, 0 aged out** — the exposed fraction is
**zero in both cells**:

| cell | n | clusters | headline | EXPOSED | CLEAN | contamination bound |
|---|---|---|---|---|---|---|
| A | 20 | 2 | +4.33 | **n=0** | +4.33 | **0.000 pts** |
| B | 150 | 116 | +0.46 | **n=0** | +0.46 | **0.000 pts** |

Because the bound is `f x d` and `f = 0`, this is decisive without needing
the exposed-vs-clean contrast to be significant — which it never could have
been on a 170-row theory. **Both cells' numbers are uncontaminated, so the
bars below read against clean data.** Cell A's 29 classifiable tickers are
26 `KXTRUMPSAY` plus three others, all with the deadline *before* close;
cell B's 150 rows are date-certain settlement ladders and sports games,
which carry no by-deadline deadline at all. Four validity checks (threshold
distribution, family composition, a regex sweep for missed phrasing, and a
parse-free `expected_expiration_time` check) are in `NOTES.md`; procedure
in `exposure.py` / `exposure_measure.py`.

**Cell B, on the bar as written.** The kill condition for cell B's claim is
`calibration_edge_net >= 0 at n >= 150`, and per the 2026-08-27 amendment
also `n_days >= 8`. It now stands at **n = 150 exactly, +0.46, over 6
settlement days** — value and row count both met, **the day count short by
two.** So the claim is *not yet* falsified by its own rule, and it is as
close to falsified as it can be without being so.

Two things must be said alongside that, because they cut in opposite
directions and the pre-registration does not adjudicate between them:

- **The day-clustered statistic has NOT crossed zero.** Per-day mean
  **−0.28**, day-clustered SE **6.09**, 4/6 days positive. The 2026-08-27
  amendment reads the bar on `calibration_edge_net` (the row-level figure)
  and requires the day SE *reported alongside*, which is the reading
  applied here — but on the statistic that same amendment was written
  because rows are not independent, cell B is nominally still on the
  claim's side. **When the eighth settlement day lands, the bar will fire
  on a statistic whose sibling says the opposite.** That tension is
  recorded now, before the data arrives, so resolving it later cannot be a
  post-hoc choice. It is flagged for a governance ruling rather than
  settled here.
- **Neither reading is distinguishable from zero.** t = +0.15 row-clustered.
  The honest statement remains the ticket's: what the data excludes is the
  **magnitude**, not the sign — a −3.9 avoid effect is not there. "YES
  favorites at 0.80–0.90 are priced about fairly" is what this supports;
  "they are underpriced" is not.

**And the −3.9 is not hiding in a subset.** 16 exploratory cuts over cell
B's 150 rows / 116 clusters — by family (9 groups), entry-price band (3),
ladder-leg vs discrete, and a volume median split — produce **no partition
distinguishable from zero**, and none negative at readable size. The two
apparent standouts (`index-rate` +12.69, `tech-compute` +12.45) rest on 6
and 4 rows over 2 and 1 settlement days, which is the single-observation
amplification this repo has already documented twice. Procedure and full
output: `mine_cells.py`, `data/mine_cells_result.txt`. Per the pairing
discipline nothing here is registered as a slice, because nothing survived
to register.

So **cell A is now the theory's only live claim**, exactly as the
2026-09-01 liquidity-filtered study anticipated — and its constraint is not
evidence quality but **event clusters: 2, against a gate of 10.**
