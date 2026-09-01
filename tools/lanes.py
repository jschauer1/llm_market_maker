"""Lane claims — who is working on what, visible but not locked.

`go` gives a session five lanes and asks it to pick one and stay in it.
This records the choice so every other session can see it: a peer
choosing its own lane can tell that maintenance is covered and go find
something else, without anyone having to send a message about it.

**A lane is not the floor.** The floor must happen exactly once a day, so
`tools/floor.py` locks it and refuses a second holder. A lane claim is
advisory. Two sessions on maintenance is wasteful rather than harmful,
and a session that judges the work important enough may join a lane
already held (user ruling 2026-08-31). Joining is discouraged and never
blocked: what keeps it rare is having to write down why, not being told
no. `LaneHeld` names the current holder so a refused session knows both
who to talk to and that it could join if it really means to.

The theory lane carries a `focus` — which theory. Two sessions on that
lane are only colliding if they picked the same one, and treating the
lane itself as exclusive would stop the most obviously parallel work in
the repo.
"""

from __future__ import annotations

import sqlite3

from tools.db import utcnow, write

#: The lanes `go` dispatches to. `floor` is here so the board of who-is-
#: doing-what is complete, but the floor's own exclusivity lives in
#: `tools/floor.py` -- claiming the floor lane does not substitute for
#: `floor.claim`, which is what actually enforces once-a-day.
LANES = ("floor", "theory", "new-theory", "find-theories", "maintenance")

#: How long a lane claim stands before it is treated as abandoned. Longer
#: than the floor's, because a research lane is a whole session's work
#: rather than a fixed procedure.
LEASE_HOURS = 6


class LaneHeld(Exception):
    """Raised when a lane is already held and `join` was not given."""


def _parse(stamp: str):
    from datetime import datetime

    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def _hours(earlier: str, later: str) -> float:
    return (_parse(later) - _parse(earlier)).total_seconds() / 3600.0


def _live(conn: sqlite3.Connection, now: str) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM lane_claims WHERE released_at IS NULL"
        " ORDER BY claimed_at"
    ).fetchall()
    return [r for r in rows if _hours(r["claimed_at"], now) < LEASE_HOURS]


def status(conn: sqlite3.Connection, now: str | None = None) -> dict:
    """Every lane, and who currently holds it."""
    now = now or utcnow()
    out = {
        lane: {"holders": [], "focus": [], "claims": []} for lane in LANES
    }
    for row in _live(conn, now):
        entry = out[row["lane"]]
        entry["holders"].append(row["session"])
        if row["focus"]:
            entry["focus"].append(row["focus"])
        entry["claims"].append(dict(row))
    return out


def claim(
    conn: sqlite3.Connection,
    lane: str,
    session: str,
    *,
    focus: str | None = None,
    join: str | None = None,
    now: str | None = None,
) -> sqlite3.Row:
    """Take a lane. Raises `LaneHeld` if someone has it and `join` is not set.

    `focus` narrows the claim — the theory being worked, for the theory
    lane. Two sessions on the theory lane with different focuses are not
    colliding, so only a matching focus counts as held.

    `join` is the deliberate override: a non-empty reason, recorded. It
    exists because a session may judge work important enough to double up
    on, and refusing outright would make the tool wrong rather than the
    behaviour rare.
    """
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {LANES}")
    if not session or not session.strip():
        raise ValueError("a session name is required to claim a lane")
    if join is not None and not join.strip():
        raise ValueError(
            "joining a held lane needs a reason: say why this work is worth "
            "two sessions. If you cannot, take an open lane instead"
        )
    now = now or utcnow()
    with write(conn):
        held = [
            r for r in _live(conn, now)
            if r["lane"] == lane and (r["focus"] or None) == (focus or None)
            and r["session"] != session
        ]
        if held and join is None:
            who = ", ".join(r["session"] for r in held)
            raise LaneHeld(
                f"lane {lane!r}"
                + (f" (focus {focus!r})" if focus else "")
                + f" is held by {who}. Take an open lane, or pass a join "
                "reason if this genuinely wants two sessions"
            )
        cur = conn.execute(
            "INSERT INTO lane_claims"
            " (lane, session, focus, claimed_at, joined, join_reason)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (lane, session, focus, now, 1 if held else 0,
             join.strip() if held and join else None),
        )
        claim_id = cur.lastrowid
    return get(conn, claim_id)


def release(
    conn: sqlite3.Connection,
    claim_id: int,
    *,
    summary: str | None = None,
    now: str | None = None,
) -> sqlite3.Row:
    """Give the lane back, and say what came of it."""
    row = get(conn, claim_id)
    if row is None:
        raise KeyError(claim_id)
    if row["released_at"] is not None:
        raise ValueError(f"lane claim {claim_id} was already released")
    with write(conn):
        conn.execute(
            "UPDATE lane_claims SET released_at = ?, summary = ? WHERE id = ?",
            (now or utcnow(), summary, claim_id),
        )
    return get(conn, claim_id)


def get(conn: sqlite3.Connection, claim_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM lane_claims WHERE id = ?", (claim_id,)
    ).fetchone()


def recent(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    """The last few lane claims, newest first — what sessions have worked on."""
    return conn.execute(
        "SELECT * FROM lane_claims ORDER BY claimed_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
