# deadline_drift — lab notebook

Dated, raw, append-only. The distilled version lives in `THEORY.md`.

## 2026-08-29 — proposed, v1, bins not yet collected

Promoted from idea 3 after five audit rounds. Full narrative in
`studies/2026-08-29-deadline-drift-classifier-audit/STUDY.md`; short version
is that a board-wide mechanical screen is unreachable (round 5: 12% against
a 10% bar, not distinguishable from round 4's 16%) and the allowlist is
(round 5b: 70/70 series, exhaustive, no sampling error).

Three things that surprised me, worth a future session knowing:

- **The horizon snapshot nearly fooled me.** First run of the screen
  returned 0 candidates with 856 markets "outside horizon", which reads like
  a dead theory. It is not: the population is long-dated by construction, so
  41-in-window today is a *stock*, and the *flow* is 714 closes over the
  next 12 months. Check flow, not stock, for any theory whose markets are
  long-dated. I nearly reported a viability problem that does not exist.
- **The 7–21 day bucket is empty** — 41 markets at 0–7d, 0 at 7–21d. Close
  dates in these families cluster hard on month boundaries. If the day bins
  come back sparse in the middle of the window, that clustering is why, and
  the bin edges may need to follow the clustering rather than round numbers.
- **`mutually_exclusive` is reliable here and unreliable board-wide.** Looks
  contradictory, is not. The price test catches a partition only when it is
  tightly priced: `KXUKCABOUT` is 23 legs summing 0.90 and is caught;
  `KXSUPERBOWLHEADLINE` is 54 illiquid longshot legs summing 3.64 and is
  missed. A signal's hit rate is a fact about a population, never about the
  signal — backlog index step 0e, which came out of this same work.

Not done and deliberately so: **no hazard bins**. They are the expensive
rate-limited step, section 7 forbids collecting them until the population is
settled, and the population only settled today. That is the next step and
the only thing between v1 and `testing`.

## 2026-08-29 (later) — the thesis, finally measured. It does not hold up.

After five audit rounds spent on the *screen*, the actual claim got tested
for the first time. Tier A, no model anywhere.

**What was collectable, and why that is the headline.** Kalshi archives
settled markets out of its public API ~60 days after close. Walking all 70
allowlist series returned **112 settled markets** — that is not a sample,
it is the *entire fetchable history* for this population. Candles for all
112 gave 2,805 daily observations, saved raw in
`hazard_observations.json`.

**Clustered by market**, because one market contributes ~25 daily rows that
all share a single outcome — treating those as independent would inflate n
by 25x and manufacture significance out of nothing:

```
POOLED, late window (<=21d), entry band ($0.05-0.60), n = 55 markets
  mean yes_ask      0.148
  realized P(YES)   0.182
  gap              -3.4 pts   (SE 5.2, z = -0.66)
```

**The point estimate has the wrong sign.** The thesis says YES is
*overpriced* late, so the gap should be positive. It is negative — YES was
mildly *under*priced — and not significant either way. Kill criterion 1 was
"implied and empirical hazard agree within fees across all bins"; on this
evidence they agree, with the point estimate leaning against the theory.

**What I am NOT doing: writing `hazard_bins.json`.** With `min_n=30`, cell
`d3|p0` (n=31) would squeak through and start emitting +4.4pt "edges" from
a single thin cell. That is manufacturing bets out of noise, so the file
stays absent, `price()` keeps returning nothing, and the theory stays
`proposed`. The bins are data, not a live instrument.

**One pattern, recorded as a hypothesis and explicitly NOT an edge.** The
only positive cells are the cheapest price bin ($0.05-0.15), and they are
the three biggest cells: +1.0 (n=19), +2.8 (n=27), +4.4 (n=31), monotone in
days-remaining. That is longshot bias exactly where the thesis predicts it,
and it is the *only* place the effect appears — everything at $0.15-0.60
runs negative. Per CLAUDE.md's pairing discipline this is a hypothesis to
pre-register for a forward test, never an edge to bet on the data that
suggested it. If it is pursued, the pre-registration is: **NO on allowlist
markets with yes_ask in $0.05-0.15 and 7-21 days to close.**

**The urgent operational finding.** 112 markets is all that exists *today*,
and the window keeps rolling — markets settling now become unfetchable in
60 days. This population produces ~714 closes a year, so a capture job
running from today would hold ~350 by February and ~700 by next August. The
repo has `market_snapshots` and the settled-history machinery already; what
is missing is anything that routinely sweeps THIS population before it
expires. That is worth more than any further screen work, and it is the
thing that decides whether this theory is ever testable at n that matters.

## 2026-08-29 (later still) — CORRECTION: the previous entry was measuring an artifact

**Retract the "-3.4 pts, thesis does not hold" result above.** It was
contaminated by early-settlement lookahead through the *time* axis. Session
09 flagged the general shape while reviewing an unrelated amendment; I
checked, and it had already bitten.

**The bug.** `days_to_close` was computed from each settled market's
`close_time`. These markets carry `can_close_early=true`, and measured
across all 112:

```
              deadline - actual_close      closed >3d early
  YES  n=34   median 209.6d                32/34
  NO   n=78   median  -0.2d                 0/78
```

A NO market runs to its deadline. A YES market stops trading the moment the
event fires — a median of seven months early. So the two arms were on
**different clocks**: "21 days to close" meant *21 days before the deadline*
for NO markets and *21 days before the event* for YES markets, which is
precisely when the price is climbing toward 1.0. The first result therefore
measured "prices rise before events happen", which is true and worthless.

It is also a **selection** error, not only an axis error: a market that
resolves YES early never experiences the quiet-near-the-deadline state the
thesis is about, so conditioning on actual close imported exactly the
population the thesis excludes.

**Re-anchored on the deadline stated in the rules text** (parsed for
112/112), same clustering by market:

```
                        contaminated      corrected
  anchor                actual close      stated deadline
  markets                        55               48
  mean yes_ask                0.148            0.109
  realized P(YES)             0.182            0.062
  gap                        -3.4 pts        +4.7 pts   (SE 3.5, z=1.34)
  net of fees                      —          +4.0 pts
  outcome mix                     —        3 YES / 45 NO
```

**The sign flips.** Corrected, the point estimate is *thesis-consistent*:
YES overpriced late by ~4.7 gross, ~4.0 net after the 0.68pt fee on a NO at
$0.891.

**It is not a demonstration.** z=1.34 is not significant, and the whole
estimate rests on **3 YES outcomes** — one more would move P(YES) from
0.062 to 0.083 and cut the gap by a third. This is a promising point
estimate on a sample far too small to reject zero, and it must not be
reported as anything else.

Two lessons worth carrying, both mine:

- **Check the clock before trusting a hazard measurement.** On any "does X
  happen by D" market, actual close is a function of the outcome. Anchor on
  the *scheduled* deadline, always. The corrected pipeline parses it from
  the rules text and it was recoverable for 112/112.
- **I published the artifact before checking it.** The previous entry and
  its commit stated a conclusion with the wrong sign, and it survived
  because the result was *unsurprising* — a thesis failing is exactly what I
  had been primed to expect after five rounds of screen work. A result that
  confirms your current mood deserves the same scrutiny as one that
  offends it.

### Reproducibility fix, and why dropping early-YES markets is not survivorship bias

The correction above was committed as prose: the numbers retracting a
committed conclusion existed only in one session's memory. Fixed —
`collect_settled.py` persists the raw `list_settled` payloads, per-market
anchors (parsed deadline, actual close, and the gap), and candles carrying
**both** `days_to_close` and `days_to_deadline`; `hazard.py` regenerates
both tables from disk. `python -m theories.deadline_drift.hazard` prints the
contaminated and corrected rows side by side, so the retraction is a number
you can run rather than a claim you have to trust.

`hazard_observations.json` is deleted rather than kept: every row in it was
anchored to actual close with no absolute dates, so it could only ever
reproduce the *wrong* table. `data/candles.json` supersedes it and carries
both anchors.

**On the 7 markets the corrected view drops.** At a glance, excluding
markets that resolved YES before deadline−21 looks like selection — the
correction removes exactly the arm that would raise P(YES). It is not.
Conditioning on "still open at deadline − h" is the hazard-analysis
**at-risk set**: a market that has already resolved YES is not available to
bet at that moment, so excluding it is precisely what makes P(YES) the right
*conditional*. The number answers "given I can still buy NO here, how often
does YES come in?" — the only question a bettor can act on. Anchoring on
actual close does the opposite: it drags each YES market's resolution
moment into the late window and asks a question nobody can trade.

### Canonical numbers

`python -m theories.deadline_drift.hazard` is the canonical source for every
figure in this notebook; anything quoted here that disagrees with it is
stale. Session 09 found the two disagreeing on the YES early-settlement
median (script 212.9 vs notes 209.6) and the data was right: `hazard.py`
was taking `v[len(v)//2]`, which for even n is the upper-middle element
rather than the median. Fixed to `statistics.median`. **209.6 days is
canonical.** A reproducible script is only worth as much as its arithmetic,
and this one was checked against a number written down before it existed —
which is the only reason the bug surfaced.

## 2026-08-29 (cont.) — deadline-drift's classifier audited three times; the spec is missing its biggest exclusion (migrated from RESEARCH_LOG.md)

**Did:** Started backlog #2 (`deadline-drift`) with the piece its own spec
calls "most of the work" and makes a kill criterion: the rules-text
classifier and a 50-market hand audit. Ran the audit **three times** on
disjoint systematic samples of the 117,272-market board. No API calls and
no hazard bins collected — deliberately, because the bins are the
expensive step (Kalshi rate-limits to ~4–5 req/s) and misclassification
poisons them. Study, classifier and all three judged samples:
`studies/2026-08-29-deadline-drift-classifier-audit/`.

| round | population | misclassified /50 | rate |
|---|---|---|---|
| 1 | 7,613 | 20 | **40%** |
| 2 | 5,155 | 10 | **20%** |
| 3 | 4,792 | 6 | **12%** |

**Learned:**

1. **The spec's non-goal list is missing its largest contaminant.** It
   names scheduled certainties and continuous thresholds; the dominant
   family is neither. **Multi-destination "which branch" markets** — "X's
   next team is Y before D", "Z is the first person confirmed as
   Commissioner" — resolve YES only if the event happens *and* lands on
   this branch, making them a hazard **times a conditional multinomial**.
   At board scale that is **2,687 markets, 34% of the whole by-deadline
   population**. Anyone implementing the spec as written pools all of it
   into the hazard bins. Spec amended in place.
2. **The classifier is a long tail of prose, not a pattern set.** Every
   round found a family the previous one had not imagined — prose count
   thresholds ("the number of X ... is at least 5"), role succession
   ("becomes Chief Minister following the 2026 Manx general election"),
   scheduled competition outcomes ("wins a tennis major"), and in round 3
   a price threshold that said "strictly greater than" instead of
   "above". The rate halves each round, which is either convergence or an
   irreducible floor; one more cheap round distinguishes them.
3. **Auditing before collecting was the right order and nearly wasn't
   taken.** The instinct was to build the bins first. At 40%
   misclassification the bins would have been meaningless, and they cost
   hours of rate-limited API time that cannot be parallelised.
4. **The theory itself looks good.** 4,792 markets in 859 series survive,
   3,079 in the entry band, and the survivors are exactly the thesis:
   traded / pardoned / charged / IPO-confirmed / legislation-passed
   before a date.

Idea 3 moved `considered` → `investigating` with all of this recorded.

**Round 4, run immediately after: 16% — it went UP.** That is the
answer. Every fix rounds 1–3 implied was folded in and the rate did not
improve; at n=50 the SE on a 15% rate is ~5 points, so 12% and 16% are
one number — **a plateau near 15%**, above the spec's own bar. Five of
round 4's eight misses were multi-destination *again*, in phrasings no
extension of the round-3 pattern anticipates: "the next club that
Cristiano Ronaldo joins is CF Monterrey", "Russia is the first country to
launch a manned mission", "the next new Secretary of Defense ... is Mike
Pompeo", "leaves before any other Pro Football head coach", "a coalition
that includes SPD make up the next elected ruling government".

**The residue is semantic, not syntactic** — "does this condition on
which branch the event takes?" is a meaning these share, not a string.
That is exactly CLAUDE.md's line for when to reach past code: mechanics
yield to a regex (the gate work earlier today), reading comprehension
does not.

**Next: a user decision, because every option costs something the spec
promised.** (1) a cheap LLM gate — clears the bar, forfeits **tier A**,
which was this theory's defining property; (2) a series allowlist of the
~20 unambiguous recurring families — stays tier A, smaller population,
and reintroduces the maintenance treadmill today's gate work moved away
from; (3) drop it. Spec section 3 amended to say section 4 is not
implementable as written. **No hazard bins under any option until this is
settled.**

