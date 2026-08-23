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
    theories.register(conn, "b", "B", "theories/b", status="retired", now=TS)
    active = theories.list_theories(conn, status="active")
    assert [r["id"] for r in active] == ["a"]
    assert len(theories.list_theories(conn)) == 2
