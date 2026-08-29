# Theory slices — subset edges with their own credibility

Date: 2026-08-29. Status: implemented alongside this spec.

## Problem

A theory's aggregate can be flat while a defined subset of its output
carries a real, mechanism-backed edge. The worked example is
`insider_judgment`: the full screen is breakeven at scale
(`backtest-2026-08-25-insider-fullcov`, n=3,181, t_ev −0.25), but the
bet rule pre-registered after the s200 judged round — strong-or-moderate
verdict, NO side — scored **+4.92 pts net (p=0.0008, 312 rows / 85
events)** on the 257 events judged *after* pre-registration. Today the
ranking layer has one credibility number per (theory, disposition), so a
strong-moderate-NO candidate and a weak-YES candidate from the same
theory rank on the same evidence row. The proven subset is buried by the
aggregate, and the unproven remainder borrows whatever the subset earned.

The repo's existing answer — promote the slice to a sibling theory
(`no_side_premium` came out of `mention_family`'s slicing pass this way)
— is right when the subset needs its own *procedure* (its own screen,
entry rule, population). It is too heavy when the subset is just "these
rows of the parent's normal output, weighted on their own record."

## Design

### A slice is a registered, mechanical sub-population

New table `theory_slices` (one row per (theory_id, slug)):

- `predicate_json` — a declarative AND-of-clauses over **recorded ledger
  fields**: `outcome` (list), `confidence` (list of bucket labels),
  `entry_price` ({min?, max?}, inclusive), `extra` (exact-match keys in
  `extra_json`). Unknown keys raise. Baskets never match (the vocabulary
  is single-leg). Predicates are data, never judgment — the structural
  ladder applies: if a slice boundary can't be written in this
  vocabulary, it isn't a slice, it's a new theory.
- `hypothesis` — the mechanism claim (why *this* subset should differ).
  Required; a slice with no mechanism is curve-fitting with a slug.
- `origin` — where the pattern was found (run ids, study, notes entry),
  and — when `registered_at` is passed explicitly rather than defaulted
  to now — the citation for that earlier date (a dated THEORY.md entry,
  a study, git history). The registration date is an evidentiary claim
  and must be auditable.
- `oos_run_ids` — runs designated out-of-sample **at registration**,
  with the argument for why living in `origin`.
- `priority` — tie-break when registered slices overlap; higher wins,
  then earlier `registered_at`.
- `status` — `registered` | `retired`. **A slice is immutable once
  registered**: changing a predicate would silently merge two different
  hypotheses into one track record, exactly the merge theory versioning
  exists to prevent. Supersede with a new slug and retire the old one.
  Retiring is a governance call (user / supervisor), like retiring a
  theory: a retired slice stops driving ranking but keeps reporting.

Registering a slice never bumps the theory's version. The theory's
decision procedure — what it screens, judges, and records — is
untouched; a slice only changes which evidence row the *ranking layer*
feeds into credibility shrinkage. Facts are data, not procedure.

### Out-of-sample discipline is structural, not aspirational

The pairing discipline says a pattern found post-hoc is a hypothesis to
pre-register, never an edge to bet on the same data that suggested it.
The slice mechanism enforces that in code: an observation matching a
slice's predicate counts toward the slice's **credibility** only if

- its decision date is strictly after the registration day (forward
  evidence — live rows accrued after the hypothesis existed, or a
  backtest whose *decision days* postdate registration), **or**
- its run is listed in `oos_run_ids` (a disjoint sample or a
  post-pre-registration judged round, with the argument recorded in
  `origin`),

and its run is **not tier C** (contaminated evidence never feeds
credibility, here as everywhere). Everything else that matches the
predicate is reported separately as `in_sample` — visible for
diagnosis, never in the credibility path. A backtest over historical
decision days is in-sample *by default*, however recently it ran; only
explicit designation with a recorded argument moves it.

### Readiness gates, then a partition

A slice may drive ranking only when its out-of-sample evidence clears

- `n_clusters ≥ 10` (`rank.PROBATION_N` — the same probation floor
  credibility itself uses, on the same cluster semantics), and
- `n_days ≥ 5` distinct settlement days (the same floor as
  `buckets.MIN_BUCKET_DAYS`, from the settlement-day clustering study —
  one hot night must not define a slice).

Below the gates, nothing changes: candidates rank on the theory's
row exactly as before, and the slice is reported as "registered,
accruing evidence." At or above them, the theory's evidence pool is
**partitioned**:

- a candidate matching a ready slice ranks on that slice's
  out-of-sample score (n_clusters, calibration_edge_net,
  mean_claimed_edge — all three from the same row, the existing
  no-mixing rule);
- every other candidate ranks on the **complement** — the theory's
  observations matching no ready slice — so the remainder neither
  borrows the slice's edge nor hides behind the aggregate it used to
  prop up. The partition cuts both ways: a ready slice whose
  out-of-sample record is *bad* drags exactly its own candidates down.

The `rank.credibility` / `ranked_edge` formula is untouched. The
mechanism only selects which score row feeds it, which is the same
choice find-edge already makes per disposition.

### Evidence pool

Segment scores pool `run_mode` live + backtest (tier C excluded), via
`score.observations()` — because for a theory like `insider_judgment`
the demonstrated slice evidence *is* tier-B backtest rows, and a
live-only pool would ignore precisely the record the mechanism exists to
use. All segments in one report (slices, complement, aggregate) come
from the same pool, so their numbers are comparable. Position identity,
decision-attempt scoring, cluster semantics, and the exp/-lane exclusion
are all inherited unchanged from `score.observations`.

## Components

- `db/schema.sql` — `theory_slices` (new table; purely additive).
- `tools/score.py` — observation dicts gain the fields a predicate and
  the OOS split need (`position_kind`, `outcome`, `confidence`,
  `entry_price`, `extra`, `decision_date`, `run_id`, `resolved_day`);
  public seam `observations(...)` + `aggregate(...)`. `compute_score`
  behavior is byte-identical (it now composes the two).
- `tools/slices.py` — `build_matcher`, `register_slice`, `retire_slice`,
  `list_slices`, `segment_report` (aggregate + per-slice oos/in-sample +
  complement + readiness), `ranking_segment` (one candidate → which
  segment ranks it).
- `tools/cli.py` — `slices register | list | report | match | retire`.
- Skills/docs — CLAUDE.md ranking section, find-edge §6/§7,
  score-theories, tools/README.md.

## Testing

`tests/test_slices.py`: matcher semantics (including fail-loud unknown
keys, None-confidence, basket exclusion); registration immutability;
OOS/in-sample split by date rule, `oos_run_ids`, and tier-C exclusion;
readiness gates on clusters and settlement days; the ranking partition
(slice / complement / aggregate fallback). Full existing suite must stay
green — `compute_score` and everything downstream is unchanged
arithmetic.

## First registration

`insider_judgment` / `strong-moderate-no`: predicate
`{"outcome": ["no"], "confidence": ["strong", "moderate"]}`,
`registered_at` 2026-08-26 (the bet rule's actual pre-registration,
recorded in THEORY.md Learnings 2026-08-26 and
`backtests/RESULTS.md`), `oos_run_ids` =
`backtest-2026-08-26-insider-judged-s200b`,
`backtest-2026-08-26-insider-judged-s57` (judged after the rule was
registered; s200, which generated the rule, stays in-sample).

## Alternatives considered

- **Sibling theory per slice** — the status quo. Kept for subsets that
  need their own procedure; too heavy for pure re-weighting, and it
  forks the ledger identity of what is really one theory's output.
- **Bucket-level credibility** — buckets already carry measured *edges*
  for pricing, but they are one-dimensional (the label), cannot express
  side or price-band conditioning, and have no OOS discipline; slices
  rank, buckets price. Orthogonal and both kept.
- **Slice-aware SQL in `compute_score`** — rejected; predicate
  evaluation in Python over the enriched observation list keeps the
  scoring SQL untouched and the predicate vocabulary in one place.
