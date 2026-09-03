# mention_family — backtest performance

**Distilled 2026-09-02 at migration.** The theory's code was deleted and
its raw backtest payloads never existed as files — this theory replayed
through the shared parent's `replay.py` and its own `backtest.py`, both
writing **into the ledger**, not into a `backtests/` folder. So the
underlying rows are still queryable and nothing here needs recovering
from a deleted artifact. The user's ruling of 2026-09-01 was "theory +
notes + backtest performance with details, not the entire backtest".

**Every number below comes from one of exactly three surviving sources**,
and each is labelled:

- **[rationale]** — the retirement rationale recorded on the theory's
  registry row (`theories.get(conn, 'mention_family')
  ['retirement_rationale']`), written by the session that proposed
  retirement on 2026-08-25.
- **[THEORY]** — `THEORY.md` beside this file.
- **[NOTES]** — `NOTES.md` beside this file.

Nothing here was estimated, re-derived or inferred. Where a number could
not be sourced from one of those three, it is absent rather than guessed.

The rows themselves outlive all of this — retirement deletes code, never
evidence:

    python -m tools.cli score report mention_family

## The two runs, and why the second one is the answer

| | bootstrap | full coverage |
|---|---|---|
| run id [THEORY] | `backtest-2026-08-24-stage1-90d` | `backtest-2026-08-25-mention-fullcov` |
| tier [THEORY] | A | A |
| what it walked [THEORY] | a 600-of-18,430 systematic sample of the shared stage-1 screen, of which **116 rows** were this family | **every** mention-family survivor in the API-reachable window: **11,084 survivors across 379 series**, **3,441 screen hits**, all settled |
| `calibration_edge_net` [THEORY] | **+5.48 pts** | **−1.53 pts** |

Same window, ~30x the markets, opposite sign. The second is not a
different test of a different period — the bootstrap's own window is a
subset of it **by construction** [NOTES], which is the entire point: it
tests whether the 116-row sample was lucky, and the answer is yes.

Coverage detail: **2,103 of the 11,084 survivors returned no candles** —
already past Kalshi's archival floor — so effective coverage is closes
**~2026-06-22 .. 2026-08-24** [NOTES].

## The headline, at full coverage

All [rationale] unless marked, and reproduced identically in [THEORY]:

| | |
|---|---|
| n settled | **3,441** |
| win rate vs mean price [THEORY] | **0.797** vs **0.802** |
| `calibration_edge` (gross) | **−0.49** |
| `calibration_edge_net` | **−1.53** |
| `roi_all` | **−1.9%** |
| fresh rows only (excluding the 116 the bins were fit on) [THEORY] | **−1.78** net |

The repo scorer and an independent script agree on these [NOTES].

**The family is priced essentially fairly, and a favorite-buyer loses the
fee.** That sentence is the whole result: the gross edge is already
negative, so this is not an edge eaten by costs.

## Every price bin, before and after

The bins were fit on the 116 bootstrap rows and then measured on the full
population. `THEORY.md` carries the "before" table under an **INVALIDATED
2026-08-25** banner; it is reproduced here only next to what replaced it.

| bucket | price range | bootstrap n / win rate / net [THEORY] | full-coverage n / win rate / mean price [THEORY] | full-coverage net [rationale] |
|---|---|---|---|---|
| `mention_family_lt75` | $0.65–$0.75 | 37 / 0.730 / **+1.87** | 1,132 / 0.678 / 0.694 | **−2.9** |
| `mention_family_75_85` | $0.75–$0.85 | 38 / 0.868 / **+6.38** | 1,003 / 0.785 / 0.796 | **−1.9** |
| `mention_family_85plus` | $0.85–$0.98 | 41 / 1.000 / **+7.88** | 1,190 / 0.913 / 0.909 | **+0.1** |

**Every bin is at or below zero net** [rationale]. `lt75` and `75_85` are
negative outright; `85plus` is *perfectly calibrated* — its bootstrap
41/41 was sampling luck [rationale], exactly as the same morning's
skeptical audit had suspected [NOTES].

That 41/41 had been flagged in advance. `THEORY.md` said, before the
rerun: *"Zero losses in 41 tries is strong evidence of a high win rate,
not proof of certainty… the true rate is very likely below 100%, so a
+7.88pts headline on this bin deserves more hedging than the other two."*
It read 0.913 at n=1,190.

