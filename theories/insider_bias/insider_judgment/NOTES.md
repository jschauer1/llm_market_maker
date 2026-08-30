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

## 2026-08-29 (cont.) — v4: a bucket contributes an edge, not a probability

The three stacked defects of 2026-08-28 turned out to be two mechanical
bugs and one contamination, and the first two are now fixed in
`tools/buckets.py`. **`insider_judgment` bumps to v4.**

### Defect 2 was the load-bearing one, and it was a sign error in kind

`edge_for` computed `(bucket_win_rate − this candidate's price) × 100`.
That reads the bucket's *pooled win rate* as *this candidate's
probability*, which makes the claimed edge move 1:1 with price. It is not
a calibration — it is a bet that price carries no information at all.

Concretely, on this theory's own live `weak` rate (n=67, win 0.7761,
mean entry 0.8446):

| candidate ask | old claim | corrected claim |
|---|---|---|
| 0.66 | **+10.04** measured | +0.00 prior |
| 0.72 | **+4.20** measured | +0.00 prior |
| 0.85 | −8.28 measured | +0.00 prior |
| 0.97 | −19.59 measured | +0.00 prior |

A 30-point swing driven entirely by price, out of a bucket whose actual
realized edge is **−6.85 points**. The corrected formula carries
`(win_rate − mean entry price of the rows that measured it)` — how far
the bucket beat the prices it was really bought at — and lets only the
fee depend on the candidate's own price.

Three things that had silently disagreed now agree: the prior path
(always points of edge), `score.compute_score` (which *grades* this
theory on `win_rate − price_implied_rate`), and `Edge.model_prob` (now
this candidate's price plus the bucket's edge, not a pooled rate
describing other prices).

### Defect 1 fixed as `MIN_BUCKET_DAYS = 5`

`score.bucket_rates` now reports `n_days`, and a bucket must span five
distinct settlement days before it may replace its prior. A rates dict
that cannot supply `n_days` or `mean_entry_price` **fails closed** to the
prior — an unverifiable measurement is not a measurement, which is the
same false-survival failure that let one night of football define
`weak`. `bucket_rates` snapshots persist `n_days` too (nullable: unknown
must read as unknown, never as zero).

Live effect: all three of this theory's buckets are currently `n_days`
1–2, so **every bucket falls back to its prior** and the 16 junk
"positive edge" rows this run produced could not be minted at all.

### Defect 3 (gate leakage) is NOT fixed

`gate.py` still passes FIBA, KBO, CPL, T20, USL, Taça de Portugal,
Argentine/Bolivian league football and the Carbon Arc vendor-metric
family. That is a `gate.py` change and a separate version bump; it is the
next thing to do here. What has changed is that leakage can no longer
*define* a bucket on one night — it still contaminates the population.

### A found bug in a retired sibling, worth recording

The same correction re-ranks `mention_family`'s golden output, and the
diff is the defect in one line: the old top pick was a **$0.85**
candidate at +14.11 net, the corrected one a **$0.97** candidate at
+8.21. The old formula was sorting that theory by *cheapness*, because
every candidate in a price bin got repriced against that bin's win rate.
`mention_family` is retired and records nothing, so no version was
bumped; the pre-correction arithmetic is preserved unmodified in
`tests/characterization/goldens/mention_rank_wide.json` and the
correction itself is now locked by
`test_the_bucket_edge_correction_is_visible_in_the_goldens`.

## 2026-08-29 (cont.) — defect 3 closed: the gate reads rules now, 130 survivors → 18

The last of the three 2026-08-28 defects. `gate.py` classified by
series-ticker prefix only, which means it knows exactly the families
someone has already typed into it — and Kalshi adds families faster than
that. Measured over the whole 117,272-market board:

```
328 screened events
-198 removed by the prefix allowlist (v2)
=130 survivors, of which 109 were STILL families the thesis rejects
```

84% of what reached the expensive stage was junk, and not stragglers —
whole categories: 39 Carbon Arc vendor-panel events, 47 sport fixtures
across a dozen unenumerated leagues, 7 OpenRouter share events, 3
Metacritic events.

### The fix is to match resolution mechanics, not names

A Carbon Arc panel says "Carbon Arc" in its own resolution rules whatever
its ticker is called, so one pattern covers every such series Kalshi ever
adds. Four rules-text rules, each measured against every series on the
board before being written:

| rule | series caught | markets | false positives |
|---|---|---|---|
| sport fixture | 611 | ~23,000 | none |
| Carbon Arc vendor panel | 77 | 956 | none |
| statistical release | 29 | ~1,000 | none |
| OpenRouter / Metascore | 11 | 122 | none |

**Net: 130 survivors → 18**, zero forbidden eliminations board-wide. The
18 are exactly the events this session's own hand-judgment had identified
as arguable, arrived at independently — which is about as good a check on
a gate as is available without settlements.

### Two obvious rules were measured and rejected — this is the real lesson

Both would have shipped on intuition and both silently kill live
candidates. This is the failure mode the gate's docstring already named
("inside a matched family it drops silently"), caught only because the
patterns were run over the whole board before being written rather than
after.

