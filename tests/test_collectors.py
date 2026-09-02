"""Long-running collections have to be visible, or a stall is silent.

Incident 2026-09-01 (ticket backfill-restart-loop): the series-bias
liquidity backfill stopped twice because the session running it ended --
once for 5.7 hours before anyone noticed, and only then because a session
happened to run `collect.py status` by hand. Nothing prompts that. The job
outlives a session by design (~4 hours), so the failure is structural:
whoever starts it cannot finish it.

The data is perishable -- Kalshi ages settled markets out ~60 days after
close -- so a stall is permanent loss rather than delay. The first aged-out
rows appeared during the restarted run.
"""

import sqlite3

import pytest

from tools import collectors


@pytest.fixture
def progress_db(tmp_path):
    """A stand-in for a study's own collect.db `progress` table."""
    path = tmp_path / "collect.db"
    c = sqlite3.connect(path)
    c.execute(
        "CREATE TABLE progress (phase TEXT NOT NULL, key TEXT NOT NULL,"
        " done_at TEXT NOT NULL, note TEXT, PRIMARY KEY (phase, key))"
    )
    c.executemany(
        "INSERT INTO progress (phase, key, done_at) VALUES (?, ?, ?)",
        [
            ("backfill", "KXAAA", "2026-09-01T10:00:00+00:00"),
            ("backfill", "KXBBB", "2026-09-01T11:00:00+00:00"),
            ("prices", "KXAAA", "2026-08-29T14:00:00+00:00"),
        ],
    )
    c.commit()
    c.close()
    return path


def _collector(path, phase="backfill"):
    return collectors.Collection(
        name=f"test {phase}",
        db=path,
        phase=phase,
        unit="series",
        command=f"collect.py {phase}",
    )


def test_reports_count_and_last_write(progress_db):
    got = collectors.read(_collector(progress_db), now="2026-09-01T11:30:00Z")
    assert got.done == 2
    assert got.last_write == "2026-09-01T11:00:00+00:00"


def test_a_recent_write_reads_as_running(progress_db):
    got = collectors.read(_collector(progress_db), now="2026-09-01T11:02:00Z")
    assert got.state == "RUNNING"


def test_a_cold_phase_reads_as_idle_with_its_age(progress_db):
    """The 5.7-hour hole. Nothing here claims the job is broken -- only
    that it has not written, which is the fact nobody had."""
    got = collectors.read(_collector(progress_db), now="2026-09-01T16:42:00Z")
    assert got.state == "IDLE"
    assert got.age_hours == pytest.approx(5.7, abs=0.05)


def test_a_missing_database_is_not_an_error(tmp_path):
    """A study whose collector has never run must not break orientation."""
    got = collectors.read(
        _collector(tmp_path / "nope.db"), now="2026-09-01T12:00:00Z"
    )
    assert got.state == "ABSENT"
    assert got.done == 0


def test_a_database_without_a_progress_table_is_not_an_error(tmp_path):
    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    got = collectors.read(_collector(path), now="2026-09-01T12:00:00Z")
    assert got.state == "ABSENT"


def test_an_unknown_phase_reports_nothing_rather_than_lying(progress_db):
    got = collectors.read(
        _collector(progress_db, phase="never-ran"), now="2026-09-01T12:00:00Z"
    )
    assert got.done == 0
    assert got.state == "IDLE"
    assert got.last_write is None


def test_reading_is_read_only(progress_db):
    """`cli state` must never be able to disturb a collector's own DB --
    it is run by every session, including while a walk holds that file."""
    before = progress_db.read_bytes()
    collectors.read(_collector(progress_db), now="2026-09-01T12:00:00Z")
    assert progress_db.read_bytes() == before


def test_a_locked_database_degrades_instead_of_crashing(progress_db, monkeypatch):
    """The collector holds this file for hours at a time. `cli state` is
    the session's orientation surface and must render anyway."""
    def boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(collectors.sqlite3, "connect", boom)
    got = collectors.read(_collector(progress_db), now="2026-09-01T12:00:00Z")
    assert got.state == "UNREADABLE"


def test_the_registry_names_the_known_collections():
    """Two entries today, both phases of the series-bias collector."""
    names = [c.name for c in collectors.REGISTRY]
    assert any("series-bias" in n and "prices" in n for n in names)
    assert any("series-bias" in n and "backfill" in n for n in names)
    for c in collectors.REGISTRY:
        assert c.command, "every entry says how to resume it"


