# Entry timing — pre-registration, written BEFORE looking

**Date:** 2026-08-30 ·
**Tier:** A (no model anywhere) ·
**Verdict:** **FAILED PREDICTION**, and the useful half is the secondary null

**Committed before any edge, win rate or difference was computed.** At the
time of writing I had run exactly one query against the corpus, and it
computed **counts only** — row counts, series counts, distinct close-day
counts, and the distribution of rows across offset buckets. No outcome of
any kind. That script is kept as
`counts.py` so the claim is checkable rather than asserted.

## The question

Every theory in this repo has to choose *when* to enter, and only one
measurement of that choice exists: `insider_judgment` found that a uniform
3–2 day late entry underperformed first-qualifying entry on its own
population (**+2.32 vs +5.10** net). That is one screen, one population,
one thesis. If entry timing has a general direction, every theory's entry
rule is affected; if it does not, theories can enter whenever liquidity is
best and stop worrying about it.

This study asks the same question on a completely different and much
broader population, at **zero marginal fetch cost**, because both prices
are already on disk.

## Why this is a study and not a theory

It produces a measurement about *execution*, not a bet. Nothing here
registers a theory, records an opportunity, or touches the ledger.
CLAUDE.md: `Theory` is for things that produce bets; an execution policy
decorates candidates.

## Population — frozen, and deliberately so

`tickets/study/investigation/2026-08-29-series-bias-mining/data/collect.db` as it stood at
**2026-08-30T19:27Z**, copied to a scratchpad snapshot before this bar was
written. The live file is being appended to by a resumed phase-2
collection right now, so freezing is what makes this reproducible: a
population that grows while it is being analysed is not a population.

- **8,268 paired rows** (both entry prices present) across **219 series**,
  **61 distinct close days**. 128 series carry ≥ 40 paired rows.
- Each row is one settled Kalshi market carrying two independently priced
  entry points from the same candle history:
  - **`main`** — the ask at **25% of scheduled lifetime** before scheduled
    close (the earlier entry).
  - **`alt`** — the ask at **24h** before scheduled close (the later
    entry), `NULL` where the market lived under 24h, which is why 2,637 of
    10,905 rows are unpaired and excluded.
- Both anchor to **scheduled** close (`expected_expiration_time`), never
  observed close. On a "does X happen by D" market the observed close *is*
  the outcome variable, so anchoring to it would make the information
  state a function of the answer. 7,059 of these rows settled early, so
  this is not a technicality — it would contaminate most of the corpus.

**Scope honesty, fixed now.** Phase 2 priced series in ascending order of
market count, so this frozen slice is the **small-series tail** and is
heavily **sports/soccer** (KXUSLBTTS, KXEREDIVISIE*, KXLIGAPORTUGAL*,
KXUCL1HBTTS …). It is **not** the board, and a result here generalizes to
recurring small series, not to Kalshi at large. Politics, weather and the
large series are in the 612 series still being collected and are **out of
this study's population by construction**, not by choice after the fact.

## The statistic

Per entry point, the **day-clustered** gross calibration edge in points:
one observation per **close day** = `mean(won − ask)` over that day's rows;
the estimate is the mean over days, SE the between-day standard error.

Day-clustered, not row-counted, for the reason this repo has now been
bitten by five separate times: recurring series settle in tight clumps, so
rows are not independent draws. **Gross, not net** — fees are a roughly
constant −1 to −3 pt offset that applies to *both* entry points and
therefore cancels exactly in the paired difference, which is the primary
statistic. Net is reported beside it for the separate question of whether
either entry is bettable at all.

**The primary statistic is the PAIRED difference**, day-clustered:

```
Δ = edge(alt, 24h) − edge(main, 25% of lifetime)
```

Paired, because both entries are the same market with the same outcome, so
the market-level and day-level noise that dominates either edge separately
largely cancels. Reporting two separately-noisy edges and eyeballing the
gap is the weaker test and is not the one that decides this.

## The sign, fixed in advance

**Prediction: Δ < 0** — the later (24h) entry earns *less* than the
earlier entry, the same direction `insider_judgment` measured.

Fixing the sign now is the point. Without it, a positive Δ could be
reported as "timing matters, just the other way", which would make the
hypothesis unfalsifiable. A positive Δ is a **failed** prediction and will
be reported as one, whatever its magnitude.