**One reconciliation, recorded rather than smoothed over.** The
pattern-mining pass reports the same bin as **+0.11 net at n=1,231**
[THEORY, NOTES] against **+0.1 at n=1,190** [rationale, THEORY] from the
scorer. The two count slightly different row sets (the mining pass reads
"ask in $0.85–0.97" directly; the scorer reads the recorded bucket
label). Neither was reconciled before retirement, and both say the same
thing to one decimal place.

## Every sub-family, on fresh rows

[rationale], with the bootstrap column from [THEORY]'s audit entry:

| sub-family | bootstrap net [THEORY] | full-coverage, fresh rows [rationale] |
|---|---|---|
| World Cup sponsor mentions | **+8.3** (n=28) | **−0.94** |
| earnings-call mentions | **+6.1** (n=38) | **−3.82** |
| political speech (`KXTRUMPMENTION`/`SAY`/`ACT`) | **−5.2** (n=26) | **+0.05** |
| other | **+12.7** (n=24, a tail of n=1 series) | **−1.48** |

**All four land at ~zero or negative** [rationale]. The two that carried
the bootstrap — World Cup and earnings — were not seasonal edges that
expired; **they were noise** [NOTES].

This also resolves the audit's sharpest practical worry in the worst
possible way for the theory. The live preview slate was **100%
political-speech series** (TRUMPMENTION, WARSHMENTION, FEDMENTION,
SECPRESSMENTION) [THEORY] — i.e. the bootstrapped rates were being
applied to precisely the sub-population that had measured **−5.2**.

## The statistical case was already weak before the rerun

The skeptical audit of 2026-08-25 [THEORY, NOTES] checked the bootstrap
against the null *"the ask was already fair"*, with exact
heterogeneous-probability binomial tails:

| | p |
|---|---|
| `lt75` | 0.40 |
| `75_85` | 0.17 |
| `85plus` | 0.026 (41/41 at mean price 0.916 is only ~2σ) |
| pooled, gross | 0.0395 |
| **pooled, net of fees** | **0.070** |

And that is *before* any correction for this family having been
**selected** as the best-looking slice of a 200-row backtest containing
**115 series families**, with the price-bin boundaries then fit on the
same 116 rows [THEORY]. Nothing there survives a selection-aware read.

**What the audit checked and found clean**, which is why the failure is
inferential rather than mechanical [THEORY, NOTES]: no lookahead
(`replay_market` enters at the daily candle's closing ask with `screen()`
evaluated at that same timestamp); `no_ask = 1 − yes_bid` is exact on
Kalshi's complementary book; fees are in `edge_pts_net`; event clustering
negligible (**113 distinct events in 116 rows**, max 2 per event); and
sampled candle traces around nine `85plus` entries show stable pre-event
favorites with real entry-day volume (0.95 → 0.95 → settle 1.00), not
post-news stale quotes — so "entered after the mention already happened"
was rejected for the sampled rows.

## The diagnosis: every alternative explanation, ruled out

The `score-theories` checklist, answered [rationale]:

| could it be… | answer |
|---|---|
| small n? | no — **3,441** |
| a fee artifact? | no — **gross is negative too** (−0.49) |
| inverted? | no — **no side or bin is significantly positive** |
| one good slice? | no — per-series means at n≤25 scatter **+22 to −45 pts**, mean-zero noise, and **no slice was pre-registered** |
| version mixing? | no — **v1 throughout** |
| regime change? | no — **the same window as the bootstrap** |

Live agreement: the first live out-of-sample settlement,
**`KXTRUMPMENTION-26AUG24B-IRAN`, no @0.89 → resolved yes**, also lost
[rationale].

## Mining the dead dataset: what died, and the one thing that lived

A structured slicing pass over the 3,441 settled rows (**366 events, 135
series** [NOTES]) — timing bins, fine price bins, side × price, dtc ×
price, volume quartiles, spread bands, sub-family interactions,
per-series z-scores — each cell with exact heterogeneous-null binomial
tails plus an event-clustered t so correlated sibling strikes cannot fake
significance [NOTES]. All figures below [THEORY, NOTES]:

**Dead — the bootstrap's markers do not survive scale:**