def test_render_lines_carry_state_count_and_age(progress_db):
    lines = collectors.render(
        [_collector(progress_db)], now="2026-09-01T16:42:00Z"
    )
    assert len(lines) == 1
    assert "IDLE" in lines[0]
    assert "2 series" in lines[0]
    assert "5.7h" in lines[0]


def test_render_shows_the_resume_command_for_a_cold_collection(progress_db):
    """A session that spots the stall should not have to go find how to
    restart it -- that lookup is the friction that let it sit for hours."""
    lines = collectors.render(
        [_collector(progress_db)], now="2026-09-01T16:42:00Z"
    )
    assert "collect.py backfill" in "\n".join(lines)


# --- completeness, where the study can answer it honestly ---
#
# An IDLE line that nags a session to resume a finished job is a tool that
# lies, and this lane exists to stop that. But completeness is
# study-specific: only some phases can express "work left" as a query, so
# `remaining_sql` is optional and its absence means no claim is made.


@pytest.fixture
def obs_db(tmp_path):
    path = tmp_path / "collect.db"
    c = sqlite3.connect(path)
    c.execute(
        "CREATE TABLE progress (phase TEXT NOT NULL, key TEXT NOT NULL,"
        " done_at TEXT NOT NULL, note TEXT, PRIMARY KEY (phase, key))"
    )
    c.execute("CREATE TABLE obs (series_ticker TEXT, spread REAL)")
    c.executemany(
        "INSERT INTO progress (phase, key, done_at) VALUES ('backfill', ?, ?)",
        [("KXAAA", "2026-09-01T10:00:00+00:00")],
    )
    c.executemany(
        "INSERT INTO obs (series_ticker, spread) VALUES (?, ?)",
        [("KXAAA", None), ("KXAAA", 0.02), ("KXBBB", 0.01)],
    )
    c.commit()
    c.close()
    return path


REMAINING = (
    "SELECT COUNT(DISTINCT series_ticker) FROM obs WHERE spread IS NULL"
    " AND series_ticker NOT IN"
    " (SELECT key FROM progress WHERE phase = 'backfill')"
)


def _with_remaining(path, sql=REMAINING):
    return collectors.Collection(
        name="test backfill", db=path, phase="backfill", unit="series",
        command="collect.py backfill", remaining_sql=sql,
    )


def test_no_work_left_reads_as_complete(obs_db):
    """KXAAA's NULL survived its own backfill -- the candles aged out
    upstream -- which is not the same as work remaining."""
    got = collectors.read(_with_remaining(obs_db), now="2026-09-02T00:00:00Z")
    assert got.remaining == 0
    assert got.state == "COMPLETE"


def test_an_unattempted_series_keeps_it_idle(obs_db):
    c = sqlite3.connect(obs_db)
    c.execute("INSERT INTO obs (series_ticker, spread) VALUES ('KXCCC', NULL)")
    c.commit()
    c.close()
    got = collectors.read(_with_remaining(obs_db), now="2026-09-02T00:00:00Z")
    assert got.remaining == 1
    assert got.state == "IDLE"


def test_a_complete_collection_does_not_nag_a_resume(obs_db):
    lines = collectors.render(
        [_with_remaining(obs_db)], now="2026-09-02T00:00:00Z"
    )
    assert "COMPLETE" in lines[0]
    assert "resume:" not in "\n".join(lines)


def test_without_remaining_sql_no_completeness_is_claimed(progress_db):
    """`prices` cannot express work-left without duplicating the
    collector's own eligibility rule, so it makes no claim at all."""
    got = collectors.read(_collector(progress_db), now="2026-09-01T16:42:00Z")
    assert got.remaining is None
    assert got.state == "IDLE"


def test_a_broken_remaining_query_degrades_to_no_claim(obs_db):
    got = collectors.read(
        _with_remaining(obs_db, "SELECT COUNT(*) FROM no_such_table"),
        now="2026-09-02T00:00:00Z",
    )
    assert got.remaining is None
    assert got.state == "IDLE", "an unanswerable query must not claim COMPLETE"


def test_a_running_collection_is_running_even_if_work_remains(obs_db):
    c = sqlite3.connect(obs_db)
    c.execute("INSERT INTO obs (series_ticker, spread) VALUES ('KXCCC', NULL)")
    c.execute(
        "INSERT INTO progress (phase, key, done_at)"
        " VALUES ('backfill', 'KXDDD', '2026-09-02T00:00:00+00:00')"
    )
    c.commit()
    c.close()
    got = collectors.read(_with_remaining(obs_db), now="2026-09-02T00:01:00Z")
    assert got.state == "RUNNING"
