# Position identity: one position per theory version, however many runs saw it

**Date:** 2026-08-27. **Status:** design approved, implementation not started.
**Supersedes:** `docs/DEDUP_PLAN.md` — the diagnosis stands; §3.1 (Level 2),
§3.2 (ROI semantics), §3.3 (attempt shape) and §5 (migration rule) are revised
here.

---

## 1. The problem

`opportunities` is keyed `(theory_id, theory_version, run_id, kalshi_ticker,
outcome)`. Every run gets a fresh dated `run_id`, so the constraint enforces
"one row per market per **run**" where `tools/ledger.py`'s own docstring states
the intent as "one position per market per **theory version**".

Two consequences, one cause:

- Pooled scoring counts a re-recorded bet as an independent observation.
- `times_seen` — the counter that exists to record re-proposal — reads 1 on
  all 9,153 rows, because every repetition inserted a new row instead of
  incrementing the existing one.

## 2. Evidence

All figures reproduced against `db/market_edge.db` on 2026-08-27.

| segment | rows | distinct (ticker, side) | duplicates |
|---|---|---|---|
| insider_judgment v3 backtest | 4,759 | 3,195 | 1,564 |
| mention_family v1 backtest | 3,557 | 3,441 | 116 |
| mention_family v1 live | 40 | 35 | 5 |
| structural_arb v2 live | 2 | 1 | 1 |
| **total** | | | **1,686** |

The insider_judgment figure **excludes the 480-row
`exp/2026-08-26-insider-judged-gated100` run**; the raw table count for that
segment is 5,239. `DEDUP_PLAN.md` omits this qualifier, so a reader
reproducing its table gets a different number and distrusts the document.

Headline distortion:

- pooled (`score report` with no `--run-id`): `n=4,759, calibration_edge_net -0.588`
- full-coverage run alone: `n=3,195, calibration_edge_net -1.149`

The judged sub-runs were drawn *from* the fullcov population and scored better,
so pooling re-counted those markets and pulled the headline up. A duplicate
improved measured performance.

Other verified facts:

- `times_seen = 1` on 9,153 / 9,153 rows.
- `extra_json.entry_day_iso` present on 8,880 / 9,153; 273 need a fallback.
- 0 (ticker, side) pairs proposed by more than one `theory_id`; 104 by more
  than one theory *version*.
- `user_action`: 2 taken, 20 skipped, 9,131 untouched.
- The judged runs are **strict subsets** of fullcov (0 orphans) and
  **partition** it (0 overlap between them, 0 confidence disagreements).

## 3. Why the plan's migration rule had to change

`DEDUP_PLAN.md` §5 specifies "earliest decision survives as the row". Applied
to the real data:

```
backtest-2026-08-25-insider-fullcov      3195 rows   confidence = NULL
backtest-2026-08-26-insider-judged-s200   704 rows   weak/moderate/strong
backtest-2026-08-26-insider-judged-s200b  644 rows   weak/moderate/strong
backtest-2026-08-26-insider-judged-s57    216 rows   weak/moderate/strong
```

All 1,564 duplicate groups have the same shape: one earlier NULL-confidence
fullcov row plus one later confidence-labelled judged row. Earliest-wins keeps
the NULL one and **deletes every LLM confidence label in the backtest**.
`bucket_rates(run_mode='backtest')` would return empty afterward.

Coalescing instead — with zero conflicts to resolve, because the judged runs
partition fullcov — makes something computable that is impossible today, since
the labels and the settlements currently live on different rows:

```
merged backtest bucket rates, insider_judgment v3, n=1,564
  weak      n=770  win 0.858  entry 0.861   -0.29 pts gross
  moderate  n=565  win 0.878  entry 0.853   +2.51 pts gross
  strong    n=229  win 0.891  entry 0.851   +3.95 pts gross
```

Gross, not net; pre-cutoff tier; post-hoc. Not an edge to bet — a hypothesis
the merge makes visible, to be pre-registered rather than acted on.

## 4. Data model

### 4.1 `opportunities`

```sql
lane TEXT NOT NULL DEFAULT 'main',
UNIQUE (theory_id, theory_version, run_mode, lane, kalshi_ticker, outcome)
```

- `lane` = the full `run_id` when it starts with `exp/`, else `'main'`. Two
  experiments stay separate from each other and from the record they are
  measured against.