## Inclusion rules and the power floor — part of the bar

Stated as claims, not left implicit, because on 2026-08-29 two separate
studies in this repo had their conclusions silently spanned by an
inclusion rule nobody had written down (`calibration_harvest`'s horizon
collapse, `series-bias-mining`'s count-as-power floor).

1. **Paired rows only.** A row without `ask_24h` cannot contribute to a
   paired difference. Excluded rows are counted and reported.
2. **A power floor on the primary test, not a count floor.** The pooled
   paired difference must have a minimum detectable effect
   `MDE = 2.8 × SE` of **≤ 2.0 points**. Below 2 points a timing effect
   cannot change any entry rule in this repo, so a test that cannot
   resolve 2 points has not measured anything. The MDE is reported
   whatever it comes out as.
3. **No outcome-based exclusion anywhere.** Nothing is dropped for how it
   resolved.
4. **Side disagreement is measured, not swept.** The favorite side can
   differ between the two entry points (`side` vs `side_24h`); where it
   does, the two rows are genuinely different bets. The **primary test is
   the full paired set**, since that is what an entry rule would actually
   experience. The side-agreeing subset is reported as a **secondary**
   check, declared here so it cannot later be presented as the headline if
   it happens to look better.

## Multiple comparisons

**One primary test:** the pooled paired Δ. That is the whole
confirmatory family, so no correction applies to it.

Everything else — per-series Δ, per-offset-bucket Δ, the side-agreeing
subset — is **exploratory**, reported with Holm–Bonferroni across the
tested set and labelled exploratory in the write-up. An exploratory hit is
a hypothesis for a pre-registered forward test, never a finding.

## What counts as what, fixed now

- **Confirmatory:** MDE ≤ 2.0 pts **and** day-clustered |t| ≥ 2 on the
  pooled paired Δ, **in the predicted negative direction**. Then entry
  timing has a measured general direction in recurring small series, and
  every theory's entry rule should be revisited against it.
- **Genuine negative:** MDE ≤ 2.0 pts and |t| < 2. Then timing does *not*
  matter in this population at any size worth acting on — a useful result,
  because it frees entry to follow liquidity rather than a rule.
- **Failed prediction:** |t| ≥ 2 with Δ **positive**. Reported as a failed
  prediction, not re-read as a discovery.
- **Not measured:** MDE > 2.0 pts. Recorded now so a thin result cannot be
  talked up later.

## Known limits, fixed now

- **Sports-dominated small-series tail** (see Population). The single
  biggest limit, and the reason a null here does not license "timing never
  matters".
- **Two entry points, not a curve.** 25%-of-lifetime and 24h are what
  exist on disk; they are not a sweep, and the answer is about those two
  points.
- **In-sample throughout.** No split-half is available and none is
  claimed — this is a single measurement, and its follow-through if
  confirmatory is a pre-registered test on the 612 series still being
  collected, which are a genuinely fresh population.
- **`main` collapses toward `alt` for short-lived markets.** At a 4-day
  lifetime, 25% is 24h, so the two entry points coincide and Δ is
  mechanically 0. The offset distribution is reported so the reader can
  see how much of the corpus is in that regime, and it is a dilution
  toward the null, never a source of false positives.

---

# Result — FAILED PREDICTION, after a design defect I had to fix first

Run 2026-08-30, after the bar above was committed (`fc52527`).

## First, the defect — and it inverted the headline

The pre-registered primary statistic was `alt − main`, described in the bar
as "later minus earlier". **That description is wrong for most of the
corpus, and I did not notice until the offset breakdown made it
impossible to miss.**

`main` sits at 25% of scheduled lifetime before close; `alt` sits at a
fixed 24h before close. Which one is *later* therefore depends on the
market's lifetime:

| lifetime | 25% of lifetime | which entry is later |
|---|---|---|
| > 4 days | > 24h before close | `alt` (24h) is later — as the bar assumed |
| **< 4 days** | **< 24h before close** | **`main` is later — inverted** |

Measured: **5,156 of 8,268 paired rows (62.4%) are inverted.** The
pre-registered pooled difference averaged two opposite contrasts, so its
sign meant nothing. It reported **−2.41 pts, t = −3.85**, which by the
letter of the bar was "CONFIRMATORY: later entry earns less, as
predicted" — a clean confirmation of a prediction, produced by a bug.

Caught because the exploratory offset breakdown had `<6h` and `6-24h`
strongly negative while `1-3d` was flat: buckets whose *own definition*
put `main` on the other side of `alt`. `orient.py` re-orients every row so
the difference always reads later-minus-earlier.

This is the fourth time in two days that an unstated inclusion or framing
rule silently spanned a conclusion in this repo. The pattern is now
specific enough to name: **when two measurement points are defined by
different rules — one relative, one absolute — check that their ordering
is constant across the population before differencing them.**

## Re-oriented result

Every figure below reads **later entry minus earlier entry**, day-clustered
over 61 close days.

| population | n | later − earlier | SE | t | MDE |
|---|---|---|---|---|---|
| **POOLED (primary)** | 8,268 | **+2.97** | 0.62 | **+4.79** | 1.74 |
| long-lived (> 4d) | 3,111 | +0.10 | 1.36 | +0.08 | 3.80 |
| short-lived (< 4d) | 5,156 | +4.54 | 0.81 | +5.63 | 2.26 |
| side agrees (secondary) | 7,580 | **+0.56** | 0.30 | +1.86 | 0.85 |
| side flips | 688 | **+31.43** | 6.90 | +4.56 | 19.32 |

**Verdict by the committed bar: FAILED PREDICTION.** The bar fixed the sign
negative — later entry earns *less*. The powered pooled result is
significant and **positive**. Fixing the sign in advance is exactly what
stops this being written up as "timing matters, just the other way", and
it is being reported as a failed prediction instead.

## What the decomposition actually says, which is more useful than the headline

The pooled +2.97 is **not a timing edge**, and reporting it as one would be
the second error of this study:

1. **On the 92% of rows where you buy the same side at both points, the
   difference is +0.56 pts (t = 1.86, MDE 0.85) — not significant, and
   below the 2.0-point floor the bar declared actionable.** Waiting does
   not get you a better price on the bet you were already going to make.
2. **The entire pooled effect is the 8% of rows where the favorite side
   flipped between the two points (+31.43).** There, the later entry buys
   whatever the market now favors, and the later favorite wins far more
   often. That is price informativeness — the market learned something
   between the two timestamps — not an edge anyone can harvest, because
   you cannot know in advance which markets will flip.

**So the genuine finding is the secondary one: entry timing on a fixed
side is worth about half a point in this population, which is nothing.**
For these theories, entry should follow liquidity and spread, not a timing
rule. That is a real result and it is the useful half.

## Does this contradict insider_judgment?

**No, and it must not be read as doing so.** That theory measured
first-qualifying (+5.10) against a 3–2 day late entry (+2.32) — a 2.78-point
penalty for waiting — on strong/moderate NO favorites at mean ask 0.863
selected by an LLM judge. The comparable measurement here is the
side-agreeing subset (+0.56 ± 0.30) on sports-dominated small recurring
series. Different populations, different selection, different price band.
Two populations disagreeing about a half-point effect is not a conflict to
resolve; it is a reason not to generalize either.

## An unregistered observation, flagged as a hypothesis and nothing more

Both entry points show favorites badly overpriced in this population:
**−5.19 pts** gross at the 25%-of-lifetime entry and **−7.60 pts** at 24h.
That was not pre-registered here and is not a finding of this study. It is
worth recording only because it points the same way as an independent
measurement made the same day — `calibration_harvest`'s forward corpus had
favorites at mean ask 0.839 realizing 0.800, −3.88 gross. Two unrelated
populations, favorites overpriced by 4–8 points. **A pre-registered,
powered test of "Kalshi favorites are overpriced" belongs in its own study
with its own bar** — `no_side_premium` already holds the side-level version
of this claim — and neither of today's numbers may be cited as evidence
for it, because neither was collected to answer it.

## Reproduce

```bash
python tickets/study/answer/2026-08-30-entry-timing/counts.py  <collect.db>   # counts only
python tickets/study/answer/2026-08-30-entry-timing/measure.py <collect.db>   # as pre-registered (defective framing)
python tickets/study/answer/2026-08-30-entry-timing/orient.py  <collect.db>   # the correction
```

`measure.py` is kept, defect and all, because the write-up's central claim
is that a committed bar produced a confirmation that was an artifact —
deleting the script that produced it would remove the evidence for that.