- **Entry timing.** 0–4d: **−0.95 net (n=2,418)**; every timing bin
  negative; the 10–14d bin's claimed **+10.2** re-measures at **−3.06**.
  Only the literal last day (0–1d) is even breakeven, **+0.29**.
- **Price level.** 0.80+ as such: **−0.51 net (n=1,767)**. The old
  `85plus` bin is perfectly calibrated. Price level alone carries
  nothing — the bin's meaning was always just "ask in $0.85–0.97".
- **Per-series skill.** z-variance **1.19** against 1.0 binomial across
  the **96 series with n≥10**; the best series (`KXMTPMENTION`,
  **z=+2.27**) is within the expected maximum for 96 draws of noise.

**Survived every stress — side × price:**

- **NO favorites at ask ≥0.90: +2.25 pts net after fees** — n=450, 213
  events, `p_fair=0.0084`; positive in **all four sub-families, both
  window halves, both dtc slices**, and still **+1.86** excluding the
  ended World Cup series. NO 0.85+ pooled: **+1.88 (n=685, p=0.011)**.
- **YES favorites are overpriced in every band, −1.7 to −4.2 net**; YES
  0.80–0.90 is significantly *worse* than fair.
- **The mirror trade does not work.** Fading YES favorites by buying NO
  longshots at `1 − yes_bid` is **negative at every band** — the spread
  eats the mispricing. The optimism tax is only harvestable standing on
  the NO-favorite side near certainty.

**And its honest status, stated at the time:** found in a **~50-cell
post-hoc scan** with an **event-clustered t of only +1.4** — *a
hypothesis to pre-register, not a measured edge*. It was recorded on
backlog idea `no-side-premium`, whose Becker-based mechanism had
predicted exactly this asymmetry, and became its own theory. It was
**never** treated as a revival of this one: the both-sides price-bin
procedure is what was measured dead.

## Two facts about the harness that this theory established

- **Kalshi archives settled markets out of its public API roughly 60 days
  after close.** Established by systematic probing when the backward
  extension (closes 2025-08-25 .. 2026-05-26) returned **zero survivors**
  [NOTES]: the markets listing serves only never-traded husks beyond the
  floor, events keep shells back to 2025 with no markets attached, and
  candlesticks for archived tickers return empty. Two corollaries — the
  original "90-day" backtest was effectively a ~60-day one, and **the
  floor advances daily**, so historical evidence survives only if
  captured before it ages out.
- **`tools/buckets.edge_for` was ranking this theory by cheapness.**
  Corrected 2026-08-29 (after retirement): a bucket now contributes its
  own realized edge rather than being repriced against each candidate's
  ask. On the characterization fixture the top pick moved from a **$0.85
  candidate at +14.11 net** to a **$0.97 one at +8.21** [NOTES]. Price
  binning was the workaround that kept this survivable — inside a narrow
  bin a flat rate is nearly right — which is why the defect never showed
  here as it did on `insider_judgment`'s single 0.65–0.97 band. **The v1
  ledger rows were priced by the old formula and stay that way**; anyone
  reviving this must re-derive, not reuse, any ranking from that era.

## Structural facts about the population, for whoever asks the per-series question

From the bootstrap's 116 rows [THEORY]:

- **36% only became screen-eligible on the literal last day before
  close**, and most of the rest in the final 1–2 days; **only 12 of 116**
  were sitting as a favorite 10+ days out. A screen for this family has
  to run close to individual close dates — a recurring check, not a
  one-off scan.
- The confound is stated in the same place: those are *different markets
  selected by when each crossed into favorite territory*, not one market
  resampled at different entry times. **Whether delaying entry on an
  early-qualifying candidate helps or hurts was never tested.**
- On a live board (101,856 markets), **490 mention-family markets were
  open with the nearest close 14.6 days out** [NOTES] — outside the
  14-day screen. Zero live candidates was the correct answer, not a bug.

## The method lesson

A **~3% systematic sample (116 rows) produced +5.48 pts net with an
all-positive bin table on the same window where full coverage measures
−1.53** [NOTES]. Small backtest samples of a screen's own selection are
not weak evidence of the sample's claim — **they can be confidently
wrong.** Prefer full coverage of a scoped population wherever the fetch
allows it, and treat any sampled result as unconfirmed until it survives
the full walk.
