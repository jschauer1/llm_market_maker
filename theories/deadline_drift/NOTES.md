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
