# Entry timing — pre-registration, written BEFORE looking

**Date:** 2026-08-30 · **Status:** pre-registered, not yet run ·
**Tier:** A (no model anywhere)

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

`studies/2026-08-29-series-bias-mining/data/collect.db` as it stood at
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