- `run_id` stays on the row as an attribute — which run first saw this — not
  as identity.
- `theory_id` and `theory_version` **stay in the key**. Two theories proposing
  one ticker are two forecasts and both get graded; two versions are two track
  records. CLAUDE.md requires this and it is not negotiable.
- The decision date is **not** in the key: proposed 8/26 and again 8/27 is one
  position with two attempts.

### 4.2 `opportunity_attempts` — every time the theory proposed it

Shaped after `opportunity_legs` (composite PK, cascade).

```sql
CREATE TABLE IF NOT EXISTS opportunity_attempts (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    decision_date  TEXT NOT NULL,        -- 'YYYY-MM-DD'
    run_id         TEXT NOT NULL,
    recorded_at    TEXT NOT NULL,
    entry_price    REAL NOT NULL,
    edge_pts_net   REAL NOT NULL,
    disposition    TEXT NOT NULL DEFAULT 'screened'
                   CHECK (disposition IN ('screened','endorsed','rejected')),
    confidence     TEXT,
    judged_blind   INTEGER,
    PRIMARY KEY (opportunity_id, decision_date, run_id)
);
CREATE INDEX IF NOT EXISTS idx_attempts_run ON opportunity_attempts(run_id);
```

Day granularity is deliberate: it collapses two recordings of one decision an
hour apart, and it is the unit the persistence signal is wanted in.
`attempt_dates` is derived (sorted distinct `decision_date`), never stored —
storing it beside the child table would be two places holding overlapping
truth.

Carrying the judgment fields per attempt is what resolves the collision in §3
with no tiebreak, keeps provenance traceable (`run_id` → `judgment_runs`), and
makes "did the theory change its mind about this market" a query.

### 4.3 `opportunity_fills` — every time the user acted on it

The mirror of attempts. There is no take-date field in the schema today at
all; this creates one.

```sql
CREATE TABLE IF NOT EXISTS opportunity_fills (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    filled_on      TEXT NOT NULL,       -- 'YYYY-MM-DD'
    size           REAL NOT NULL,
    price          REAL,                -- actually paid; NULL means the proposed ask
    reason         TEXT,
    recorded_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fills_opportunity ON opportunity_fills(opportunity_id);
```

No uniqueness on `(opportunity_id, filled_on)`: two buys on one day at two
prices are two real fills. Day-granularity collapse is right for attempts (two
recordings of one decision) and wrong for money.

### 4.4 The rollup rule

What the surviving position row holds:

| fields | taken from |
|---|---|
| `entry_price`, `edge_pts_net`, `spread_at_call`, `volume_at_call`, `run_id`, `scan_id`, `first_seen_at` | **earliest** attempt |
| `confidence`, `judged_blind`, `rationale` | **latest attempt carrying a judgment**, else earliest |
| `disposition`, `interpretation`, `interpreted_at` | **earliest attempt carrying an interpretation**, else earliest |
| `times_seen`, `last_seen_at` | `COUNT(attempts)`, `MAX(recorded_at)` |
| `user_action`, `user_size` | `'taken'` iff a fill exists; `SUM(fills.size)` |

"Earliest" and "latest" both order by `(decision_date, recorded_at)`. "Latest
attempt carrying a judgment" means the last attempt in that order whose
`confidence IS NOT NULL`; if no attempt carries one, the earliest attempt's
values stand.

**Amended 2026-08-28, during the final review of the implementation.** As
first written this row read "`disposition`, …, `interpretation`,
`interpreted_at` — latest attempt carrying a judgment", and `edge_pts_net`
travelled with them because `ledger.interpret` writes all four in one
statement. Measured against the real ledger that flipped nine positions from
`endorsed` to `rejected`, including **both** positions holding money: each was
endorsed on 8/26 at its ask and then declined on 8/28 at a *worse* ask, and a
re-proposal at a different price is a judgement of that price, not a revision
of the one the user is holding. It also put an `edge_pts_net` computed against
the later ask onto the earlier `entry_price` — the mismatched pair the
paragraph below forbids. So: research fields come from the earliest
*interpreted* attempt (earliest-interpreted, not simply earliest, so a group
first judged by a later pass keeps its verdict), and `edge_pts_net` never
leaves the earliest attempt. `migrate_positions` names every superseded
verdict, rather than counting them, so the call is visible while it is still
reversible.

