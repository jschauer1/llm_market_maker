# Handoff: position identity, deduplication, and the persistence signal

**Session:** 2026-08-27. **Status:** diagnosed and designed; tests written and
failing by design; **implementation not started.**

---

## 1. The question that started it

> "If I have two suggested markets and they are the same, in terms of
> performance that should not improve performance relative to just having the
> suggested market once — unless it was settled and now we're looking at
> something similar."

Correct, and it was not holding. What follows is what the database actually
showed.

---

## 2. What we learned

### 2.1 The UNIQUE key is scoped one level too narrow

`opportunities` was keyed:

```sql
UNIQUE (theory_id, theory_version, run_id, kalshi_ticker, outcome)
```

`run_id` is in that key and **every run gets a fresh dated id**
(`live-2026-08-23`, `backtest-2026-08-25-insider-fullcov`, ...). So the
constraint enforces *"one row per market per **run**"* where the intent —
stated in `tools/ledger.py`'s own docstring — is *"one position per market per
**theory version**"*:

> "Re-sighting the same thesis updates the existing row rather than inserting
> a new one. A market that stays mispriced for a week is one bet seen seven
> times, not seven bets."

Worked example from the live DB — four of five key columns identical, so the
constraint never fires:

| | row A | row B |
|---|---|---|
| theory_id | insider_judgment | insider_judgment |
| theory_version | 3 | 3 |
| kalshi_ticker | KX1ALBUM-26DEC-FUT | KX1ALBUM-26DEC-FUT |
| outcome | yes | yes |
| **run_id** | **backtest-2026-08-25-insider-fullcov** | **backtest-2026-08-26-insider-judged-s200b** |
| entry_price | 0.94 | 0.94 |
| times_seen | 1 | 1 |

### 2.2 It corrupts scoring

