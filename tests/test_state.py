import pytest

from tools import db, state


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def test_state_renders_every_panel_header(conn):
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    for panel in ("THEORIES", "STANDING", "EVIDENCE", "WINDOWS",
                  "QUEUE", "FRESHNESS"):
        assert panel in text


def test_absent_tables_render_stubs_not_errors(conn):
    # rulings (phase 2), theory_versions (phase 6) and data_windows
    # (phase 7) do not exist yet -- the shape is stable from day one and
    # panels light up as phases land (spec 3.2).
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "not yet tracked" in text


def test_state_reflects_theories_and_freshness(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " title, raw_json) VALUES ('kalshi', 'T-1',"
            " '2026-08-29T10:00:00Z', 't', '{}')"
        )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "demo_theory" in text
    assert "last board pull" in text and "2026-08-29T10:00:00Z" in text


def test_write_flag_emits_state_md(conn, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state.write_state(conn, now="2026-08-29T12:00:00Z")
    assert (tmp_path / "STATE.md").read_text(encoding="utf-8").startswith("#")