Price and edge move together from one attempt, so they can never be a
mismatched pair — which is what keeps `_single_leg_observations` correct with
no change to its SELECT. Pooled scoring therefore becomes the fullcov screen
alone (`n=3,195, -1.15`), with the judged view reachable via `--run-id`.

## 5. Attribution

Taking a bet names the theory it is taken for.

```bash
python -m tools.cli opportunities mark-taken <id> taken \
    --theory insider_judgment --size 25 --reason "..."
```

- `--theory` required for `taken` (not for `skipped` — only money can be
  double-counted). It must match the row's `theory_id`; a mismatch raises
  naming both, which also catches grabbing the wrong id.
- If any other row for the same `(kalshi_ticker, outcome)` is already `taken`,
  raise and name the theory and id holding it. **One real position, one theory
  credited.** Two theories agreeing is two forecasts and one bet.
- `mark-taken` **appends a fill** rather than overwriting. Monday at 0.80 and
  Thursday at 0.90 are two rows, both kept.
- Unmark stays `mark-taken <id> untouched`, which already exists.

**`untouched` carries no negative connotation and never has.** Calibration
counts every settled row regardless of `user_action`; `user_action` feeds only
`roi_taken`. The 9,131 untouched rows are not declines — the user cannot take
9,131 bets. A theory's performance rests on what it *suggested*. Nothing is
stamped onto the rows of theories that were not named: `compare-theories`
filters divergence mining on `user_reason`, which is NULL on untouched rows,
so they are already excluded from that analysis and writing to them would only
inject noise. `skipped` remains different and meaningful — a deliberate no,
with a reason.

## 6. Migration

`python -m tools.cli db migrate-positions [--dry-run]`, run once, printing
before/after counts and a collapse summary. `init_db` detects the old key and
raises pointing at the command — it does **not** run automatically. Unlike
`_migrate_theories`, which is row-preserving, this one deletes 1,686 rows and
can only be verified after the fact.

1. `CREATE TABLE opportunities_premigration_<ts> AS SELECT * FROM opportunities`,
   and the same for `opportunity_legs`.
2. Decision date per row from `extra_json.entry_day_iso`, falling back to
   `date(first_seen_at)` for the 273 rows without it.
3. Group by the new key; every row in a group becomes an attempt; apply the
   §4.4 rollup.
4. **Repoint `opportunity_legs`** at the surviving `opportunity_id` before the
   losing rows go. `opportunity_legs` is `ON DELETE CASCADE`, so skipping this
   silently eats the losing basket's legs. `structural_arb` v2's
   `BASKET:875376849dbc917b` (ids 9310/9311) is a live instance.
5. Rebuild with the new constraint using the `_migrate_theories` pattern
   (`legacy_alter_table` on, foreign keys off, single transaction, rollback on
   any exception).
6. Backfill `opportunity_fills` from the 2 existing `taken` rows, dated
   `date(last_seen_at)`.

Expected: 9,153 → 7,467 rows, 1,564 confidence labels preserved, 0 legs
orphaned, 2 fills backfilled.

**Verification is independent:** the judged verdicts survive on disk at
`theories/insider_bias/insider_judgment/backtests/judged-*/` (62 files with
`row_index.json`), so a bad merge is recoverable without re-spending tokens.
The fullcov rows have no artifact folder and are irreplaceable — Kalshi
archives settled markets at ~60 days, so re-running that backtest may no
longer be possible. That asymmetry is why the migration preserves rather than
re-records.

## 7. API changes

**`tools/ledger.py`**

- `record_opportunity` gains keyword-only `decision_date: str | None = None`
  (defaults to the date part of `now`), computes `lane` from `run_id`,
  conflicts on the new key, inserts the attempt row. Its `is_new` return
  finally means something — today it is `True` on every new run.
- `record_basket` gets identical treatment. Its legs already
  `ON CONFLICT (opportunity_id, leg_index) DO UPDATE`, so a re-proposal
  updates them on the surviving position.
- New readers: `attempts(conn, id)`, `attempt_dates(conn, id)`, `fills(conn, id)`.
- `mark_user_action` implements §5.

All existing callers pass keyword arguments, including the in-flight
`theories/calibration_harvest/collect.py`, so the signature change is backward
compatible.

