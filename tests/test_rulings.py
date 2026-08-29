import pytest

from tools import db, rulings


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_record_and_list_roundtrip(conn):
    rid = rulings.record(
        conn, "clustered SEs are reported beside every score",
        authority="supervisor", subject="scoring",
        ruled_at="2026-08-29T00:00:00Z",
        log_entry="2026-08-29 (cont.) — attempt-level scoring landed",
    )
    rows = rulings.list_rulings(conn)
    assert [r["id"] for r in rows] == [rid]
    assert rows[0]["status"] == "binding"


def test_status_transitions_and_filtering(conn):
    rid = rulings.record(conn, "x", authority="user", subject="schema")
    rulings.set_status(conn, rid, "implemented")
    assert rulings.list_rulings(conn, status="binding") == []
    assert rulings.list_rulings(conn, status="implemented")[0]["id"] == rid


def test_bad_authority_refused(conn):
    with pytest.raises(Exception):
        rulings.record(conn, "x", authority="claude", subject="schema")


def test_state_standing_shows_binding_rulings(conn):
    from tools import state
    rulings.record(conn, "the force floor is adopted", authority="user",
                   subject="lifecycle", ruled_at="2026-08-29T00:00:00Z")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "force floor" in text
