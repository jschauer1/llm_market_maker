"""Lane claims — who is working on what, visible but not locked.

`go` asks a session to pick one of four lanes and stay in it. A claim row
makes that visible to every other session, which is useful information
even when nothing is enforced: a peer choosing its own lane can see
maintenance is covered and pick something else.

**Lanes are not the floor.** The floor must happen exactly once a day, so
`tools/floor.py` locks it. A lane is advisory: two sessions on
maintenance is wasteful, not harmful, and a session that judges the work
important enough may join one that is already held (user ruling
2026-08-31). Joining is discouraged, never blocked, and records its
reason -- the friction that keeps it rare is having to say why, not being
told no.
"""

from __future__ import annotations

import pytest

from tools import db, lanes


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    return c


def test_an_open_lane_is_claimed_outright(conn):
    claim = lanes.claim(conn, "maintenance", "sess-a",
                        now="2026-08-31T01:00:00Z")
    assert claim["lane"] == "maintenance"
    assert claim["session"] == "sess-a"
    assert claim["joined"] == 0


def test_status_shows_who_holds_each_lane(conn):
    lanes.claim(conn, "maintenance", "sess-a", now="2026-08-31T01:00:00Z")

    status = lanes.status(conn, now="2026-08-31T01:30:00Z")
    assert status["maintenance"]["holders"] == ["sess-a"]
    assert status["theory"]["holders"] == []


def test_claiming_a_held_lane_is_refused_by_default(conn):
    """Refused, and told where to go instead -- the point is to steer a
    session to open work, not to stop it."""
    lanes.claim(conn, "maintenance", "sess-a", now="2026-08-31T01:00:00Z")

    with pytest.raises(lanes.LaneHeld) as err:
        lanes.claim(conn, "maintenance", "sess-b", now="2026-08-31T01:05:00Z")
    assert "sess-a" in str(err.value)


def test_a_session_may_join_a_held_lane_with_a_reason(conn):
    lanes.claim(conn, "maintenance", "sess-a", now="2026-08-31T01:00:00Z")

    claim = lanes.claim(
        conn, "maintenance", "sess-b", now="2026-08-31T01:05:00Z",
        join="the migration is blocking three theories and wants two pairs "
             "of hands",
    )
    assert claim["joined"] == 1
    assert "blocking three theories" in claim["join_reason"]
    assert lanes.status(conn, now="2026-08-31T01:06:00Z")[
        "maintenance"]["holders"] == ["sess-a", "sess-b"]


def test_joining_without_a_reason_is_refused(conn):
    """An empty reason is the discouragement doing its job: a session
    that cannot say why it is doubling up should go find open work."""
    lanes.claim(conn, "maintenance", "sess-a", now="2026-08-31T01:00:00Z")

    with pytest.raises(ValueError, match="reason"):
        lanes.claim(conn, "maintenance", "sess-b",
                    now="2026-08-31T01:05:00Z", join="   ")


def test_a_lane_claim_expires_so_a_dead_session_frees_it(conn):
    lanes.claim(conn, "maintenance", "sess-dead", now="2026-08-31T01:00:00Z")

    late = "2026-08-31T09:00:00Z"
    assert lanes.status(conn, now=late)["maintenance"]["holders"] == []
    assert lanes.claim(conn, "maintenance", "sess-b", now=late) is not None


def test_releasing_a_lane_frees_it_immediately(conn):
    claim = lanes.claim(conn, "theory", "sess-a", now="2026-08-31T01:00:00Z")
    lanes.release(conn, claim["id"], now="2026-08-31T02:00:00Z",
                  summary="adopted the NO rule at v5")

    assert lanes.status(conn, now="2026-08-31T02:01:00Z")[
        "theory"]["holders"] == []


def test_a_theory_lane_records_which_theory_is_being_worked(conn):
    """Two sessions on the theory lane are only colliding if they picked
    the same theory -- the lane alone cannot tell you."""
    lanes.claim(conn, "theory", "sess-a", focus="insider_judgment",
                now="2026-08-31T01:00:00Z")

    status = lanes.status(conn, now="2026-08-31T01:30:00Z")
    assert status["theory"]["focus"] == ["insider_judgment"]
    # A different theory is different work, so it claims cleanly.
    assert lanes.claim(conn, "theory", "sess-b", focus="structural_arb",
                       now="2026-08-31T01:05:00Z") is not None


def test_the_same_theory_twice_is_held_like_any_other_lane(conn):
    lanes.claim(conn, "theory", "sess-a", focus="insider_judgment",
                now="2026-08-31T01:00:00Z")

    with pytest.raises(lanes.LaneHeld):
        lanes.claim(conn, "theory", "sess-b", focus="insider_judgment",
                    now="2026-08-31T01:05:00Z")


def test_an_unknown_lane_is_refused(conn):
    with pytest.raises(ValueError, match="lane"):
        lanes.claim(conn, "wandering", "sess-a")


def test_find_theories_is_a_lane(conn):
    """Sourcing theses is not the same work as building one. go-new-theory
    takes ONE thesis all the way to running; this lane goes looking for
    theses nobody has proposed and files them. Different output, different
    session, so it needs its own claim."""
    claim = lanes.claim(conn, "find-theories", "sess-a",
                        now="2026-09-01T01:00:00Z")
    assert claim["lane"] == "find-theories"
    assert "find-theories" in lanes.status(conn, now="2026-09-01T01:30:00Z")


def test_every_lane_go_dispatches_to_is_claimable(conn):
    """The schema's CHECK and `lanes.LANES` must not drift apart.

    They did: `study` was added to LANES and to `go`'s lane table on
    2026-09-01 without widening `lane_claims`, so `lane claim --lane study`
    died with a bare `sqlite3.IntegrityError: CHECK constraint failed` --
    an entire lane unclaimable in every database, new and old. A per-lane
    test would not have caught it, because the missing lane is by
    definition the one nobody wrote a test for. Iterate LANES instead.
    """
    for i, lane in enumerate(lanes.LANES):
        claim = lanes.claim(conn, lane, f"sess-{i}",
                            now=f"2026-09-01T0{i}:00:00Z")
        assert claim["lane"] == lane


def test_a_database_predating_a_lane_is_migrated_rather_than_rejected(conn):
    """An old DB carries the narrow CHECK in its own DDL, and
    `CREATE TABLE IF NOT EXISTS` will not touch it. The migration used to
    short-circuit on a hardcoded sentinel lane name, so it stopped firing
    for every lane added after that one. It now diffs the accepted sets."""
    conn.executescript(
        """
        DROP TABLE lane_claims;
        CREATE TABLE lane_claims (
            id INTEGER PRIMARY KEY,
            lane TEXT NOT NULL
                 CHECK (lane IN ('floor','theory','new-theory',
                                 'find-theories','maintenance')),
            session TEXT NOT NULL, focus TEXT, claimed_at TEXT NOT NULL,
            released_at TEXT, summary TEXT,
            joined INTEGER NOT NULL DEFAULT 0, join_reason TEXT
        );
        INSERT INTO lane_claims (id, lane, session, claimed_at)
        VALUES (1, 'maintenance', 'legacy-sess', '2026-08-31T01:00:00Z');
        """
    )
    db._migrate_lane_claims(conn)

    claim = lanes.claim(conn, "study", "sess-a", focus="some-study",
                        now="2026-09-01T02:00:00Z")
    assert claim["lane"] == "study"
    # the legacy row survives the rebuild
    kept = conn.execute(
        "SELECT session FROM lane_claims WHERE id = 1").fetchone()
    assert kept[0] == "legacy-sess"
