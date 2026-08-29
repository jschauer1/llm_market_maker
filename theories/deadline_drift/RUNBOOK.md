# deadline_drift — run procedure

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

## Run the screen

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

`price()` returns nothing while `data/hazard_bins.json` is absent, and it
is absent on purpose: the theory is `proposed`, the corrected estimate rests
on **3 YES outcomes**, and wiring that into live pricing would manufacture
bets out of noise. Do not create that file until the capture has run long
enough for a cell to carry a defensible `n` — see THEORY.md's status
section for what promotion requires.
