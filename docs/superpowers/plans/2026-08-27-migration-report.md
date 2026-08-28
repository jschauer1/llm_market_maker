# Migration report: position identity + attempt fidelity

**Ran:** 2026-08-28, against `db/market_edge.db`.
**Command:** `python -m tools.cli db migrate-positions` (dry run first, then applied).
**Spec:** `docs/superpowers/specs/2026-08-27-position-identity-design.md`,
amended by `docs/superpowers/specs/2026-08-27-attempt-fidelity-design.md`.
**Code:** `tools/db.py::migrate_positions`, merged to `master` at `12a898b`.

This is a one-time data migration. It is done; do not re-run it.
`has_legacy_position_key(conn)` now reads false, so `migrate_positions`
early-returns as a no-op on this database (by design — see spec §6 F2 in
`.superpowers/sdd/2026-08-27-position-identity/progress.md`).

## Backups

Two independent backups exist, taken seconds apart before the rebuild:

- **File copy:** `db/market_edge.db.bak-20260828194424` (untracked, 4.1 GB —
  do not commit it; it is data, not source).
- **In-database table:** `opportunities_premigration_20260828T234500` and
  `opportunities_premigration_20260828T234500_legs`, the exact pre-migration
  `opportunities` and `opportunity_legs` rows, verbatim (`CREATE TABLE ...
  AS SELECT *`). This is the one to query — see "Recovering a superseded
  value" below.

## What changed

`opportunities` was keyed on `(theory_id, theory_version, run_id,
kalshi_ticker, outcome)`. A bet re-proposed by a later run inserted a new
row instead of updating the existing one, so pooled scoring counted a
re-recorded bet as two independent observations and `times_seen` — the
counter that exists to record re-proposal — read 1 on every row. The
migration rekeys `opportunities` on `(theory_id, theory_version, run_mode,
lane, kalshi_ticker, outcome)`, moves every prior recording into a new
`opportunity_attempts` child table at full column parity (rationale,
extra_json and every other per-run field, not just the ones the position
row already tracked), and backfills `opportunity_fills` from the rows the
user had already marked `taken`.

## Counts (dry run and apply agreed; applied in 2.78s)

```
before 9948 -> after 8183 positions      attempts 9948 (none lost)
labels_preserved 5934                    fills_backfilled 2
legs_repointed 0                         takes_missing_size 0
superseded_interpretation_count 26       backup opportunities_premigration_20260828T234500
```

`before` is the row count `migrate_positions` read from `opportunities`
before rebuilding it; `after` is the number of distinct groups under the
new key, i.e. the surviving position count. Every one of the 9,948
pre-migration rows became an attempt — none were dropped, only collapsed
onto a shared position where the new key says they are the same bet.
`legs_repointed 0` and `takes_missing_size 0` mean neither of the two edge
cases the spec worried about (a merged basket's legs needing to move to
the surviving id; a `taken` row with no `user_size` that would abort the
fill backfill) fired on this database.

## Verification (re-run independently against the live database, not copied from the migration's own report)

```
opportunities rows            8183
opportunity_attempts rows     9948
labels (confidence NOT NULL)  5934
orphan legs                   0
orphan attempts               0
times_seen > 1                1764   (this counter had never left 1 before)
PRAGMA foreign_key_check      0 violations
PRAGMA integrity_check        ok
sqlite_sequence(opportunities) 10529  (max live id 10527, max backup id 10529)
opportunity_fills rows        2
```

The `sqlite_sequence` ceiling matters because the rebuild only re-inserts a
group's *surviving* id — a row that lost its dedup and was merged away
never lands in the new table again, so naively rebuilding AUTOINCREMENT
bookkeeping from what was actually re-inserted would land below the
highest id the table had ever handed out (10529, from the backup) and the
next real write would collide with an id the backup table already claimed.
`migrate_positions` restores the ceiling explicitly; confirmed above.

**Attempt fidelity** — the second spec's whole point, that no per-attempt
value (rationale, extra_json feature) is lost on a merge, not just
preserved in the backup:

```
distinct rationale    opportunity_attempts 702  == opportunities_premigration_...  702
distinct extra_json   opportunity_attempts 5680 == opportunities_premigration_... 5680
```

Both counts match the backup exactly — every distinct value that existed
pre-migration still exists somewhere in `opportunity_attempts` post-migration.

## Scores after the migration

```
insider_judgment v3 backtest pooled : n=3195  n_attempts=4759  cal_net=-1.1486
insider_judgment v3 backtest fullcov: n=3195  n_attempts=3195  cal_net=-1.1486
```

(`python -m tools.cli score report insider_judgment --version 3 --run-mode
backtest`, with and without `--run-id backtest-2026-08-25-insider-fullcov`;
re-run above, both agree with each other to the last displayed digit.)

