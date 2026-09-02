"""Where the repo's long-running collections are, and whether they moved.

**The problem this exists for.** A collector here is a multi-hour,
resumable, per-series-atomic walk against *perishable* upstream data —
Kalshi ages settled markets out of its public API ~60 days after close. The
job outlives the session that starts it by design, so the failure mode is
structural rather than careless: whoever launches it cannot finish it, and
the next session only learns it stopped by running the study's own `status`
subcommand and comparing counts, which nothing prompts anyone to do.

Measured cost, 2026-09-01: the series-bias liquidity backfill stalled at
213/647 series and sat dead for **5.7 hours** before a session noticed by
hand — the second time that had happened. The first aged-out rows appeared
during the restarted run, so by then every stall was permanent loss rather
than delay.

`cli state` already answers "is the board stale, is the floor due". It said
nothing about a collection, which is why this module feeds a `COLLECTIONS`
block into the same panel.

**Why a registry rather than a general mechanism.** Collection state lives
in each study's own SQLite file, in that study's own schema. There is no
repo-wide table to read, and inventing one would mean migrating collectors
that work. Two entries today; add a row when a new long walk ships.

**This module only ever reads, and never authoritatively.** It opens each
database read-only and degrades to a status rather than raising: the file
may be missing, may predate the phase, or may be locked by the very walk it
is reporting on. `cli state` is run by every session, so a collector
holding its own file must never be able to break orientation.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

#: A phase that wrote within this many minutes is treated as live. Chosen
#: against the observed 1.6 series/min: a healthy walk writes far inside
#: it, and a walk that is merely slow because peers are sharing Kalshi's
#: limiter still clears it.
RUNNING_WITHIN_MINUTES = 10.0


@dataclass(frozen=True)
class Collection:
    """One long-running collection: where its progress lives, and how to
    resume it."""

    name: str
    db: Path
    phase: str
    unit: str
    command: str
    #: Optional query returning the count of units still needing work, used
    #: only to distinguish COMPLETE from IDLE. Optional because
    #: completeness is study-specific: `backfill` can express it, `prices`
    #: cannot without duplicating the collector's own eligibility rule in
    #: `tools/`, and a duplicated rule drifts. No query means no claim.
    remaining_sql: str | None = None


@dataclass(frozen=True)
class Status:
    collection: Collection
    done: int
    last_write: str | None
    age_hours: float | None
    state: str  # RUNNING | COMPLETE | IDLE | ABSENT | UNREADABLE
    remaining: int | None = None


#: The known long-running collections. Both phases of the series-bias
#: collector; `prices` walks unpriced series, `backfill` re-prices the
#: pre-3cc5317 rows that read NULL liquidity fields.
_SERIES_BIAS = Path("studies/2026-08-29-series-bias-mining")

REGISTRY: tuple[Collection, ...] = (
    Collection(
        name="series-bias prices",
        db=_SERIES_BIAS / "data" / "collect.db",
        phase="prices",
        unit="series",
        command=f"python {_SERIES_BIAS.as_posix()}/collect.py prices",
    ),
    Collection(
        name="series-bias backfill",
        db=_SERIES_BIAS / "data" / "collect.db",
        phase="backfill",
        unit="series",
        command=f"python {_SERIES_BIAS.as_posix()}/collect.py backfill",
        # A series whose spread is still NULL *after* its own backfill ran
        # had its candles age out upstream -- that is loss, not work left.
        # Only a NULL-carrying series never attempted is remaining work.
        remaining_sql=(
            "SELECT COUNT(DISTINCT series_ticker) FROM obs"
            " WHERE spread IS NULL AND series_ticker NOT IN"
            " (SELECT key FROM progress WHERE phase = 'backfill')"
        ),
    ),
)


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def read(collection: Collection, now: str) -> Status:
    """Progress for one collection, never raising.

    A phase with no rows is IDLE with `last_write` None rather than ABSENT:
    the database exists and the phase simply has not started, which is a
    different fact from "this collector has never run at all".
    """
    path = Path(collection.db)
    if not path.exists():
        return Status(collection, 0, None, None, "ABSENT")

    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True,
                               timeout=1.0)
        try:
            row = conn.execute(
                "SELECT COUNT(*), MAX(done_at) FROM progress WHERE phase = ?",
                (collection.phase,),
            ).fetchone()
            remaining = None
            if collection.remaining_sql:
                try:
                    got = conn.execute(collection.remaining_sql).fetchone()
                    remaining = int(got[0]) if got and got[0] is not None else None
                except sqlite3.Error:
                    # An unanswerable query claims nothing. Silently
                    # reporting COMPLETE here would retire a live
                    # collection, which is the expensive direction.
                    remaining = None
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        # "no such table" means the file predates this phase; anything else
        # (classically "database is locked") means the walk holds it.
        if "no such table" in str(exc):
            return Status(collection, 0, None, None, "ABSENT")
        return Status(collection, 0, None, None, "UNREADABLE")
    except sqlite3.Error:
        return Status(collection, 0, None, None, "UNREADABLE")

    done, last_write = (row or (0, None))
    done = done or 0
    if not last_write:
        return Status(collection, done, None, None, "IDLE", remaining)

    age_hours = max(
        0.0, (_parse(now) - _parse(last_write)).total_seconds() / 3600.0
    )
    if age_hours * 60.0 <= RUNNING_WITHIN_MINUTES:
        state = "RUNNING"
    elif remaining == 0:
        state = "COMPLETE"
    else:
        state = "IDLE"
    return Status(collection, done, last_write, age_hours, state, remaining)


def statuses(now: str, registry=None) -> list[Status]:
    return [read(c, now) for c in (registry or REGISTRY)]


def render(registry, now: str) -> list[str]:
    """Lines for `cli state`'s FRESHNESS panel.

    IDLE is deliberately not called STALLED, and it is the only state that
    prints a resume hint. A phase that can prove it has no work left reads
    COMPLETE and stays quiet; one that cannot prove it either way reports
    its age and lets the reader judge, which is what the 5.7-hour hole
    actually needed. Nagging a session to restart a finished walk would be
    the same defect pointed the other way.
    """
    lines = []
    for st in statuses(now, registry):
        c = st.collection
        if st.state == "ABSENT":
            lines.append(f"    {c.name:<22} (no data yet)")
            continue
        if st.state == "UNREADABLE":
            lines.append(
                f"    {c.name:<22} (database busy — a walk is probably holding it)"
            )
            continue
        age = f"{st.age_hours:.1f}h ago" if st.age_hours is not None else "never"
        left = f", {st.remaining} left" if st.remaining else ""
        line = (
            f"    {c.name:<22} {st.done} {c.unit} done{left},"
            f" last write {age}  {st.state}"
        )
        if st.state == "IDLE":
            line += f"\n      {'':<20} resume: {c.command}"
        lines.append(line)
    return lines
