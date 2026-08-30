# The promotion key

Key version: 1
(Spec: `docs/superpowers/specs/2026-08-30-go-session-structure-design.md` §5.
Evaluator: `tools/promotion.py`; `python -m tools.cli promote --help`.)

**This key decides what the user is told about.** Every candidate a theory
records classifies onto exactly one rung below. A session reporting bets
cites the rung for every bet shown *and* for every bet withheld; a session
that cannot name the rung for a decision has found a gap in the key, and
the gap goes in the report's "For your ruling" section — never an
improvised call.

**The rungs are mechanical and code evaluates them.** `cli promote` prints
the rung and every criterion it checked; sessions never eyeball n's and
calibration numbers against this table by hand (eyeballing is where the
documented row-mixing failures live). What stays judgment is upstream —
stage-2 verdicts, endorse/reject — and downstream — dissent (§Amendment).

## Order of evaluation

A candidate is tested against the rungs in this order; the first match is
its rung. "Segment" always means the row `tools/slices.py::ranking_segment`
returns under the chain pool — the ready-slice / complement / aggregate
partition, never a hand-picked score row. All three rank inputs come from
that one segment row.

| rung | name | criteria |
|---|---|---|
| R6 | CONTROL | Already settled; or `disposition='rejected'` (the stage-2 control group); or claimed `edge_pts_net` ≤ 0 (an observation row — ruling 13: recorded so cells accrue, never a bet). |
| R2 | RISKLESS | Basket whose cost plus fees ≤ `min_payout` — an arbitrage, not a forecast. Reported in its own bucket, legs itemized with per-leg asks and the verify-every-leg warning; never averaged into forecast numbers. |
| R4 | ACCRUING (gate) | A judgment theory's candidate not yet `endorsed` — stage 2 has not run, so nothing interpretable is being withheld; it is waiting. |
| R5 | MEASURED-AGAINST | Segment past the evidence gates (n_clusters ≥ 10 and n_days ≥ 5, out of sample) with `calibration_edge_net` ≤ 0. Suppressed from the bets table **even when today's claimed edge is positive** — the measured record outranks the claim. Goes to the diagnosis queue, not the trash. |
| R1 | RECOMMENDED | Segment past the evidence gates with `calibration_edge_net` > 0, **and** claimed net edge recomputed at today's ask > 0, **and** executable (below). |
| R3 | PROVISIONAL | Segment's out-of-sample record positive but below the gates, spanning ≥ 3 settlement days (ruling 14: fewer has no usable error bar), **and** positive at today's ask, **and** executable. Reported in the bets table labeled with exactly what is missing (e.g. "n_clusters 7/10, n_days 4/5"). |
| R4 | ACCRUING | Everything else: recorded, evidence building, nothing demonstrated yet. Reported as counts per theory in the Activity section, never as a bet. |

## Preconditions shared by R1 and R3

- **Today's ask, not the recorded entry.** The claimed edge is adjusted to
  the current ask (price delta plus fee delta). Edge ≤ 0 at today's ask →
  R4, "edge gone at today's ask". An unquoted evaluation is flagged
  `unquoted` and must be re-quoted before the bet is acted on.
- **Executability.** Spread (in points) must be smaller than the claimed
  net edge at the ask, and an ask must exist (depth floor: 1 contract,
  unless the theory's RUNBOOK states more). Fails → R4, "not takeable".
- **Ranked edge is display, not a gate.** `rank.ranked_edge` is computed
  from the same segment row and shown beside the claim; a positive R1/R3
  is reported even when shrinkage makes the ranked edge small — the
  numbers do the discounting, per the ranking rules.

## Escalations the evaluator raises

- **Orphaned evidence** — a slice READY out of sample at a prior theory
  version while the current version's segment is not ready and no proven
  carry pools them (`promotion.orphaned_evidence`). The proven edge has no
  bet path; adopting the rule is a version-bump decision. Goes in "For
  your ruling" every session until ruled.
- **Below-gates slice match** — a candidate matching a registered slice
  still short of its gates ranks on the complement/aggregate with the
  match noted, exactly as `ranking_segment` reports it.

## Amendment

The key changes like a theory procedure: edit this file, bump
`Key version`, mirror `promotion.KEY_VERSION`, and log the change —
`tests/test_promotion.py` holds doc and code to the same version and the
same rung set. A session that disagrees with a rung's answer for a
specific candidate reports the rung's verdict **and** its dissent as a
proposed amendment; it never overrides the rung in the report.

## Changelog

- v1 (2026-08-30) — initial six rungs, per the go-session-structure spec.
