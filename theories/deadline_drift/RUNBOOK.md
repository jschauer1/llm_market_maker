# deadline_drift — run procedure

## Stages

| # | stage | who decides | artifact |
|---|---|---|---|
| 1 | settled capture top-up | code | `collect_settled` — time-critical, resumable; rebuilds `data/population_facts.json` when it finishes |
| 2 | hazard estimate | code | `python -m theories.deadline_drift.hazard` |
| 3 | screen + record | code | `THEORY.start(ctx).finish()` — records DD-1 observation rows |

No judgment stage. **Current version: 2 (`testing`).**

## The standing obligation: top up the settled capture

**This is the only thing in this theory that is time-critical, and missing
it is unrecoverable.** Kalshi archives settled markets out of its public
API roughly 60 days after close. Every allowlist market that settles and
is not captured within that window is gone from upstream permanently.

The population produces roughly **714 closes a year**, so each month of
capture is worth ~60 markets. The first estimate ran on 112 — the entire
fetchable history at the time, and the reason it could not reject zero.

```bash
python -m theories.deadline_drift.collect_settled
```

Incremental and resumable: it writes after every series and skips anything
already on disk, so an interrupted run costs seconds and a re-run is cheap.
About **130 fetches** — roughly 70 series walks plus candles for whatever
is new. Under a minute.

**When to run it.** Any session, whenever the marker is stale:

```python
from tools import db
from theories.deadline_drift.collect_settled import days_since_capture
d = days_since_capture(db.connect())      # None = never captured
```

**> 14 days (or `None`) means run it.** Two weeks is a quarter of the
archive window, so it leaves a wide margin — the check is deliberately
loose because the cost of running it needlessly is seconds and the cost of
skipping it is data that no longer exists.

Sessions die mid-task; a convention any session can execute outlives them,
which is why this is a marker in the database and a paragraph here rather
than a background job belonging to one session.

## Reproduce the hazard estimate

```bash
python -m theories.deadline_drift.hazard
```

Prints the estimate under both time anchors. The `actual close` row is
retained deliberately and is **wrong** — it is the contaminated view from
the 2026-08-29 correction, kept so the retraction is runnable rather than
merely asserted. Use `stated deadline`.

## Run the theory — this is what a floor does

Since v2 this theory is `testing`, so it runs in every floor and appears
on `floor checklist` alongside its sub-theory `dd2-one-off`.

```python
from datetime import datetime, timezone
from tools import board as bt, db
from theories.deadline_drift import THEORY
from tools.theory import TheoryContext

conn = db.connect()
ctx = TheoryContext.build(conn=conn, board=bt.get_board(conn),
                          now=datetime.now(timezone.utc))
res = THEORY.start(ctx).finish()      # records DD-1 observation rows
```

**Every row it writes claims edge 0 and is not a bet.** That is the
2026-08-30 observation-row ruling, and it is what lets this theory
collect DD-1's out-of-sample set without asserting an edge it has not
earned. `promote` refuses them by design ("no positive claimed edge —
observation/control row"), so **there is nothing here to report to the
user as a recommendation** and a floor report should say the theory ran,
how many rows it accrued, and nothing more.

**What to report each run:** rows recorded, the split by `recurring`
(DD-2's two arms), and the gate removals by category — a code gate drops
silently inside families it thinks it knows, so `ScanResult.gate_removed`
is reported every time.

## Run the screen directly

```python
from datetime import datetime, timezone
from tools import board as bt, db
from theories.deadline_drift import THEORY
from tools.theory import TheoryContext

conn = db.connect()
ctx = TheoryContext.build(conn=conn, board=bt.get_board(conn),
                          now=datetime.now(timezone.utc))
result = THEORY.screen(ctx)
```

`price()` emits observation rows while `data/hazard_bins.json` is absent,
and it is absent on purpose. **Do not create that file until DD-1
clears.** Writing it is what turns this theory from one that observes into
one that bets, and it also arms the `under_review` trigger — until then a
theory with zero settled *bettable* rows is unmeasured, not failing. See
THEORY.md's status section.

## Record

Rows go through the contract (`start(ctx).finish()`) like every mechanical
theory. Two things about them that are easy to get wrong:

- **Entry is the FIRST qualifying day, and that is part of the
  hypothesis.** Entering the first day inside the window measures +3.4 in
  sample; averaging over every qualifying day measures −1.7. The ledger
  enforces it for free — its dedup key preserves `entry_price` and
  `first_seen_at` from the first sighting — so re-running the screen daily
  is correct and does not corrupt the entry price. **Do not "refresh"
  entry prices.**
- **`extra_json` is written only at row creation.** A feature added after
  a row lands is missing from that row forever. Add fields before a run,
  or backfill the same day from the same board pull.

## Sub-theories

A **sub-theory** is a theory run over a *subset* of this theory's data --
a registered slice with its own evidence, gates and record, which may be
strong while the parent is flat.

**`dd2-one-off`** (registered 2026-09-01) -- DD-2, pre-registered in
THEORY.md before any out-of-sample data. Predicate
`{"outcome": ["no"], "extra": {"recurring": false}}`, where `recurring`
means the series has >= 3 settled events, a property fixed at listing
time. Mechanism: a recurring family teaches its own base rate, a one-off
question has no reference class on the board, so the premium should track
NON-RECURRENCE rather than subject matter.

Below its gates (>= 10 event clusters and >= 5 settlement days, out of
sample), so it is reported as accruing and changes no ranking yet. It
carries no `mined_from_run_ids` because the analysis that suggested it
wrote no ledger rows.

**Report it every run** -- `floor complete` refuses a report that omits a
registered sub-theory, and the guard exists because a floor report once
covered four theories carefully and never mentioned the best-evidenced
result in the repo.

Candidates NOT registered, deliberately: the `branch_family` and
`in_allowlist` subsets, and the fixed-k elimination shape. All three are
recorded as fields, so any of them can be registered later from settled
rows -- registering several slices at once on a theory with no
settlements would be multiple comparisons dressed as pre-registration.

## Report

Every session's floor reports `days_since_capture` — the capture is the
one time-critical item here, and > 14 days (or `None`) means it must run
before the session ends. Data missed past the ~60-day archive window is
gone upstream permanently.

## Skip

Nothing. The screen runs in every floor now that status is `testing`, and
the capture (stage 1) is never skipped when its marker is stale — cost is
seconds, the alternative is unrecoverable loss.

**Do not reach for `backtest-theory` on this theory without reading
THEORY.md's Status section first.** There is no clean replay available:
the population was chosen on the results of analysing the entire
fetchable history, so every settled market it can reach is in-sample for
that choice, and recording it as a tier A run would let the data that
suggested the population vouch for it.
