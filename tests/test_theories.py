import pytest

from tools import db, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_register_creates_a_theory_at_version_one(conn):
    theories.register(conn, "insider_bias", "Insider Bias",
                      "theories/insider_bias", now=TS)
    row = theories.get(conn, "insider_bias")
    assert row["name"] == "Insider Bias"
    assert row["version"] == 1
    assert row["status"] == "proposed"
    assert row["created_at"] == TS


def test_get_returns_none_for_unknown_theory(conn):
    assert theories.get(conn, "nope") is None


def test_register_is_idempotent(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.register(conn, "t1", "One Renamed", "theories/t1", now=TS)
    assert theories.get(conn, "t1")["name"] == "One Renamed"
    assert len(theories.list_theories(conn)) == 1


def test_register_does_not_reset_version(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.bump_version(conn, "t1", now=TS)
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    assert theories.get(conn, "t1")["version"] == 2


def test_register_does_not_reset_status(conn):
    # Re-registering happens on every scan that discovers theories on disk.
    # If it reset status, an active theory would be silently demoted to
    # proposed and drop out of the live run.
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.set_status(conn, "t1", "active", now=TS)
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    assert theories.get(conn, "t1")["status"] == "active"


def test_set_status_updates_status_and_timestamp(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.set_status(conn, "t1", "active", now="2026-08-24T00:00:00Z")
    row = theories.get(conn, "t1")
    assert row["status"] == "active"
    assert row["updated_at"] == "2026-08-24T00:00:00Z"


def test_set_status_rejects_invalid_status(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    with pytest.raises(ValueError):
        theories.set_status(conn, "t1", "banana")


def test_bump_version_increments_and_returns(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    assert theories.bump_version(conn, "t1", now=TS) == 2
    assert theories.bump_version(conn, "t1", now=TS) == 3
    assert theories.get(conn, "t1")["version"] == 3


def test_bump_version_rejects_unknown_theory(conn):
    with pytest.raises(KeyError):
        theories.bump_version(conn, "nope")


def test_list_filters_by_status(conn):
    theories.register(conn, "a", "A", "theories/a", status="active", now=TS)
    theories.register(conn, "b", "B", "theories/b", status="paused", now=TS)
    active = theories.list_theories(conn, status="active")
    assert [r["id"] for r in active] == ["a"]
    assert len(theories.list_theories(conn)) == 2


def test_list_running_only_includes_under_review(conn):
    # under_review theories stay on the board -- that is the whole point of
    # the status. proposed/paused/retired do not run.
    for tid, status in (
        ("a", "proposed"), ("b", "testing"), ("c", "active"),
        ("d", "under_review"), ("e", "paused"),
    ):
        theories.register(conn, tid, tid.upper(), f"theories/{tid}", now=TS)
        theories.set_status(conn, tid, status, now=TS)
    running = theories.list_theories(conn, running_only=True)
    assert [r["id"] for r in running] == ["b", "c", "d"]


def test_list_rejects_status_and_running_together(conn):
    with pytest.raises(ValueError):
        theories.list_theories(conn, status="active", running_only=True)


def test_evidence_level_statuses_are_accepted(conn):
    # testing and under_review are the two the older status set lacked, and
    # under_review is the one the lifecycle now leans on.
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    for status in ("testing", "active", "under_review", "paused"):
        theories.set_status(conn, "t1", status, now=TS)
        assert theories.get(conn, "t1")["status"] == status


# --- retirement is the user's call -------------------------------------


def test_claude_cannot_retire_a_theory(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.propose_retirement(conn, "t1", "screen and judgment both flat",
                                now=TS)
    with pytest.raises(PermissionError):
        theories.set_status(conn, "t1", "retired", now=TS)
    assert theories.get(conn, "t1")["status"] != "retired"


def test_cannot_register_a_theory_as_retired(conn):
    # Otherwise register() is a trivial bypass of the set_status guard.
    with pytest.raises(PermissionError):
        theories.register(conn, "t1", "One", "theories/t1", status="retired")


def test_user_cannot_retire_without_a_diagnosis_on_file(conn):
    # The rationale is what the user reads when ruling. Retiring with none
    # means nobody wrote down why -- which is how a system forgets.
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    with pytest.raises(ValueError):
        theories.set_status(conn, "t1", "retired", now=TS,
                            authorized_by="user")


def test_user_can_retire_once_a_proposal_stands(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.propose_retirement(conn, "t1", "no slice profitable at n=180",
                                now=TS)
    theories.set_status(conn, "t1", "retired", now=TS, authorized_by="user")
    assert theories.get(conn, "t1")["status"] == "retired"


def test_propose_retirement_does_not_change_status(conn):
    # The theory keeps running while the user has not ruled -- pulling it off
    # the board would stop the evidence that answers the question.
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.set_status(conn, "t1", "under_review", now=TS)
    theories.propose_retirement(conn, "t1", "diagnosed", now=TS)
    row = theories.get(conn, "t1")
    assert row["status"] == "under_review"
    assert row["retirement_proposed_at"] == TS
    assert row["retirement_rationale"] == "diagnosed"


def test_propose_retirement_requires_a_rationale(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    for bad in ("", "   "):
        with pytest.raises(ValueError):
            theories.propose_retirement(conn, "t1", bad, now=TS)


def test_propose_retirement_rejects_unknown_theory(conn):
    with pytest.raises(KeyError):
        theories.propose_retirement(conn, "nope", "gone", now=TS)


def test_withdraw_retirement_clears_the_proposal(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.propose_retirement(conn, "t1", "diagnosed", now=TS)
    theories.withdraw_retirement(conn, "t1", now=TS)
    row = theories.get(conn, "t1")
    assert row["retirement_proposed_at"] is None
    assert row["retirement_rationale"] is None


def test_recovering_to_active_clears_a_stale_proposal(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.propose_retirement(conn, "t1", "diagnosed", now=TS)
    theories.set_status(conn, "t1", "active", now=TS)
    assert theories.get(conn, "t1")["retirement_proposed_at"] is None


def test_staying_under_review_keeps_the_proposal(conn):
    theories.register(conn, "t1", "One", "theories/t1", now=TS)
    theories.propose_retirement(conn, "t1", "diagnosed", now=TS)
    theories.set_status(conn, "t1", "under_review", now=TS)
    assert theories.get(conn, "t1")["retirement_proposed_at"] == TS


def test_list_pending_retirement_surfaces_unruled_proposals(conn):
    theories.register(conn, "a", "A", "theories/a", now=TS)
    theories.register(conn, "b", "B", "theories/b", now=TS)
    theories.register(conn, "c", "C", "theories/c", now=TS)
    theories.propose_retirement(conn, "a", "diagnosed a", now=TS)
    theories.propose_retirement(conn, "c", "diagnosed c", now=TS)
    theories.set_status(conn, "c", "retired", now=TS, authorized_by="user")
    # a is awaiting a ruling; b was never proposed; c has been ruled on.
    assert [r["id"] for r in theories.list_pending_retirement(conn)] == ["a"]