`compute_score` pools every run of a theory+version+run_mode when no
`--run-id` is passed ([tools/score.py:85](../tools/score.py#L85)), so each
re-recording became an independent observation.

| segment | rows | distinct (ticker, side) | duplicates |
|---|---|---|---|
| insider_judgment v3 backtest | 4,759 | 3,195 | **1,564** |
| mention_family v1 backtest | 3,557 | 3,441 | 116 |
| mention_family v1 live | 40 | 35 | 5 |
| structural_arb v2 live | 2 | 1 | 1 |
| **total** | | | **1,686** |

Headline distortion, insider_judgment v3 backtest:

- **pooled** (what `score report` prints with no `--run-id`): `n=4,759, calibration_edge_net -0.59`
- **full-coverage run alone**: `n=3,195, calibration_edge_net -1.15`

The judged sub-runs (`s200`, `s200b`, `s57`) were drawn *from* the fullcov
population and scored better, so pooling re-counted those same markets and
pulled the headline up. **A duplicate improved measured performance** — the
exact failure the user described.

Downstream blast radius:

- `bucket_rates` pools identically, so the realized win rates
  `tools/buckets.py` converts into betting probabilities are computed over
  duplicated rows.
- `rank.credibility(n, ...)` takes `n` directly, so inflated n raises
  credibility via `n/(n+20)`.
- `settlement_day_clusters` inherits both.

### 2.3 The same defect silently destroyed the persistence signal

```
times_seen distribution across all 9,153 rows:
   times_seen = 1 : 9153      <- every row
```

`times_seen` exists to count re-proposal. **It has never incremented, once.**
Not because nothing repeated — 1,686 positions demonstrably repeated — but
because each repetition inserted a *new row* instead of incrementing the
counter on the existing one.

**This is the key insight of the session.** The bug and the lost signal are
one defect seen from two sides: every repetition was simultaneously
(a) fabricated into an extra bet that moved the score, and (b) erased as
evidence that the theory kept proposing it. Fixing the key fixes both.

### 2.4 The decision date already exists in the data

`extra_json` carries `entry_day_iso` / `entry_day_ts` — the as-of day of the
decision. Coverage **8,880 / 9,153**. It is distinct from `first_seen_at`,
which is wall-clock *recording* time and is useless for this (all 1,564
duplicate pairs differ on it, because the two runs ran an hour apart).

Checked across all 1,564 insider_judgment duplicate groups:

```
SAME entry_day_iso      : 1564   <- same decision, recorded twice
DIFFERENT entry_day_iso : 0      <- genuine re-entry on another day
```

So no heuristic on price equality is needed — decision identity is a fact the
theory already recorded.

### 2.5 There are currently zero multi-day re-decisions

**Correction made mid-session:** 19 live `insider_judgment` positions appearing
across runs looked like genuine "proposed Monday, still there Thursday." They
are not — grouping without `theory_version` hid that they are v2
(`live-2026-08-23`) vs v3 (`live-2026-08-26-noscan`). Different versions are
deliberately separate track records.

Regrouped correctly, **all 1,686 duplicates are same-day re-recordings.** The
closest thing to a real repeat is structural_arb's basket
`875376849dbc917b`, recorded 12:02 and 23:34 on 8/27 — same day, same 0.92.

Consequence: the merge is provably lossless as to decisions, and the
attempt-date list starts empty of real multi-day entries and accumulates
going forward. **The fix is corrective for the double-count and preventive
for the persistence signal** — which is the right time to build it, before
more is lost.

### 2.6 Cross-theory and cross-version overlap

- **0** (ticker, side) pairs proposed by more than one `theory_id`.
- **104** proposed by more than one theory *version* (insider_judgment v2/v3,
  structural_arb v1/v2).
- `user_action`: 2 taken, 20 skipped, 9,131 untouched.

### 2.7 Database layout (asked directly)

**One shared SQLite file**, `db/market_edge.db`, 11 tables. Theories are
separated by a `theory_id` **column**, not by separate databases or tables.

```
opportunities     9,153      theory_id: YES     <- all theories, one table
backtest_runs         8      theory_id: YES
bucket_rates          5      theory_id: YES
judgment_runs        19      theory_id: YES
theory_facts      1,809      theory_id: YES
ideas                26      theory_id: YES
scores                0      theory_id: YES

market_snapshots  1,051,326  theory_id: no      <- shared board cache
settlements           6,700  theory_id: no      <- how markets resolved
theories                  5  theory_id: no      <- the registry
opportunity_legs          8  theory_id: no      <- hangs off opportunities
```

That split matters: `settlements` is global and keyed by ticker — correct,
a market resolves once no matter how many theories bet on it. `opportunities`
is per-theory, so two theories proposing one ticker are two *forecasts*.

---

## 3. The design

### 3.1 Two levels, because two different things are being counted

Conflating a **proposal** with a **bet** is what makes "duplicate" ambiguous.

**Level 1 — Proposal.** "insider_judgment v3 says buy KXFOO yes."
Key: `(theory_id, theory_version, run_mode, lane, kalshi_ticker, outcome)`.
**Scored for calibration.**

- `run_id` moves from identity to **attribute** — it stops saying *which
  position this is* and starts saying *which run made this attempt*. Without
  this the date list fragments exactly as the rows do now.
- `lane` = `run_id` when it starts with `exp/`, else `'main'`. Keeps
  experiments quarantined; without it an `exp/` attempt merges into the
  record it is meant to be measured against.
- `theory_id` / `theory_version` **stay**. Deduping across theories here would
  destroy the per-theory track record the repo exists to build. Two theories
  proposing one ticker are two forecasts and both get graded.
- **The decision date is NOT in the key.** A bet proposed 8/26 and again 8/27
  is ONE position carrying `["2026-08-26", "2026-08-27"]`.

**Level 2 — Bet.** "I hold KXFOO yes, 50 contracts at 0.94, entered 8/27."
Key: `(kalshi_ticker, outcome)` — **no theory_id, no version**. One row per
actual position in the world. **Scored for money.** Carries `proposed_by`
(every theory+version that pointed at it — cross-theory agreement becomes
data rather than prose in find-edge section 4) and `fills` (a list).

This is what makes the user's rule work: **a bet taken once is counted once,
however many theories proposed it**, while every theory that proposed it stays
separately gradable. It also subsumes the `mark_user_action` defect (section 6).

### 3.2 Counting rule

- **Calibration counts positions.** Two entries into one market share one
  settlement; one outcome cannot be two independent draws. Existing precedent:
  riskless baskets are kept out of `calibration_edge` for the same reason, and
  `settlement_day_clusters` already corrects a weaker form of this.
- **ROI may count entries**, since separate entries at separate prices are
  separate money.

### 3.3 Attempts are a child table, not a JSON column

**Revised during the session.** The point of preserving repetition is to make
persistence a dimension you can *slice by*; a JSON blob is where that signal
goes to become unqueryable. `opportunity_legs` is already exactly this shape —
a child table hanging off `opportunities` for per-item facts — so
`opportunity_attempts` matches existing precedent.

```sql
CREATE TABLE opportunity_attempts (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    decision_date  TEXT NOT NULL,       -- 'YYYY-MM-DD'
    run_id         TEXT NOT NULL,
    entry_price    REAL NOT NULL,
    recorded_at    TEXT NOT NULL,
    UNIQUE (opportunity_id, decision_date, run_id)
);
```

`attempt_dates` is **derived** (sorted distinct `decision_date`), not a stored
column — storing it beside the child table would be two places holding
overlapping truth with drift risk. `len(attempt_dates)` is the persistence
signal, measurable for the first time.

Day granularity, not timestamp: it is what makes two recordings of one
decision an hour apart collapse, and it matches the unit the signal is wanted
in.

---

## 4. What is built

- **`docs/DEDUP_PLAN.md`** — this document.
- **`tests/test_position_dedup.py`** — 15 tests, **all failing by design**
  (implementation not started). They pin: one position across runs; lane
  isolation for `exp/`; version/theory/side/mode separation; the attempt list
  and its dates; first-sighting keeping `entry_price`; and the core
  requirement — *a duplicate recording must not move `n`, `calibration_edge`,
  or `roi_all`*, and a repeated winner cannot book two wins.

- **`RESEARCH_LOG.md`** — an entry pointing here.

Nothing in `tools/`, `db/`, or `theories/` is modified by this work.

**Concurrent session warning.** Another session was working this repo at the
same time and landed two commits mid-way through (`aacd5d2` settlement-day
clustering study, `f35948d` calibration_harvest v1), and left uncommitted
changes to `theories/calibration_harvest/collect.py` and its test still in
flight. Those are **not** part of this work — do not fold them into a commit
here. Re-check `git log` before starting: the schema and migration steps below
touch `tools/db.py` and `db/schema.sql`, which any concurrent theory work may
also be reading.

---

## 5. What to do next

1. **Schema** (`db/schema.sql`): add `lane` to `opportunities`, change its
   UNIQUE to the level-1 key, add `opportunity_attempts`.
2. **Migration** (`tools/db.py`), using the table-rebuild pattern
   `_migrate_theories` already uses — SQLite cannot alter a UNIQUE in place:
   - copy `opportunities` to `opportunities_premigration_<ts>` in the same DB;
   - derive each row's decision date from `extra_json.entry_day_iso`, falling
     back to `first_seen_at`;
   - group by the new key; earliest decision survives as the row; all rows in
     the group become its attempts; set `times_seen` to the attempt count;
   - rebuild with the new constraint. Expect **9,153 to ~7,467 rows**.
3. **`tools/ledger.py`**: `record_opportunity` gains `decision_date`
   (defaults to the date part of `now`), computes `lane` from `run_id`,
   `ON CONFLICT` on the new key, inserts the attempt row. Add
   `attempts(conn, id)` and `attempt_dates(conn, id)`.
4. **`tools/score.py`**: `--run-id` filtering moves to attempts (a position is
   in run X if any attempt names X, priced at that attempt); add `n_attempts`
   beside `n` so the collapse is visible in the report.
5. **Full suite** — 707 passing at session start; keep them green.
6. **Level 2** (`bets` table + `mark_user_action` to fills) as a separate commit.

---

## 6. Known defect, deliberately not yet fixed

`mark_user_action` ([tools/ledger.py:759](../tools/ledger.py#L759)) sets
`user_action`/`user_size`/`user_reason` on a single row and **overwrites**, so
"I took this bet today and yesterday" is not representable — the second mark
clobbers the first and `roi_taken` sees one position at the last size passed.
Level 2 fixes this by making fills a list.

---

## 7. Caveats that must survive this handoff

- **Deduping fixes the arithmetic of the pooled backtest number. It does not
  make that number meaningful.** `backtest-2026-08-25-insider-fullcov` (full
  coverage) and `backtest-2026-08-26-insider-judged-s200` (a judged subset of
  it) sample different populations. After this fix the honest reading of
  insider_judgment v3 remains **the fullcov run alone at -1.15**, not a pooled
  figure. The fix stops the pooled number being *inflated*; it does not make it
  the number to quote.
- **No theory version bumps.** Nothing here changes any theory's decision
  procedure — only how the ledger counts. Per CLAUDE.md, versions bump on
  procedure changes; this is not one.
- **Theory write-ups go stale.** `RESULTS.md` / `NOTES.md` in theory folders
  quote the pre-fix numbers (insider_judgment's especially). Annotate them with
  corrected figures rather than leaving them silently wrong.
- The user's note on scope: *"don't worry too much about the old data, we've
  only been collecting data a couple days."*
