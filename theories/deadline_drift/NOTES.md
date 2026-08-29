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