**`tools/score.py`**

- `_segment_filter`: `run_id NOT LIKE 'exp/%'` → `lane = 'main'`. More direct,
  and it stops depending on a merged row's `run_id` still carrying the prefix.
- The `--run-id` path joins `opportunity_attempts` and takes price and edge
  **from that attempt**. This is the only SELECT that changes.
- `_aggregate` gains `n_attempts` beside `n`, so the collapse is visible in
  the report rather than silent.
- `roi_taken` uses actual fill prices, size-weighted, falling back to the
  position's entry price where none was recorded. It currently uses the
  proposed ask for everything, which is not the user's money.
- `bucket_rates` counts positions, reading `confidence` from the rollup. One
  settlement is one draw — the same rule as calibration.

**`tools/db.py`** — `migrate_positions(conn)`; `init_db` raises on the old key.
**`tools/cli.py`** — `db migrate-positions`, `--theory` on `mark-taken`.

## 8. Testing

`tests/test_position_dedup.py` (15 tests, currently failing by design) is the
spec for identity, lanes, attempts and score invariance. Add:

- judgment coalescing: run 1 records no confidence, run 2 records `strong`;
  the position ends `strong` and both attempts are retained.
- basket dedup across runs with legs surviving on the merged position.
- cross-theory `mark-taken` raising, and `--theory` mismatch raising.
- multi-fill: two `mark-taken` calls append two fills; `user_size` is the sum;
  `roi_taken` uses the recorded prices.
- migration on a fixture DB reproducing the fullcov-plus-judged shape,
  asserting 0 labels lost and 0 legs orphaned.

`tests/test_score_characterization.py` may pin pooled numbers this work
**legitimately** changes. If one breaks, surface the before/after and get a
ruling — do not re-baseline it silently.

## 9. Known limitations and out of scope

- **`roi_all` changes meaning.** Pooled scoring reads the position's
  `entry_price`, which after the merge is first-sighting only. Arguably more
  correct, but it is an unannounced change to a headline metric.
  `tests/test_position_dedup.py::test_a_duplicate_recording_does_not_change_the_score`
  already pins this behaviour, which is why ROI counts positions rather than
  entries — contradicting `DEDUP_PLAN.md` §3.2.
- **`interpretation_value` semantics.** Under §4.4, `disposition` comes from
  the latest judged attempt while price and edge come from the earliest, so
  `compute_score(disposition='endorsed')` scores the endorsed set at
  first-sighting prices. Read the judged view with `--run-id`. Currently
  vacuous — `disposition` is uniformly `screened` across all real data.
- **Level 2 `bets` table: cut.** With `--theory` exclusivity and
  `opportunity_fills`, a theory-less position row and a `proposed_by` column
  add nothing — "which other theories saw this" is a one-line query against
  `opportunities`. Revisit only if a theory-less view of the portfolio is
  actually needed.
- **Concurrent sessions break loudly.** After migration, old code's
  `ON CONFLICT (theory_id, theory_version, run_id, kalshi_ticker, outcome)`
  no longer matches a unique constraint and SQLite raises. Loud is correct,
  but any session running pre-migration code must be restarted. There are
  uncommitted changes in `theories/calibration_harvest/` at time of writing.
- **`bucket_rates` duplicate rows are harmless.** The table is write-only
  audit history; `tools/buckets.py` takes rates as a dict from
  `score.bucket_rates()` and nothing reads the table back. Out of scope.

## 10. Caveats that must survive

- **Deduping fixes the arithmetic of the pooled backtest number. It does not
  make that number meaningful.** fullcov and the judged subsets sample
  different populations. After the fix the pooled figure *becomes* the fullcov
  figure, which is the honest reading — but that is because the judged runs
  are strict subsets, not because pooling became valid.
- **No theory version bumps.** Nothing here changes any theory's decision
  procedure, only how the ledger counts. Per CLAUDE.md, versions bump on
  procedure changes; this is not one.
- **Theory write-ups go stale.** `RESULTS.md` / `NOTES.md` in theory folders
  quote pre-fix numbers. Annotate with corrected figures rather than leaving
  them silently wrong.
- **The confidence gradient in §3 is a hypothesis, not a finding.** It was
  surfaced post-hoc on the same data that suggested it. Pre-register it in the
  idea registry for a forward test; do not bet it on that data.