1. **Ticker-suffix sport rule** `(GAME|MATCH|SPREAD|TOTAL|BTTS|TOP\d+|RACE)$`.
   Catches 496 series — *fewer* than the rules-text rule's 611 — and eats
   `KXRACE` ("Will Ferrari N.V. report Above 3225 total car shipments in
   Q3 2026": a company that knows its own shipments, which is the thesis
   verbatim) and `KXXAIGAME` ("Will xAI release a video game before
   2027"). It also files `KXHOUSERACE` and four Billboard/DJ-Mag ranking
   series under "live sport".
2. **Substring statistical rule** `^KX.*(CPI|PPI|INF|GDP|SALES|KWH)`.
   "Phili**PPI**nes" matches `PPI`, killing three Philippine election
   series; "LAYOFFSY**INF**O" matches `INF`; and `KXGTASALESRECORD`
   ("Will GTA 6 break the record for the highest-grossing videogame in 24
   hours" — Take-Two knows its own first-day sales) dies on `SALES`.

Both are recorded in `gate.py` as rejected-with-measurement, and
`test_the_rejected_rules_false_positives_still_survive` asserts all four
of those candidates still reach the deep stage. The safe form of the
statistical rule names the published series and the publishing agency
(text that appears in the rules), which is what shipped.

### Bookkeeping

Folded into **v4** rather than a v5: no v4 row had been recorded when this
landed (today's 232 rows are v3), so there is no track record for a
separate number to keep separable. The three affected characterization
goldens are kept unmodified as the record of the prefix-only gate; the
rules-reading behaviour got `_v3` files, and
`test_the_gate_v3_rules_reading_is_visible_in_the_goldens` locks the
difference — including that v3 may only *remove* survivors, never
resurrect one.

**What this does not fix.** The gate still cannot see a family whose rules
give no mechanical tell, and the screen still has no thesis term in it
(known weakness 3) — 18 survivors out of 328 screened means the screen is
selecting tradeable favourites, not markets an insider could know. That
remains the deeper problem.

## 2026-08-29 (cont.) — v4's first live run: the gate works, and the screen's side is now the problem

**First run at v4** (`live-2026-08-29b`, board of 111,102 markets). Stage 5
was judged **inline by the main session (claude-opus-5)** rather than by
Agent-tool subagents — this session was instructed not to spawn subagents
unless asked — and the `judgment_runs` row says so. Same model tier as the
runbook's `opus` alias; the record names what actually judged.

### Funnel

```
111,102  board markets
    764  screened / 365 events
    342  gated out  ->  23 events survived  ->  35 markets judged
      0  recommended
```

Gate removed: live sport 150, aggregate-of-many 47, vendor panel 35, weather
27, compute/collectible 23, scheduled indicator 26, commodity/FX 17, crypto
12, retail price index 5.

**v4's gate change is doing what it was built to do.** 130 survivors under
v3's prefix-only gate, 23 under v4 on a comparable board — and the vendor-panel
and sport families that motivated it are gone.

### The finding: the screen picks NO, and the divergences all push YES

15 of the 23 surviving events carry a rules divergence, and — this is the
part that only shows up across the batch — **almost every one is a rule that
is BROADER than its title, which makes YES easier.** The screen picked NO on
**30 of 35** legs. So the theory's own stage-1 side selection is systematically
opposed by the defect stage 2 is best at finding:

| event | divergence | direction |
|---|---|---|
| `KXCLAUDE-NXTMYTH` | rules exclude only Fable 5; **Mythos 5 shipped to approved orgs in late June** and is "branded Mythos" | may already be YES |
| `KXNEWDRUGAPPNTLA-LONV` | rolling BLA *initiated* Apr 27 2026 vs *completed* filing (H2 2026) | may already be YES |
| `KXNEWDRUGAPPLICATIONCMPS-360` | rolling NDA underway, sections submitted; completion guided Q4 2026 | may already be YES |
| `KXTRYFIRECOOK-27JAN01` | "has tried to fire" with **no after-Issuance anchor**; 2025 attempt + Aug 7 2026 notice letter | may already be YES |
| `KXSNAPELECTIONRS-27` | Vucic announced an Oct 18/25 snap election **on Aug 20**; rule says "officially announces" | may already be YES |
| `KXPRESSSECANNOUNCE-26AUG` | rules count an **acting/interim** naming; title says "the next Press Secretary" | broadens YES |
| `KXTRUMPMEET-26AUG` (10 legs) | rules count a **phone call** as a "meet" | broadens YES |
| `KXUAPFILES`, `KXCABLEAVE`, `KXBIGBENDRESUME` | rule broader than title in each case | broadens YES |

Five of those were confirmed by research (Mythos 5's June release, the two
rolling submissions, the Aug 7 Cook letter, Vucic's Aug 20 announcement) —
they are not speculative readings.

This is a **structural mismatch, not a run of bad luck**: stage 1 selects
tradeable favourites and lands on NO ~70% of the time (RUNBOOK known weakness
3), while the thesis's most reliable tell — a rule that resolves on something
already true — is precisely a YES-side signal. Every final review since v2 has
declined for a version of this reason; v4 is the first run where the gate is
clean enough that the pattern is unmistakable rather than buried under sport
and vendor-panel noise.

### Two other things worth keeping

1. **Every edge this run is `edge_basis='prior'`.** v4 has no bucket rates
   (they are version-scoped, correctly), so `strong`=4.0 / `moderate`=2.0 /
   `weak`=0.0 are placeholders. Nothing here could have been endorsed on
   measured evidence even if the judgment had favoured it.
2. **Two gate leaks measured, both real.** `KXKBOTOTAL` (two KBO baseball
   events) leaked because **Kalshi's own rules text calls a Korean pro fixture
   a "College Baseball game"** — the rules-reading matcher had nothing to
   catch. `KXDDR5MS` (a DDR5 spot-price monthly average), `KXCBDPOLAND` (an
   NBP rate decision) and `KXTECHRANKLISTAICODE` (a crowd-voted Elo
   leaderboard) also survived into a stage that should never have seen them.
   Four wasted deep-stage slots out of 23 — a 17% leak rate, now measured
   rather than assumed.

### Where this points

Not at retirement. The candidate list here is *better* than any previous run —
the gate fix worked. The open question is whether the screen should be allowed
to pick the YES side when a rules divergence says the market may already be
resolved, which is a stage-1 change and a v5. Recorded as a question, not a
change: nothing has measured that the YES side of a divergent market wins.

## 2026-08-29 (cont.) — the bet rule became a registered slice, and its OOS cell is day-robust

The pre-registered strong-or-moderate-NO bet rule is now a **registered
slice** (`strong-moderate-no`, `theory_slices`, registered_at backdated
to the documented 2026-08-26 pre-registration; `s200b`/`s57` designated
out-of-sample, `s200` in-sample — see the slice row's `origin` for the
full citation). Ranking now reads this theory per segment instead of on
one row: `python -m tools.cli slices report insider_judgment --version 3`.

What the mechanism computes from the ledger, v3, live+backtest pooled,
first-sighting prices (so the numbers differ slightly from the
campaign's first-qualifying-entry methodology in `backtests/RESULTS.md`):

| segment | n | clusters | days | row net | day mean | day SE |
|---|---|---|---|---|---|---|
| slice OOS | 320 | 88 | 42 | **+4.30** | **+8.10** | 1.88 |
| slice in-sample | 239 | 77 | 31 | +5.34 | +0.10 | 4.12 |
| complement | 2,732 | 809 | 69 | −2.54 | −2.36 | 1.34 |

Two things worth keeping:

1. **The OOS cell survives day clustering; the in-sample cell does
   not.** The 2026-08-27 entry above showed the judged runs as a whole
   flipping sign under day weighting. The bet-rule cell specifically
   does not: out of sample it is positive row-weighted AND day-weighted
   (+8.10 ± 1.88 over 42 days), while the in-sample rows collapse to
   +0.10 day-weighted — the discovery sample's strength was
   concentrated on heavy days, and the forward evidence is the part
   that generalizes. That is the right way around, and it is the first
   time this theory's central claim has held under the day lens.
2. **The complement is measurably negative** (−2.54 row / −2.36 day,
   SE 1.34, n_clusters=809). Everything this theory proposes outside
   the slice has been worse than its prices after fees. Candidates
   outside the slice now rank on that record instead of hiding behind
   the aggregate's −1.31.

Caveats, so nobody reads this as promotion: v4's own segments are empty
(nothing settled), and slice evidence is per-version — v4 candidates
citing the v3 slice segment must say so out loud until v4's segment is
ready. The OOS `mean_claimed_edge` is ≈0.09 because the backtest rows
recorded near-zero claims, so `realization` saturates at its 1.5 clamp
and credibility is effectively sample-weight × 1.5; show `clustered_se`
(2.43) and `day_clustered_se` (1.88) alongside any ranked edge built on
this segment. Status stays `testing`; the promotion bar from 2026-08-27
(live settlements, day-counted) is unchanged.

## 2026-08-29 (cont.) — divergence-flag slice blocked: v4 live rows record no extra_json

The pre-registered live tracking plan (2026-08-26) says the
`rules_diverge_from_title` flag is recorded on every live row, and the
proposed rules-diverge slice would condition on it
(`{"extra": {"rules_diverge_from_title": true}}`). Checked while
applying slices across the portfolio: **all 35 v4 live rows have
extra_json NULL** — the flag is not being recorded, so the slice cannot
be registered (its predicate would reference a field that does not
exist) and, worse, the tracking plan's data is not accruing. Fixing the
recording is a change to what v4 writes per row; flagged for the next
session that runs this theory rather than patched here. Register the
slice the day the field exists — with everything to that date
in-sample, since the +1.97/t_ev 2.90 cell that motivated it came from
post-hoc slicing of s200 and did not survive Holm.

## 2026-08-23 — `insider_bias` is `active` but already past its review trigger (migrated from RESEARCH_LOG.md)

**Did:** Documented, honestly, that `insider_bias`'s `active` status was set
by the one-time migration to prove the harness works end-to-end — it was
never a claim that the imported history clears the promotion bar. Measured
now: n=29, `calibration_edge_net = -0.75` points overall; restricted to rows
the predecessor actually bet (`extra_json.status` starting `BET`, i.e.
excluding declined-limit rows recorded at zero edge), `calibration_edge_net
= -1.87`. Both are negative, and n=29 is already past the `n=20` review
trigger in `CLAUDE.md`'s lifecycle rule.

**Learned:** `find-edge` defaults to `--status active`, so as things stand
today the first session that runs it will scan a theory whose own imported
track record says it currently loses after fees. That is not a reason to
silently change the status mid-branch (the migration's semantics should not
be rewritten after the fact) — it is a reason to flag it loudly here and in
`THEORY.md` so nobody mistakes `active` for "validated."

**Next:** Validating or retiring `insider_bias` is a first-order task for an
early session: either run the stage-2 backtest (tier B/C per its `THEORY.md`)
to see whether interpretation recovers the edge the raw screen does not show,
or apply the lifecycle rule and move it to `paused`/`retired` if it doesn't.

---

## 2026-08-23 — First live run: the screen has almost no thesis alignment (migrated from RESEARCH_LOG.md)

**Did:** First real use of the system. Pulled the complete Kalshi board
(96,084 markets, 13s, snapshotted), ran the `insider_bias` stage-1 screen →
765 candidates across 274 events, then the documented stage-2 cascade: two
strong subagents at high reasoning, judging **blind to price** (payload
programmatically asserted free of `yes_ask`/`no_ask`/`mid`/`spread`/
`fav_side`), 16 events each, returning a confidence bucket per event.
Recorded 44 opportunities under `run_id='live-2026-08-23'` — 25 endorsed,
19 rejected. These are the theory's **first-ever endorsed and rejected
rows**; every prior row was `screened`.

**Learned:**

1. **The stage-1 screen barely intersects its own thesis.** Classifying all
   274 candidate events against THEORY.md's own written gate rules, **242
   (88%) fall in categories the theory is written to reject**: aggregates of
   many independent people (61 events), live sport that leaked past
   `EXCLUDED_PREFIXES` (47), weather (32), crypto strike ladders (31),
   commodity/FX/rates (28), compute/collectible prices (20), scheduled
   indicators (16), retail price indices (7). Only 32 events could carry the
   thesis at all. The screen is a generic tradeable-favorite filter — price
   band, spread, volume, near close — with no thesis term in it. This is a
   live explanation for the flat imported record: if 88% of what reaches
   judgment cannot carry the thesis, near-zero measured edge is the expected
   result. Concrete leaks: `EXCLUDED_PREFIXES` misses `KXWNBA`, `KXUCL`,
   `KXNWSL`, `KXTESTMATCH`, `KXLMBGAME` and ~18 more live-sport families, and
   nothing excludes price-strike ladders (330 candidates on their own).

2. **Resolution rules diverge from titles at an extraordinary rate.** 19 of
   32 events (59%) carried a rules/title divergence, several decisive:
   `KXCLAUDE-NXTMYTH` excludes only Fable 5 while Mythos 5 shipped the same
   day (June 9) and is not excluded; `KXVIDEOLENGTH-GTA` never says whether
   the strike ladder measures one episode, the total, or the YouTube cut;
   `KXTRYFIRECOOK` has no "after Issuance" clause though Trump already
   attempted removal in 2025; `KXHEARNCHARGE` requires a *new* charge after
   an undefined "Issuance". THEORY.md already lists rules divergence as a
   warning sign, but at 59% it is not an occasional trap — it is the modal
   property of this candidate class, and reading rules may be a larger part
   of the edge than identifying insiders.

3. **The AGT heuristic in THEORY.md is wrong as written.** The theory says
   pre-taped competition TV is the strongest sub-case and deserves extra
   weight. The subagent correctly refused it for `KXAGTELIMINATION`: AGT's
   live quarterfinals are *not* pre-taped, and elimination is decided by
   public vote — the aggregate-of-many-people case the thesis excludes. The
   heuristic needs the qualifier "pre-taped **and** taping already
   completed"; applied to a live-vote show it inverts.

4. **Two session-level overrides**, both applying the theory's own
   warning-sign rule. `KXIPOSHEIN-DATE` strong→weak: independently verified
   that CSRC approval (Jul 10), the HKEX prospectus (Jul 26) and the ~Sep 1
   target are all in mainstream press, so there is no informational
   asymmetry — the thesis needs a group who knows what the public does not.
   `KXVIDEOLENGTH-GTA` strong→moderate on the unresolved measurement
   ambiguity.

5. **Credibility is 0.0, so every candidate ranks at 0.0.** `realization` is
   0.0 on the imported history, so `ranked_edge = 0` for every bucket. Per
   `find-edge` §6 this was reported as claimed edge plus the shrinkage
   reason, not as a table of zeros.

**Next:** The 44 rows resolve between Aug 24 and Sep 5, so
`interpretation_value` — diagnosis item 2, never computable before — becomes
available in under two weeks. Two candidate version-2 changes are now
evidence-backed enough to specify: exclude price-strike ladders and the
leaked sport families from stage 1, and add a mechanical rules-vs-title
divergence check. Both are stage-1 code, which would move part of this
theory toward tier A. Do not bump the version until the current 44 settle —
changing the procedure mid-flight is exactly what the versioning rule exists
to prevent.

**Addendum, same session — v2 bump and track-record reset.** On the user's
instruction the v1 data was **deleted** (96 imported opportunities, 28
settlements; backed up outside the repo, regenerable via
`migrate_kalshi_trader.py`) and the theory bumped to **version 2**, because
the decision procedure changed: subagent output is now an *initial*
recommendation only, and no candidate may be suggested as a bet unless the
main research session reviews and recommends it itself, with the deciding
model recorded on every row (`extra_json.final_recommendation.decided_by`).
`disposition='endorsed'` now means "the main model recommends this bet",
not "arithmetic produced a positive number". New `Stage 3` section in
`THEORY.md`.

The run was re-recorded under v2. **The mechanical v1 rule would have
endorsed 25 of 44 markets; the main model recommends 3.** That gap is the
justification for the change: the 22 it declined were dominated by a defect
visible only in the batch view — the resolution-rules divergence broadens
what counts as YES, and 543 of 765 screen candidates are NO-side favourites,
so the divergence systematically damages the exact leg the screen picked. A
per-candidate subagent cannot see that pattern; comparing candidates
side by side is what the final stage is for.

The reset means the theory is now **n=0 — unproven, not disproven**. Note the
one thing lost: the v1 rows were the only dataset that could have answered
whether LLM-introspected `q` values realize their claimed edge (see the
2026-08-23 Learnings note on `model_prob_source`). That question is now
parked behind re-running the migration, not gone.

---

## 2026-08-24 — First tier A backtest of the stage-1 screen, after a false start that took 47 minutes to fail (migrated from RESEARCH_LOG.md)

**Did:** Orient found nothing new to settle (all 44 v2 rows from yesterday
still open) and no theory besides `insider_bias` on the board, so I picked
THEORY.md's own top-priority item: a tier A backtest of the stage-1 screen
alone, which the theory had never had. Built the candle→market adapter
(`theories/insider_bias/backtest.py`, `replay_market`), then ran it.

**Learned, the expensive way first:** A naive `list_settled(min_close_ts=...,
max_close_ts=...)` walk is not usable for a recent window. One series,
`KXMVECROSSCATEGORY` (a combinatorial "shard" product), settles **400,000+
markets per day** on its own — confirmed by an exhaustive count that hadn't
finished at 400 pages for a single day. A 30-day walk ran for 47 minutes
without completing before I killed it, on the user's instruction to
investigate a better approach rather than just wait longer or shrink the
window. Two compounding mistakes made this worse than it needed to be even
before the volume problem: the fetch phase had no incremental checkpoint, so
47 minutes of API calls were unrecoverable the moment the process was
killed; and I didn't check the true scale before committing to a window size
— a few density-sampling probe calls would have caught the problem before
launching an hour-long run instead of after.

**The fix:** Kalshi's `/series` listing (one call, ~13k series) exposes a
`category` field, and `/markets?status=settled` honours an (undocumented)
`series_ticker` filter. `candidate_series()` narrows 13,437 series to ~2,200
by dropping `screen.is_excluded` ticker prefixes, `NO_CATEGORIES`
(Sports/Crypto/Weather/Commodities/Economics/Elections/Financials — the same
families `screen.is_excluded`/`gate.py` already reject downstream), and
series untouched in 60+ days — all *before* issuing a single settled-market
request. `iter_settled_survivors` then walks one series at a time, which
Kalshi's API returns dramatically smaller pages for. Result: a 90-day window
that the old approach hadn't finished in 47 minutes ran in **~9 minutes** for
the fetch phase, ~2.5 more for a 600-candidate candlestick replay. Both
`tools/kalshi/markets.py::list_settled` (new `series_ticker`/`raw_filter`/
`on_page` params) and the driver script now checkpoint incrementally —
survivors every 100 series, replay results every 25 candidates — so this
class of mistake cannot repeat.

**Result:** `run_id=backtest-2026-08-24-stage1-90d`, tier A, no LLM in the
decision path. 18,430 candidates survived the cheap pre-filter; a systematic
sample of 600 replayed against real point-in-time candles; 200 actually
cleared the screen at some point in their last 14 days. Overall:
`win_rate=85.0%`, `calibration_edge_net=+1.38pts`. That number is a
composite of a strongly negative slice (n=47, the "aggregate of many
independent people" family `gate.py` already excludes: `-11.12pts` — direct
mechanical confirmation that exclusion is correct) and two positive slices
(n=116 "MENTION"-suffix series `gate.py`'s regex currently misses:
`+5.48pts`; n=37 everything else, the cleanest thesis-eligible slice,
including `KXBIGBROTHERELIMINATION` — the same series as a live v2 endorsed
opportunity: `+4.40pts`). Full breakdown in `THEORY.md` Learnings,
2026-08-24. Moved the theory `under_review` → `testing`: the specific v1
diagnosis that kept it under review (is the screen itself broken) is now
answered — no — but the theory's actual claim (does judgment add value) is
still n=0 on the live side, so `active` isn't justified yet.

**Next:** The 44 live v2 rows still settle Aug 24–Sep 5 — once they do,
`interpretation_value` becomes computable and should be read alongside this
backtest, not in isolation. The MENTION-family question (Status item 3) is a
real open thread: is it thesis-relevant or a distinct, still-profitable
phenomenon? Deciding that is a judgment call, not more plumbing, and
probably wants a small subagent batch reading a sample of those markets'
actual resolution rules. The `KXMVECROSSCATEGORY`-style volume trap is not
insider_bias-specific — any future theory doing historical Kalshi analysis
will hit the same wall; `list_settled`'s docstring and `backtest.py`'s module
docstring both carry the account now, so it should not need rediscovering.

---

## 2026-08-25 — insider_judgment tier-A full coverage: the gate separates, but what it keeps is only breakeven; judged sample launched (migrated from RESEARCH_LOG.md)

**Did:** The non-mention full-coverage walk finished: 5,583 series,
7,948 survivors, 3,195 screen hits (3,181 with usable settlements, 831
events, 325 series), all recorded under
`run_id=backtest-2026-08-25-insider-fullcov` (tier A, run row recorded)
with deterministic gate tags on every row and every raw payload/candle
banked in the history cache as fetched. Then scored it, updated idea 14
with the replication result, and launched the tier-B judged sample
(batches 1-2 of 8 dispatched to Sonnet subagents; save-before-spend
artifacts committed first in cfed04a).

**Learned:** (1) *The gate discriminates, at scale and in the right
direction*: gate-plausible +0.71pts net (n=1,561) vs gated-out -2.18
(n=1,620) — a ~2.9pt gap. But (2) *what the gate keeps is roughly
fair-priced, not profitable*: the +0.71 is nominally p=0.04 by rows but
event-clustered t is -0.25 (1,561 rows on only 456 events), and the
84-row sample's +4.40 headline does not survive — same lesson as
mention's +5.48: small samples of this screen are confidently wrong.
So screen+gate alone earns nothing; the theory's remaining case rests
entirely on judgment adding selection within the plausible pool, which
is precisely what the judged sample measures. (3) The no-side-premium
asymmetry partially echoes on this disjoint population (YES 0.80-0.90
significantly overpriced; NO beats YES below \$0.90) but the mention
run's NO>=0.90 cell does not strongly replicate (+1.04, p=0.09) and the
band structure moves — durable claim downgraded to side-level, recorded
on idea 14. (4) Curiosity, not a claim: the gated "future price:
compute/collectible" family scored +4.56 (n=152, p=0.038, but t_ev
+0.12) — GPU/collectible price ladders; post-hoc, cluster-weak, noted
only so a future session knows it was seen.

**Next:** Ingest and commit each judged batch as it lands; score bucket
calibration + interpretation value vs the screen+gate baseline; then the
final write-up. Backfill of pre-cache raw data is running in parallel.

## 2026-08-26 — Tier-B judged sample complete: judgment orders outcomes; strong-NO and the rules-divergence flag are the standouts (migrated from RESEARCH_LOG.md)

**Did:** All 8 batches of the judged-s200 replay ran to completion under
the save-as-you-spend protocol — every batch's payload committed before
dispatch, every verdicts file written by the judging subagent itself,
ingested to the ledger and committed before the next dispatch (commits
df97b9b..1a4c490). 200 events / 704 market rows judged by
claude-sonnet-5 (web search off, blind payloads, per-batch as-of dates,
committed mechanism sheet in lieu of search). Run row recorded tier B.
Scored against the same-sample screen+gate baseline.

**Learned:** Bucket totals 24 strong / 66 moderate / 110 weak. The
buckets order outcomes exactly as the thesis predicts: strong +5.09pts
net (n=111 rows, p_fair=0.044), moderate +0.85, weak -0.79, over a
baseline of +0.67 — the first time any judgment layer in this repo has
produced its predicted ordering on settled data. Event-level means are
monotone too (+2.88 / -0.56 / -2.26). The concentrated cells: strong-NO
+8.59 net (n=83, p=0.006) against strong-YES -5.30 — the optimism-tax
asymmetry's third independent appearance today — and events flagged
rules_diverge_from_title scored +1.97 with t_ev=+2.90 (26 events), the
strongest event-clustered statistic of the session: reading rules
against titles measurably pays. Limits stated plainly: 24 strong events,
bucket-ordering clustered support weak (t_ev +0.66), sharp cells are
post-hoc slices. The judges also produced qualitative value the code
path cannot: e.g. catching that the Emmy winner markets close on
NOMINATION day (before final voting concludes), gutting the
"tabulators already know" logic for that family.

**Next:** Pre-registered live plan for insider_judgment (status stays
testing): track strong — and strong-NO as its own view — plus the
divergence flag on every live row; promotion requires the ordering to
repeat on live settlements. The judged-run bucket rates are usable as
bootstraps with the in-sample caveat attached. Backfill continues in
background (~9.6k candle windows cached so far); when done, the entire
reachable window's raw data is durable and every variant re-test is
offline.

## 2026-08-26 — Strong-YES autopsy: the bleed was sealed-tabulation award markets; excluding them repairs YES to breakeven, NO-rule strengthens (migrated from RESEARCH_LOG.md)

User challenged the methodology on strong-YES's -7c. Autopsy: the losses
cluster in Emmy-nomination/BET/award strikes — events where the judge is
arguably RIGHT that a small body already knows (tabulators), but the
knowledge is SEALED and never leaks into price before close, so buying
the public's favorite at the ask pays the crowd's guess plus spread. The
thesis needs leakable knowledge, not just knowledge — prompt-refinement
candidate for a future version ("does the group's knowledge plausibly
escape before close?"), which would be a version bump. Excluding the
award family (KXEMMY*/KXESPYS/KXBET/KXFIELDS pattern; 135 rows / 40
events, own net +1.6) symmetrically from all cells: strong-YES -7.0 →
+0.6 (n=24, breakeven, not negative); strong-NO +6.8 → +11.0 (luck
0.2%, but only 16 events); moderate-YES worsens to -6.9 (the YES
problem is not award-specific); bet rule (str+mod NO) +5.1 → +5.9,
luck-odds ~0 either way. Post-hoc caveat recorded: exclusion chosen
after seeing the losers; legitimate path is pre-registering a
sealed-small-body-decision NO-rule for the gate (version bump) and
letting live rows decide. Contamination note: strong-YES losing at all
is itself evidence the blinding held — a leaky judge wins its confident
bucket, never loses it.

## 2026-08-26 — Uniform "enter 3-2 days before close" repriced from the candle cache: waiting KILLS the moderate edge, only strong-NO survives late entry (migrated from RESEARCH_LOG.md)

User-directed focus: what if we only bet 3-2 days before close?
`reprice_entry_window.py` replays a UNIFORM late-entry strategy from the
durable candle cache (fixed snapshot nearest close-2.5d, unmodified
screen conditions, favorite at that snapshot's ask) over all 1,081
judged rows — distinguishing "chose to enter late" from the earlier,
confounded "first qualified late" filter. Result: only 444 rows are
even biddable at 3-2d (414 fail the price band there, 100 lack a candle
in the window, 69 spread, 37 volume, 17 awaiting cache backfill).
The bet rule (str+mod NO) at uniform late entry: +1.81pts, p=0.18 —
versus +5.13 at first-qualifying entry. The culprit is convergence:
moderate-NO's mean ask at 3-2d is 0.895 vs 0.861 at first
qualification, and its edge collapses to +0.29. **The moderate edge is
substantially an early-entry edge — catch the favorite when it first
crosses the screen, not after the market has drifted toward
certainty.** The exception: strong-NO holds +8.29 late (n=32/19ev,
p=0.10), consistent with the first-qualifying-entry late slice (+12.2).
The earlier "late entries did well" table was selection, not a timing
rule — the confound the mention_family docstring flagged as untested is
now tested, and delaying hurts everywhere except strong-NO. (Ignore the
repriced weak-YES +5.9 — no mechanism, third noise-shaped YES cell.)
Practical rule that survives: enter moderate-NO at first qualification;
strong-NO may be entered any time including late.

## 2026-08-26 — FULL POPULATION JUDGED: the pre-registered NO-side rule REPLICATED out of sample (migrated from RESEARCH_LOG.md)

**Did:** Completed judgment coverage of the entire gate-plausible
population from the tier-A walk: s200 (200 events) + s200b (200) + s57
(57) = 457 events / 1,561 market rows, every batch payload committed
before dispatch, every verdicts file ingested and committed as it
landed (through bbadf13), one batch recovered intact from a usage-cutoff
orphan. Also repriced the uniform 3-2-days-before-close entry over the
full set from the candle cache, and the backfill finished its walk
(~17k candle windows / ~18k payloads durable).

**Learned — the headline:** The bet rule pre-registered from s200
(strong-or-moderate judgment, NO side, first-qualifying entry)
**replicated on the 257 events judged after pre-registration: +4.92pts
net, p_fair=0.0008 (312 rows / 85 events), vs +5.34, p=0.0018 on the
original round.** Pooled: +5.10pts, p<0.0001, n=551 rows / 162 events,
win rate 0.922 at mean ask 0.863; excluding the award family: +5.45.
Sub-cells: moderate-NO replicated STRONGER (+3.61 -> +5.13, p=0.003);
strong-NO replicated in direction but weaker (+8.59 -> +4.29, p=0.096
-- partial regression toward the mean, as expected for the flashiest
cell). The rules-divergence flag repeated its direction (+1.97 ->
+2.17) without reaching significance. Full-population bucket x side:
NO ladder monotone and significant (strong +6.50 p=0.0017 / moderate
+4.52 p=0.0006 / weak -1.96), YES side flat-to-negative everywhere
(strong -4.98, moderate -3.19, weak +0.36) -- the optimism-tax
asymmetry held through every expansion. Timing at full coverage:
uniform 3-2d late entry still underperforms first-qualifying entry
(+2.32 p=0.06 vs +5.10), confirming the moderate edge is an
early-entry edge; strong-NO alone tolerates late entry.

**Next:** This is the strongest evidence any theory in this repo has
produced: tier B, pre-registered, out-of-sample replicated, mechanism-
backed (optimism tax + insider-NO), n=162 events. Still backtest, still
one summer, still sibling-correlated within events — the promotion bar
remains live settlements. Proposed live procedure for the user to
ratify (a v4 version bump): judge as today; bet only strong/moderate
NO favorites at first qualification; record dtc and the divergence
flag on every row; sealed-tabulation award families as a new gate
NO-rule candidate. Bucket rates for pricing: use the pooled judged-run
rates with the in-sample caveat until live rows accumulate.

## 2026-08-26 — Gate validation: 100 gated-out events judged, 99 weak / 1 moderate / 0 strong; the session's autonomous arc is complete (migrated from RESEARCH_LOG.md)

**Did:** Closed the last open question the backtest data could answer:
does the code gate throw away markets the judge would bet? 100 randomly
sampled gated-out events (exp/2026-08-26-insider-judged-gated100 — exp/
so it can never pool into the theory's track record), same protocol as
every s-series run. Verdict: **99 weak, 1 moderate, 0 strong.** The
regex gate and the LLM judge — built independently, one reading ticker
families, one reasoning about who-already-knows — agree essentially
perfectly on what carries no insider thesis. The gate's cheap "no" is
validated at the judgment layer; the tier-A +4.56 curiosity in the
GPU-ladder family was price-band luck, not a missed insider signal. The
single moderate (KXEOWEEK, an already-elapsed EO-count window with
publication-lag risk) is a defensible edge case, not a systematic
false negative.

**Session summary (2026-08-25/26, autonomous):** mention_family audited,
full-coverage-retested (n=3,441), found edgeless, retirement proposed;
Kalshi's ~60-day archival discovered and the durable history cache built
(~17k candle windows banked ahead of the clock); insider_judgment's
screen+gate measured at population scale (breakeven kept-slice, gate
separation real); the ENTIRE gate-plausible population judged across
three tier-B runs (457 events / 1,561 rows) with the pre-registered
NO-side rule REPLICATING out of sample (+4.92, p=0.0008; pooled +5.10,
p<0.0001); the timing question answered mechanically (moderate edge is
early-entry; strong-NO tolerates late); the strong-YES bleed traced to
sealed-tabulation award families; and the gate validated. Every batch,
verdict, run row, and finding committed as it happened; one batch
recovered intact from a usage cutoff. Awaiting the user: mention_family
retirement ruling, and ratification of the proposed v4 live procedure.

## 2026-08-29 (cont.) — gate.py reads resolution rules; 130 survivors → 18 (migrated from RESEARCH_LOG.md)

**Did:** Closed the last of the three 2026-08-28 defects. `gate.py`
classified by series-ticker prefix only, so it knew exactly the families
someone had already typed into it. Measured over the whole
117,272-market board: it removed 198 of 328 screened events and **109 of
the surviving 130 were still families the thesis rejects** — whole
categories, not stragglers. Added `RULES_NO_RULES`, which matches the
market's **resolution rules** instead of its name: four patterns (sport
fixture, Carbon Arc vendor panel, statistical release,
OpenRouter/Metascore), each validated against every series on the board,
zero false positives. **Net: 130 survivors → 18.** Folded into v4 (no v4
row had been recorded yet). Suite 883 green.

**Learned:**

1. **Matching mechanics beats matching names, and the difference is
   maintenance.** A Carbon Arc panel says "Carbon Arc" in its own rules
   whatever its ticker is called, so one pattern covers 77 series today
   and every one Kalshi adds tomorrow. The prefix list needed an edit per
   family and was losing the race.
2. **The two rules I would have shipped on intuition both silently killed
   live candidates.** A ticker-suffix sport rule
   `(GAME|MATCH|SPREAD|TOTAL|BTTS|TOP\d+|RACE)$` catches *fewer* series
   than the rules-text one (496 vs 611) and eats `KXRACE` (Ferrari's own
   shipment count) and `KXXAIGAME` (xAI's own roadmap) — both the thesis
   verbatim. A substring statistical rule
   `^KX.*(CPI|PPI|INF|GDP|SALES|KWH)` eats three Philippine election
   series on "Phili**PPI**nes" and `KXGTASALESRECORD` on `SALES`. Only
   running every candidate pattern over the whole board *before* writing
   it caught this. **That is now the procedure for any gate rule**, and
   both rejected rules are recorded in `gate.py` with their measurements
   so nobody re-adds them.
3. **An independent check fell out for free.** The 18 survivors the new
   gate produces are the same set this session's own hand-judgment had
   flagged as arguable among 131 events, arrived at by a completely
   different route. That is about as much validation as a gate can get
   before settlements arrive.
4. **The deeper problem is upstream and unchanged.** 18 survivors out of
   328 screened events means the screen still has no thesis term in it —
   it selects tradeable favourites, not markets an informed minority
   could know (known weakness 3 in the RUNBOOK). The gate has been doing
   the screen's job.

**Next:** the screen itself is now the top `insider_judgment` item — a
stage-1 filter with a thesis term would beat a stage-1.5 gate that throws
away 95% of what stage 1 returns. Otherwise: 22 specced theories remain
unbuilt, and idea 21's soft relative-value successor still has a ready
dataset.

## 2026-08-24 — pointer: the corrected Big Brother bet (migrated entry lives in mention_family's notebook)

Item (1) of `## 2026-08-24 — Two follow-ups from user questions: a
corrected Big Brother bet, and a new mechanical path for the
MENTION-family edge (migrated from RESEARCH_LOG.md)` in
`theories/insider_bias/mention_family/NOTES.md` is insider_judgment's:
the Big Brother correction and the stage-3 checklist item.

## 2026-08-26 — Formal multiplicity pass (user-prompted): Holm + event clustering (migrated from RESEARCH_LOG.md)

Holm-Bonferroni over the pre-registered family (m=4, replication data
only): bet rule p=0.0008 vs 0.0125 SURVIVES; moderate-NO p=0.0030 vs
0.0167 SURVIVES; strong-NO p=0.0961 fails; divergence flag fails. The
sterner event-clustered one-sided t (one observation per event, killing
sibling-strike inflation): bet rule +5.21/event, t=2.26, p~0.012 on the
85 replication events; +3.87, t=2.29, p~0.011 pooled over 162. So the
defensible statistical claim after full correction: THE BET RULE AND
MODERATE-NO ARE SIGNIFICANT; strong-NO alone and the divergence flag
are directionally supported but unproven, and the exploratory scans
(e.g. mention NO>=0.90 at p=0.0084 across ~50 cells vs Holm ~0.001)
never survived formal correction — which is why they were sent to
forward tests rather than believed. Report language downgraded
accordingly: the edge is established at ~p=0.01 clustered, not p<0.0001.

## 2026-08-26 — Contamination audit of the judged runs (user-prompted): no hints found; one timing wrinkle bounded (migrated from RESEARCH_LOG.md)

Four channels audited mechanically. (1) Web tools: grep of all 23 judge
subagent transcripts for WebSearch/WebFetch invocations — zero. (2)
Payload fields: all 557 events / 2,044 markets across the four runs
carry only the whitelisted fields; zero price/outcome/status keys; the
11 'settle' substring hits are ordinary Kalshi rules boilerplate
("dismissed, settled, or otherwise disposed of..."), verified in
context. (3) The one real wrinkle: batch-level as_of pinning (max of
the batch's entry days) left 618/2,044 markets whose close_time
precedes the pinned "today" — a judge could infer those events had
concluded, though never how. Contamination-shape check: those rows
scored WORSE overall (-0.74 vs +1.16 net) and the strong bucket scored
worse on them (+0.73 vs +3.52) — the opposite of leakage, which
inflates confident buckets. The bet rule on the CLEAN subset only
(still-open at as_of): +4.65 net, win 0.910, n=409 — the headline
survives with every affected row discarded. (4) Behavioral: strong-YES
lost money, verdicts track mechanism not outcomes, and three judge
instances independently rediscovered the Emmy nomination-day trap.
Fix for future runs: pin as_of per event (or min-of-batch), not
max-of-batch — noted for the v4 procedure.
