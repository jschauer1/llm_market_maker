# Attempt fidelity: an attempt records everything the run recorded

**Date:** 2026-08-27. **Status:** design approved, implementation not started.
**Amends:** `docs/superpowers/specs/2026-08-27-position-identity-design.md`.
The position-identity design stands — the key, the lane, the child tables and
the migration are all correct. This spec changes what `opportunity_attempts`
holds, adds the plumbing a backtest needs to date its attempts, and closes
three defects found while validating the plan against the live database.

---

## 1. The problem

Position identity merges rows. That is the point — a bet re-proposed by a
second run must stop counting as a second observation. But a merge is also a
write, and the merged row can only hold one value per column. The design as
written keeps nine fields per attempt:

```
opportunity_id, decision_date, run_id, recorded_at,
entry_price, edge_pts_net, disposition, confidence, judged_blind
```

Everything else a run supplied — `rationale`, `extra_json`, `spread_at_call`,
`volume_at_call`, `model_prob`, `edge_pts_gross`, `fee_pts`, `edge_basis`,
`suggested_size`, `evidence_source`, `evidence_market_id`, `scan_id` — has no
per-attempt home. On a re-sighting the position row either overwrites the old
value or discards the new one, and the losing value is gone.

This is not a migration concern. The one-time migration copies the whole table
to `opportunities_premigration_<stamp>` first, so historical values survive in
the file. Forward writes have no backup at all.

The fields that matter most are the two that carry a theory's actual thinking:

- **`rationale`** — last writer wins (`COALESCE(excluded, existing)`).
- **`extra_json`** — never updated. The first run's copy is frozen; every
  later run's is silently discarded.

`extra_json` is where every theory stores its own features. All four writers
are theory code: `calibration_harvest/collect.py`,
`insider_judgment/backtest_fullcov.py`, `insider_judgment/backtest_judged.py`,
`mention_family/backtest.py`.

This contradicts the governing data convention in `CLAUDE.md` — "save as much
as you can, while you can", "raw payloads over distillates", "a future session
that never saw this one should be able to reconstruct any result from disk".

## 2. Evidence

Measured against `db/market_edge.db` on 2026-08-27 (9,732 rows, 1,709 duplicate
groups). Columns that differ **within** a group, and would therefore lose a
value on merge:

| column | groups affected | carried per attempt today? |
|---|---|---|
| `rationale` | 1,702 | no |
| `extra_json` | 1,680 | no |
| `confidence` | 1,569 | yes |
| `judged_blind` | 1,564 | yes |
| `volume_at_call` | 19 | no |
| `entry_price` | 17 | yes |
| `spread_at_call` | 16 | no |
| `interpreted_at` | 16 | no (position-level by design, §7) |
| `interpretation` | 11 | no (position-level by design, §7) |
| `edge_pts_net` | 5 | yes |
| `user_action` | 5 | no (fills, §7) |

`extra_json` keys present only on the later row, and therefore dropped —
**1,564 groups each**: `rules_diverge_from_title`, `researched`, `batch`,
`source_run`.

The pattern that produced every one of these is the standard campaign shape:
a broad mechanical screen, then a judged pass over a subset of the same
markets. It recurs every campaign, so the loss is ongoing, not historical.

Two live consumers read the dropped data:

- `theories/insider_bias/insider_judgment/backtests/score_campaign.py:58`
- `theories/insider_bias/insider_judgment/reprice_entry_window.py:66`

Both select `WHERE o.run_id LIKE 'backtest-2026-08-26-insider-judged-%'` and
read `x.get("rules_diverge_from_title")` out of `o.extra_json`. They return
**1,561 rows today and 0 after the migration**, without erroring — the merged
row's `run_id` is the earliest run's, which is `...-insider-fullcov`.
`score_campaign.py` is what regenerates `RESULTS.md`, so the "numbers stay
regenerable from the ledger" property in `CLAUDE.md` breaks silently.

## 3. The principle

**The position row is a rollup. The attempt is the record.**

`opportunities` keeps its identity, its first-sighting anchors
(`entry_price`, `first_seen_at`, `screen_edge_pts_net`) and a cached current
best view — the thing a `list` or a ranking reads without a join.
`opportunity_attempts` holds what actually happened, one row per decision day
per run, complete.

That gives the merge a rule with no exceptions: **a merge may overwrite the
rollup, and may never lose an attempt's value.**

## 4. The attempt table

Full parity. `opportunity_attempts` carries every argument
`ledger.record_opportunity` accepts that is not part of the position's
identity:

