# The promotion key

Key version: 4
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

**Backtested evidence counts exactly as forward evidence does** (user
ruling 2026-08-31). A segment's out-of-sample record pools settlements
that came in forward with rows replayed by a tier A or tier B backtest,
and the gates below are applied to that pool — for a registered slice as
much as for a whole theory. A backtested edge is never described as
weaker for being backtested; sample size is already priced into the
t-statistic and into credibility, and charging for it twice taught
theories to avoid the honest instrument. Three things still count for
nothing: **tier C** (a model may recall outcomes it was trained on), a
replay whose **tier was never recorded**, and the run a slice was
**mined from** (`mined_from_run_ids` — a pattern cannot vouch for
itself). R1 and R3 results **disclose** how much of the record behind
them is replayed; that is disclosure, and no rung reads it.

| rung | name | criteria |
|---|---|---|
| R6 | CONTROL | Already settled; or `disposition='rejected'` (the stage-2 control group); or claimed `edge_pts_net` ≤ 0 (an observation row — ruling 13: recorded so cells accrue, never a bet); or **superseded** — the theory's current version has re-decided the same position (below). |
| R2 | RISKLESS | Basket whose cost plus fees ≤ `min_payout` — an arbitrage, not a forecast. Reported in its own bucket, legs itemized with per-leg asks and the verify-every-leg warning; never averaged into forecast numbers. |
| R4 | ACCRUING (gate) | A judgment theory's candidate carrying no confidence bucket — stage 2 has not run, so nothing interpretable is being withheld; it is waiting. A bucket **is** the interpretation: a judged row falls through to its segment and is ranked on the measured record, never held for a further model's approval. |
| R5 | MEASURED-AGAINST | Segment past the evidence gates (n_clusters ≥ 10 and n_days ≥ 5, out of sample) with `calibration_edge_net` ≤ 0. Suppressed from the bets table **even when today's claimed edge is positive** — the measured record outranks the claim. Goes to the diagnosis queue, not the trash. |
| R1 | RECOMMENDED | Segment past the evidence gates with `calibration_edge_net` > 0, **and** claimed net edge recomputed at today's ask > 0, **and** executable (below). |
| R3 | PROVISIONAL | Segment's out-of-sample record positive but below the gates, spanning ≥ 3 settlement days (ruling 14: fewer has no usable error bar), **and** positive at today's ask, **and** executable. Reported in the bets table labeled with exactly what is missing (e.g. "n_clusters 7/10, n_days 4/5"). |
| R4 | ACCRUING | Everything else: recorded, evidence building, nothing demonstrated yet. Reported as counts per theory in the Activity section, never as a bet. |

## Supersession — a version bump forks a position, it does not replace it

A position is identified by `(theory_id, theory_version, run_mode, lane,
kalshi_ticker, outcome)`. The version is *in* that key, so bumping it does
not supersede the old row — it **forks** it. The old row stops receiving
attempts and freezes at whatever the superseded procedure last thought,
and nothing ages it out, because every staleness check in this key is
about **price** and a frozen row re-quotes perfectly well.

That is worse than it sounds, for three reasons: it is silent (both rows
are legitimate records and nothing errors); it survives until the market
settles, accumulating another orphan per bump; and it **preferentially
preserves endorsements** — when a version deletes the stage that could
endorse, every `endorsed` row is stranded at a version whose procedure no
longer exists, and those are exactly the rows most likely to clear R1.

**A row is superseded when the theory's current version has re-decided
the same position**, matching the full identity minus the version. It
then takes R6, with a reason naming the superseding row.

- **Absence of a successor is not supersession.** A row merely behind the
  registry's current version keeps its rung — a market that was not
  screened today (it stopped qualifying, or the run did not reach it) has
  not been re-decided, and suppressing it would bin live candidates for a
  bookkeeping reason.
- **`run_mode` and `lane` are part of the match.** A tier A/B replay or an
  `exp/` experiment row is not a decision about today's market and never
  suppresses a live one.
- **The two sides of a ticker are different positions**, not two views of
  one, so a fresh YES row does not supersede a live NO.

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
  version while the current version's segment is not ready and no chain
  pools them (`promotion.orphaned_evidence`). The proven edge has no bet
  path.

  **The fix is to relink the evidence chain, never to adopt the rule
  into the parent's screen.** An orphan is a *versioning* fact: almost
  always a bump recorded `breaking` under the old default, correctable
  with `theories.reclassify_bump`, after which the sub-theory is ready at
  the current version and routes its own bets with nothing else changed.
  Folding the predicate into the parent buys no different bet and costs
  the complement and the out-of-sample bookkeeping — see CLAUDE.md,
  "A sub-theory is maintained, not absorbed". Goes in "For your ruling"
  every session until ruled.
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

- v4 (2026-09-01) — a position superseded by a re-decision at the
  theory's current version takes R6 (§Supersession). Prompted by an
  incident the same day: `insider_judgment` opportunity 13663
  (`KXPRESSSECANNOUNCE-26AUG-SEP08` NO, v4, `endorsed`,
  `edge_basis='prior'` +2.0) returned **R1 RECOMMENDED**, while the same
  market re-judged that hour at v6 with fresh research recorded as 109994
  — `weak`, `edge_basis='measured'`, −1.02 — and returned R6. Two live
  rows on one market promoting R1 and R6 at once, and the R1 was the
  stale one, claiming an unmeasured placeholder edge the current
  procedure would never claim. The floor report of 2026-09-01 caught it
  by hand and said so; nothing in the key would have. Rungs, their order,
  and every other criterion are unchanged, and no recorded row is
  reinterpreted — this governs what is *reported* from here.
- v3 (2026-09-01) — the R4 gate reads the confidence bucket
  instead of `disposition='endorsed'`. The criterion and the rung's own
  rationale had come apart: the rationale says the rung holds a
  candidate whose *stage 2 has not run*, while the criterion demanded a
  second, price-aware model endorse it on top. A bucket records that
  stage 2 ran, so a bucketed row now falls through to its segment and
  is ranked on evidence. Prompted by `insider_judgment`, whose entire
  measured record — including the 314 out-of-sample rows behind its
  `strong-moderate-no` slice — was generated by a procedure with no
  such endorsement step, while the live path's endorsement gate was
  rejecting 72 of 79 rows that the slice's evidence entitled. Rows
  already recorded `rejected` are untouched and stay R6: this governs
  what is judged from here, and rewrites no history. Rungs, their
  order, and every other criterion are unchanged.
- v2 (2026-08-31) — backtested evidence counts toward a segment's
  gates exactly as forward evidence does, for a registered slice as
  much as for a whole theory (user ruling). A tier A/B replay no
  longer has to be designated at registration; what is declared
  instead is the run a slice was *mined from*, which never vouches
  for it. Tier C still counts for nothing, and so does a replay with
  no recorded tier. R1/R3 results now disclose how much of the record
  behind them is replayed. Rungs and their order are unchanged.
- v1 (2026-08-30) — initial six rungs, per the go-session-structure spec.