Before the migration, pooled reported `n=4759, calibration_edge_net
-0.588`. The judged sub-runs (`backtest-2026-08-26-insider-judged-s200`,
`-s200b`, `-s57`) were drawn *from* the fullcov population and scored
better on that subset, so pooling re-counted those markets and pulled the
headline up — a duplicate improved measured performance. Pooled now equals
fullcov exactly, because the merge collapsed every duplicate; this is the
honest reading both specs call for, not a coincidence.

### Bucket rates, computable for the first time

The confidence labels (on the judged sub-runs) and the settlements
previously sat on different rows under the old run_id-keyed schema, so
`bucket_rates` over the merged backtest could not be computed at all before
this migration. Over the merged backtest (n=1,564, the judged population):

```
weak      n=770  win 0.858  entry 0.861   -0.29 pts gross
moderate  n=565  win 0.878  entry 0.853   +2.51 pts gross
strong    n=229  win 0.891  entry 0.851   +3.95 pts gross
```

Gross, not net; pre-cutoff tier B; **post-hoc on the data that suggested
it — a hypothesis, not a finding.** Pre-registered in the idea registry
(`confidence-bucket-gradient`, id 27) rather than acted on. See
`theories/insider_bias/insider_judgment/backtests/RESULTS.md` for the
full campaign statistics this reproduces exactly (Holm-Bonferroni family,
event-clustered t, bucket × side table) — `score_campaign.py`'s `load()`
reads `opportunity_attempts` directly and returns the same 1,561 rows it
returned before the migration; verified separately (see task report).

## The 26 superseded interpretations

The merge keeps the verdict from the **earliest attempt carrying an
interpretation**, so a later re-proposal of the same position at a
different price does not overwrite the verdict the money was taken on
(spec §4.4, amended 2026-08-28 during final review — see the spec and
`.superpowers/sdd/2026-08-27-position-identity/progress.md` for why
latest-wins was tried first and reversed). Every group where two or more
attempts carried an `interpretation` has exactly one verdict superseded;
`migrate_positions` names all of them (capped at 50 — all 26 fit) rather
than reporting a bare count, because a decision like this needs to stay
visible while it is still reversible.

Reconstructed read-only from `opportunities_premigration_20260828T234500`
by feeding its rows through the same grouping key and `tools.db._superseded`
that `migrate_positions` itself uses (that function is a no-op against the
live database now, since it detects the new key and returns early — this
runs its own logic, unmodified, against the backup rows directly). Sorted
money-holding positions first, as the migration's own report does.

**The two that hold money — called out explicitly, per the migration's own rule that a fill sorts first:**

| ticker | outcome | kept (money) | dropped (superseded) |
|---|---|---|---|
| `KXGROK-GROK47-26SEP04` | no | **endorsed**, entry 0.73, edge +4.52, run `live-2026-08-26-noscan`, decision day 2026-08-27 — **$25 taken 2026-08-27** | rejected, entry 0.77, edge +2.00, run `live-2026-08-28`, decision day 2026-08-28 |
| `KXGTATRAILER-26SEP` | no | **endorsed**, entry 0.75, edge +6.50, run `live-2026-08-26-noscan`, decision day 2026-08-27 — **$25 taken 2026-08-27** | rejected, entry 0.94, edge +2.00, run `live-2026-08-28`, decision day 2026-08-28 |

Both re-proposals on 2026-08-28 were judged at a materially worse ask than
the price the user is actually holding (0.77 vs 0.73; 0.94 vs 0.75) — a
verdict on a different price is not a revision of the one the money is on.
The later `rejected` verdict is not lost: it is on its own attempt row in
`opportunity_attempts` (queryable by `run_id = 'live-2026-08-28'`) and in
the backup table below.

**The full 26**, same kept/dropped shape, `has_fill` false except the two above:

| ticker | outcome | kept disposition | kept entry / edge | dropped disposition | dropped entry / edge |
|---|---|---|---|---|---|
| `KXBIGBROTHERELIMINATION-26AUG27-TAY` | no | endorsed | 0.65 / +4.52 | rejected | 0.96 / +2.00 |
| `KXGROK-GROK47-26SEP04` | no | endorsed | 0.73 / +4.52 | rejected | 0.77 / +2.00 |
| `KXGTATRAILER-26SEP` | no | endorsed | 0.75 / +6.50 | rejected | 0.94 / +2.00 |
| `KXNEWDRUGAPPLICATIONCMPS-360-26SEP01` | no | endorsed | 0.91 / +4.52 | rejected | 0.91 / +2.00 |
| `KXNEWDRUGAPPNTLA-LONV-26SEP01` | no | endorsed | 0.88 / +6.50 | rejected | 0.90 / +2.00 |
| `KXTRUMPMEET-26AUG-ABUR` | no | rejected | 0.89 / +6.50 | rejected | 0.89 / +2.00 |
| `KXTRUMPMEET-26AUG-VPUT` | no | rejected | 0.83 / +6.50 | rejected | 0.76 / +2.00 |
| `KXTRUMPMEET-26AUG-VZEL` | no | rejected | 0.76 / +6.50 | rejected | 0.78 / +2.00 |
| `KXTRUMPMEET-26AUG-XJIN` | no | rejected | 0.92 / +6.50 | rejected | 0.95 / +2.00 |
| `KXTRYFIRECOOK-27JAN01-26SEP01` | no | rejected | 0.83 / +4.52 | rejected | 0.86 / +2.00 |
| `KXADP-26AUG-T0` | yes | rejected | 0.87 / -3.90 | rejected | 0.83 / -3.90 |
| `KXB200WS-26SEP04-5.500` | yes | rejected | 0.89 / -3.90 | rejected | 0.87 / -3.90 |
| `KXBKNUGGETS-26SEP02-T3.48` | yes | rejected | 0.82 / -3.90 | rejected | 0.83 / -3.90 |
| `KXCBDISRAEL-26AUG31-HOLD` | yes | rejected | 0.80 / -3.90 | rejected | 0.86 / -3.90 |
| `KXCHIPBURRITO-26SEP02-T9.79` | yes | rejected | 0.88 / -3.90 | rejected | 0.88 / -3.90 |
| `KXCOPPERW-26AUG2817-T6.54` | yes | rejected | 0.83 / -3.90 | rejected | 0.84 / -3.90 |
| `KXGOLDMON-26AUG3117-T4491.99` | yes | rejected | 0.84 / -3.90 | rejected | 0.85 / -3.90 |
| `KXHORMUZWEEKLY-26AUG30-T25` | yes | rejected | 0.81 / -3.90 | rejected | 0.84 / -3.90 |
| `KXPAYROLLS-26AUG-T-25000` | yes | rejected | 0.86 / -3.90 | rejected | 0.86 / -3.90 |
| `KXRT-ONS-45` | yes | rejected | 0.86 / -3.90 | rejected | 0.86 / -3.90 |
| `KXT20MATCH-26AUG280800SANAM-SA` | yes | rejected | 0.83 / -3.90 | rejected | 0.84 / -3.90 |
| `KXTBCRUNCHWRAP-26SEP02-T6.70` | yes | rejected | 0.82 / -3.90 | rejected | 0.82 / -3.90 |
| `KXTOKENUSE-26AUG31-T112` | yes | rejected | 0.84 / -3.90 | rejected | 0.87 / -3.90 |
| `KXU3-26AUG-T4.0` | yes | rejected | 0.87 / -3.90 | rejected | 0.85 / -3.90 |
| `KXWNBAGAME-26AUG28PDXATL-ATL` | yes | rejected | 0.88 / -3.90 | rejected | 0.87 / -3.90 |
| `BASKET:875376849dbc917b` (structural_arb) | basket | rejected | 0.92 / +4.76 | rejected | 0.92 / +4.76 |

24 of the 26 are `rejected -> rejected` re-judgments where nothing about
the recorded disposition changed (the `no_side_premium` / `nsp` live scan
re-run a day later at slightly different asks, same verdict both times);
those cost nothing to have merged the "wrong" way. Only the five
`endorsed`-kept groups (including the two money rows) are cases where the
choice of "earliest interpreted" versus "latest interpreted" could have
changed the recorded disposition — and for all five, earliest is also
the better price (a later re-proposal was judged worse), so nothing here
is a case of the migration picking a stale verdict over a better one.

## Recovering a superseded value

Nothing here is destroyed. If a future session needs the dropped verdict,
the price it was judged against, or any other pre-migration column value:

```sql
SELECT * FROM opportunities_premigration_20260828T234500
WHERE kalshi_ticker = '<ticker>' AND outcome = '<outcome>';
```

returns every pre-migration row for that market, including the ones that
lost the merge. The equivalent attempt-level detail (which run recorded
which rationale/extra_json) is also live in `opportunity_attempts` — no
backup query needed for that half, since attempt fidelity means it was
never collapsed:

```sql
SELECT * FROM opportunity_attempts
WHERE opportunity_id = (SELECT id FROM opportunities WHERE kalshi_ticker = '<ticker>' AND outcome = '<outcome>');
```

The file backup (`db/market_edge.db.bak-20260828194424`) is the fallback
if the in-database backup tables are ever dropped; open it as a plain
SQLite file, independent of anything in the live database.