```sql
CREATE TABLE IF NOT EXISTS opportunity_attempts (
    opportunity_id     INTEGER NOT NULL REFERENCES opportunities(id)
                       ON DELETE CASCADE,
    decision_date      TEXT NOT NULL,
    run_id             TEXT NOT NULL,
    recorded_at        TEXT NOT NULL,
    scan_id            TEXT,
    entry_price        REAL NOT NULL,
    spread_at_call     REAL,
    volume_at_call     REAL,
    model_prob         REAL,
    edge_pts_gross     REAL,
    fee_pts            REAL,
    edge_pts_net       REAL NOT NULL,
    edge_basis         TEXT NOT NULL DEFAULT 'prior'
                       CHECK (edge_basis IN ('measured','prior','model')),
    disposition        TEXT NOT NULL DEFAULT 'screened'
                       CHECK (disposition IN ('screened','endorsed','rejected')),
    confidence         TEXT,
    judged_blind       INTEGER,
    rationale          TEXT,
    suggested_size     REAL,
    evidence_source    TEXT,
    evidence_market_id TEXT,
    extra_json         TEXT,
    PRIMARY KEY (opportunity_id, decision_date, run_id)
);
```

`extra_json` is already each theory's escape hatch, so full parity means a
theory can add a feature without the ledger needing to know about it and
without that feature being lost on the next merge.

**The parity rule is enforced, not documented.** A new test in
`tests/test_conventions.py` inspects `record_opportunity`'s signature and
asserts that every parameter outside the identity set
(`theory_id`, `theory_version`, `run_mode`, `kalshi_ticker`, `outcome`,
`run_id`, `decision_date`, `now`) has a matching column on
`opportunity_attempts`. Adding a parameter without an attempt column fails at
the commit that adds it, not a year later when someone tries to reproduce a
result.

`_record_attempt` writes all of it. Its `ON CONFLICT` update keeps the
last-writer-wins rule for the measured fields (a second recording of the same
decision in the same run is a correction) and `COALESCE`s the judgment fields
so a later judging pass adds a label without erasing one.

## 5. Backtest support: dating an attempt

An attempt is keyed on the day the theory was **deciding about**, never the
day the code ran. Without this the whole table degenerates: a backtest that
replays sixty days in one session stamps every attempt with the same
`decision_date` and the same `run_id`, the primary key collapses them, and
sixty decisions become one row.

The position-identity plan adds the `decision_date` parameter but never wires
it to a caller, so this is exactly what would happen.

Three layers, all required:

**a. `TheoryContext.now` is the source for the contract path.**
`tools/theory.py:120` `OpportunityRecord.from_scored` passes
`decision_date=ctx.now.date().isoformat()`. `TheoryContext.now` is already
declared as the harness's as-of time, and `CLAUDE.md` already assigns time to
the harness; a replay that sets `ctx.now` to the replayed day gets correctly
dated attempts for free, and a live run gets today, which is what the default
would have produced anyway.

**b. `record_opportunity` and `record_basket` require it for backtests.**
Mirroring the existing rule at `tools/ledger.py:169` — `run_id` is already
mandatory for `run_mode="backtest"` — an omitted `decision_date` on a backtest
raises. A live run keeps the wall-clock default. This makes the failure mode
impossible rather than merely documented, which matters because the symptom of
getting it wrong is silent data collapse rather than an error.

**c. The four direct callers pass it.** Each already has the day in scope:

| caller | source |
|---|---|
| `insider_judgment/backtest_fullcov.py:186` | `entry_day` (already computed) |
| `mention_family/backtest.py:195` | `entry_day` (already computed) |
| `insider_judgment/backtest_judged.py:247` | `r["entry_day_iso"]` |
| `calibration_harvest/collect.py:192` | new `entry_day_iso` on the observation dict, computed at build time from `close_iso` and `days_to_close`, both in scope at `collect.py:160` |

`calibration_harvest` is the one that needs a new field rather than a
reference; it is a two-line change where the observation is assembled, and it
also makes that theory's entry day queryable, which it is not today.

## 6. Run-scoped scoring must not fan out

Once `decision_date` is real, one run can hold several attempts for one
position. The position-identity plan's run-scoped query joins on
`a.opportunity_id = o.id AND a.run_id = ?`, which then returns one row per
attempt and counts a single settlement several times — reintroducing, through
a different door, the double counting the whole design exists to end.

It is latent rather than active today only because no run currently records a
position on two decision days. `calibration_harvest` already has 6 rows at
`times_seen = 2`, so the shape exists.

Scoring joins **exactly one attempt per position per run** — the run's
earliest, which is the entry the theory would have taken when it first said
so, and which matches the rule the position row already follows (first
sighting owns the price, and never drifts):

```sql
LEFT JOIN (
    SELECT opportunity_id, run_id, entry_price, edge_pts_net
    FROM (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY opportunity_id, run_id
            ORDER BY decision_date, recorded_at
        ) AS rn
        FROM opportunity_attempts
    ) WHERE rn = 1
) a ON a.opportunity_id = o.id AND a.run_id = ?
```

Window functions are available (SQLite 3.42; they landed in 3.25). Applies
identically to `_single_leg_observations` and `_basket_observations`. The
regression test is direct: one position, two attempts in one run, one
settlement, `n == 1`.

## 7. What stays on the position row, and why

Not everything is per-attempt, and the exclusions are deliberate:

