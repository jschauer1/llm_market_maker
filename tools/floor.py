"""Floor duty — one session runs the daily floor, and the rest can tell.

`go`'s floor is the repo's one standing guarantee: every running theory
sees today's board through its complete procedure. It needs to happen
once a day, not once per session — four sessions collided on 2026-08-30
under a message-only protocol, and the defective duplicate run that came
out of it is still quarantined in the ledger because a DELETE needs the
user.

So the claim is a row, not a message. A session asks `status()` whether
the floor is due, `claim()` for the right to run it, and `complete()`
when the report has landed. Every session reaches the same answer from
the same table, including one that started while another was mid-run and
one that never received any peer's message at all.

Two clocks, and they answer different questions:

- **FLOOR_INTERVAL_HOURS** — how long a *completed* floor satisfies the
  requirement. The user's rule: nobody runs another one for 24 hours
  unless explicitly asked, and `force=True` is that asking.
- **CLAIM_LEASE_HOURS** — how long an *unfinished* claim blocks other
  sessions. Without it, a session that claims the floor and dies costs
  the repo a whole day of evidence, which is a worse failure than the
  duplicate run the claim exists to prevent. Past the lease the claim is
  taken over, and the abandoned row stays as the audit trail.

The lease is deliberately longer than a floor takes and far shorter than
the interval: a real floor is a board pull plus a settle run plus every
theory's runbook, which is minutes to a couple of hours with subagents,
so a claim still open after four is a dead session, not a slow one.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from tools.db import REPO_ROOT, utcnow, write

#: A completed floor satisfies the daily requirement for this long.
FLOOR_INTERVAL_HOURS = 24

#: An unfinished claim blocks other sessions for this long, then expires.
CLAIM_LEASE_HOURS = 4


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def _hours_between(earlier: str, later: str) -> float:
    return (_parse(later) - _parse(earlier)).total_seconds() / 3600.0


def _latest_completed(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM floor_runs WHERE completed_at IS NOT NULL"
        " ORDER BY completed_at DESC LIMIT 1"
    ).fetchone()


def _open_claim(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM floor_runs WHERE completed_at IS NULL"
        " ORDER BY claimed_at DESC LIMIT 1"
    ).fetchone()


def status(conn: sqlite3.Connection, now: str | None = None) -> dict:
    """Whether the floor is due, who holds it, and when it last landed.

    `due` is the whole answer a session needs: True means run it (after
    winning `claim`), False means somebody already did or is doing it.
    `reason` says which, in words meant for a report.
    """
    now = now or utcnow()
    done = _latest_completed(conn)
    held = _open_claim(conn)

    holder = None
    if held is not None:
        age = _hours_between(held["claimed_at"], now)
        if age < CLAIM_LEASE_HOURS:
            holder = held["session"]

    since = None if done is None else _hours_between(done["completed_at"], now)

    if holder is not None:
        due, reason = False, (
            f"claimed by {holder} at {held['claimed_at']} "
            f"({age:.1f}h ago, lease {CLAIM_LEASE_HOURS}h)"
        )
    elif since is not None and since < FLOOR_INTERVAL_HOURS:
        due, reason = False, (
            f"last completed {since:.1f} hours ago; next due in "
            f"{FLOOR_INTERVAL_HOURS - since:.1f} hours"
        )
    elif since is None:
        due, reason = True, "no floor has ever completed"
    else:
        due, reason = True, f"last completed {since:.1f} hours ago"

    if holder is None and held is not None:
        reason += (
            f" (claim by {held['session']} at {held['claimed_at']} "
            "expired unfinished)"
        )

    return {
        "due": due,
        "reason": reason,
        "holder": holder,
        "hours_since_completed": since,
        "last_completed_at": None if done is None else done["completed_at"],
        "last_completed_by": None if done is None else done["session"],
        "last_report_path": None if done is None else done["report_path"],
        "interval_hours": FLOOR_INTERVAL_HOURS,
        "lease_hours": CLAIM_LEASE_HOURS,
    }


def claim(
    conn: sqlite3.Connection,
    session: str,
    *,
    now: str | None = None,
    force: bool = False,
) -> sqlite3.Row | None:
    """Take floor duty, or return None if it is not this session's to take.

    None is a complete answer, not an error: the floor already ran, or
    another session is running it. The caller goes and does research
    instead. `force=True` is the user explicitly asking for a floor
    inside the interval; it still refuses to cut in on a live claim,
    because two sessions running the floor at once is the exact
    collision this table exists to prevent.
    """
    if not session or not session.strip():
        raise ValueError("a session name is required to claim floor duty")
    now = now or utcnow()
    with write(conn):
        # Re-read inside the transaction: two sessions starting together
        # must not both see an unclaimed floor. `write` opens BEGIN
        # IMMEDIATE, so the loser blocks here and then sees the winner's
        # row rather than an empty table.
        state = status(conn, now=now)
        if state["holder"] is not None:
            return None
        if not state["due"] and not force:
            return None
        cur = conn.execute(
            "INSERT INTO floor_runs (session, claimed_at, forced)"
            " VALUES (?, ?, ?)",
            (session, now, 1 if force else 0),
        )
        claim_id = cur.lastrowid
    return get(conn, claim_id)


def required_coverage(conn: sqlite3.Connection,
                      root=None) -> list[dict]:
    """Everything a floor report must account for.

    Theories, sub-theories, AND every study still in flight.

    A sub-theory is a theory run over a subset of another theory's data,
    and by this repo's definition it *is* a theory — its evidence is its
    own, it clears its own gates, and it can be strongly supported while
    the theory around it is flat. So the floor's work list is not the
    running theories; it is the running theories **and every registered
    sub-theory of them**.

    A RETIRED sub-theory stays on the list. Retirement must never hide a
    record, which is the whole reason a retired slice keeps reporting.

    An **unfinished study** is on the list for a different reason. The
    floor never re-runs a study -- doing that on a schedule is multiple
    comparisons by calendar -- but a study collecting against perishable
    data is losing rows *upstream* while it sits, since Kalshi ages
    settled markets out of its public API after ~60 days. That stall has
    happened twice and both times somebody noticed by accident. A
    COMPLETE study is not required: it needs no daily mention, and
    `cli studies` renders the whole set on demand.
    """
    from tools import slices as slices_mod, studies as studies_mod
    from tools import theories as theories_mod

    out: list[dict] = []
    for row in theories_mod.list_theories(conn, running_only=True):
        out.append({"kind": "theory", "name": row["id"], "theory": row["id"]})
        for s in slices_mod.list_slices(conn, row["id"]):
            out.append({
                "kind": "sub-theory",
                "name": s["slug"],
                "theory": row["id"],
                "status": s["status"],
            })
    for study in studies_mod.survey(root if root is not None else REPO_ROOT):
        if study["complete"]:
            continue
        out.append({
            "kind": "study",
            "name": study["slug"],
            "theory": None,
            "status": study["status"],
        })
    return out


def coverage_gaps(conn: sqlite3.Connection, report_text: str,
                  root=None) -> list[dict]:
    """What `required_coverage` names that the report never mentions.

    A name test, deliberately crude: it cannot tell a good line from a
    bad one, only a present name from an absent one. That is the failure
    worth catching mechanically — the 2026-09-01 floor reported all four
    theories carefully and simply never mentioned `strong-moderate-no`,
    the best-evidenced result in the repo.
    """
    text = (report_text or "").lower()
    return [c for c in required_coverage(conn, root=root)
            if c["name"].lower() not in text]


def complete(
    conn: sqlite3.Connection,
    claim_id: int,
    *,
    now: str | None = None,
    report_path: str | None = None,
    report_text: str | None = None,
    summary: str | None = None,
    root=None,
) -> sqlite3.Row:
    """Record that the floor ran and the report landed.

    This is what starts the 24-hour clock — claiming does not, because a
    claim is an intention and the guarantee is about work actually done.

    If a report is given (as `report_text`, or a readable `report_path`)
    it is **checked**: every running theory and every registered
    sub-theory must be named in it, or this refuses and says which are
    missing. Sub-theories were being dropped from reports while every
    theory was covered carefully, and a rule asking sessions to remember
    did not hold — so the omission is made impossible instead, the same
    way `record_opportunity` refuses a judged row with no provenance.

    Completing with no report at all still works: a blocked floor has to
    be able to close out, and this check must never become a reason not
    to write a report.
    """
    row = get(conn, claim_id)
    if row is None:
        raise KeyError(claim_id)
    if row["completed_at"] is not None:
        raise ValueError(
            f"floor run {claim_id} was already completed at "
            f"{row['completed_at']}"
        )
    text = report_text
    if text is None and report_path:
        candidate = Path(report_path)
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8")
    if text is not None:
        gaps = coverage_gaps(conn, text, root=root)
        if gaps:
            listed = ", ".join(
                f"{g['name']} ({g['kind']}"
                + (f" of {g['theory']}" if g["kind"] == "sub-theory" else "")
                + ")"
                for g in gaps
            )
            raise ValueError(
                "the floor report does not mention: " + listed +
                ". Every running theory and every registered sub-theory "
                "gets a line — a sub-theory's evidence is its own and can "
                "be strong while its parent is flat, so leaving one out "
                "hides exactly the result most worth reporting."
            )
    with write(conn):
        conn.execute(
            "UPDATE floor_runs SET completed_at = ?, report_path = ?,"
            " summary = ? WHERE id = ?",
            (now or utcnow(), report_path, summary, claim_id),
        )
    return get(conn, claim_id)


def get(conn: sqlite3.Connection, claim_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM floor_runs WHERE id = ?", (claim_id,)
    ).fetchone()


def recent(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    """The last few floor runs, newest first — completed and abandoned."""
    return conn.execute(
        "SELECT * FROM floor_runs ORDER BY claimed_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