- **`interpretation`, `interpreted_at`, `disposition`.** `ledger.interpret`
  is stage-2 research keyed on `opportunity_id`; it judges the *position*, not
  one proposal of it, and has no run in scope. `disposition` still appears on
  the attempt because 371 legacy rows carry a real per-row value the migration
  must preserve; forward it records `'screened'`, the same value
  `record_opportunity` writes to the position row.
- **`user_action`, `user_size`, `user_reason`.** These are rollups of
  `opportunity_fills`, which is the money-side mirror of the attempt table.
  Already handled by the position-identity design.
- **`first_seen_at`, `screen_edge_pts_net`, `entry_price`.** First-sighting
  anchors. `entry_price` is *also* per-attempt, because the price series is
  the point; the position row's copy stays frozen so it never drifts.

## 8. Migration changes

Five corrections to `db.migrate_positions`, three of them defects rather than
enhancements:

**a. It must create `opportunity_fills`.** As specified it builds
`schema_statement("opportunities")` and `("opportunity_attempts")` only. The
live database has just `opportunities` and `opportunity_legs`, and Task 8's
guard makes `init_db` *refuse* a legacy database — so the fills table cannot
exist when the migration inserts the two taken rows. It raises `no such
table`. The plan's own `test_money_already_recorded_becomes_a_fill` fails for
the same reason. Add `schema_statement("opportunity_fills")`.

**b. Backfill the new attempt columns.** The pre-migration rows are in hand
while the migration runs, so populate every column in §4 from the row it came
from. One wider `INSERT`, no extra pass. This puts the 1,564 dropped
rationales and their `rules_diverge_from_title` features into
`opportunity_attempts` rather than leaving them only in a backup table nothing
queries.

**c. `judged_blind` travels with `confidence`.** The plan takes the label from
the latest attempt that carried one but leaves `judged_blind` on the earliest
row's value, so 1,564 positions would end up labelled `strong`/`moderate` with
a NULL blind flag. Both come from the same attempt.

**d. `user_action` and `user_size` are recomputed from the fills** rather than
copied from the earliest row. Today only 5 groups vary and none of them is a
take, but copying the earliest would let a later `taken` row become an
`untouched` position holding a fill.

**e. The Task 9 stop-condition is derived, not hard-coded.** The plan halts if
the dry run does not report `before: 9153, after: 7467, labels_preserved:
1564`. The database has grown since; it now reports **9,732 / 8,022 / 5,773**,
so Task 9 stops by its own rule and will keep going stale. Replace the literal
gate with an independently computed one: `before` must equal
`SELECT COUNT(*) FROM opportunities`, and `after` must equal the distinct
count over the new key computed by a separate query. Those hold at any size.

## 9. Consumers to repoint

Three queries move from the position row to the attempt. All three become
*more* correct, not merely compatible: a per-run analysis should read what
that run recorded.

| file | change |
|---|---|
| `insider_judgment/backtests/score_campaign.py:54-72` | `FROM opportunity_attempts a JOIN opportunities o ON o.id = a.opportunity_id`, filter `a.run_id LIKE ?`, read `a.extra_json`, `a.confidence`, `a.entry_price`, `a.run_id` |
| `insider_judgment/reprice_entry_window.py:66-79` | same shape |
| `insider_judgment/backtest_judged.py:108-115` | `WHERE a.run_id = SOURCE_RUN_ID`; works by luck today because fullcov happens to be the earliest run, and breaks the moment it is not |

Verification is exact: `score_campaign.load()` must return **1,561** rows
after the migration, the same count it returns today.

## 10. Testing

Beyond the position-identity plan's own suite:

- **Conventions:** every non-identity `record_opportunity` parameter has an
  `opportunity_attempts` column (§4).
- **Fidelity:** two runs propose one position with different `rationale` and
  different `extra_json`; both attempts retain their own values.
- **Backtest dating:** `run_mode="backtest"` without `decision_date` raises;
  a replay recording one ticker on three entry days under one `run_id`
  produces three attempts.
- **No fan-out:** that same position, settled, scores `n == 1` under
  `--run-id` (§6).
- **Migration:** new columns backfilled; `judged_blind` matches the attempt
  the `confidence` came from; `opportunity_fills` exists.
- **Consumers:** `score_campaign.load()` returns 1,561 rows post-migration.

## 11. Effect on the implementation plan

`docs/superpowers/plans/2026-08-27-position-identity.md` is amended, not
replaced:

| task | change |
|---|---|
| 1 | attempt table gains the §4 columns; add the conventions test |
| 2 | `_record_attempt` writes them; backtest requires `decision_date` |
| 3 | same for `record_basket` |
| 4 | replace the fan-out join with the §6 window-function join |
| 5–6 | unchanged |
| 7 | §8 a–d |
| 8 | unchanged |
| 9 | §8e derived stop-condition; refreshed expected figures |
| 10 | add §9 consumer repointing; add the 1,561-row verification |
| **new** | plumb `decision_date` through `theory.py` and the four callers (§5) |

No theory version bumps. This changes what the ledger stores and how a
backtest dates it — no theory's decision procedure moves.
