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
    # theory_versions (phase 6) and data_windows (phase 7) do not exist
    # yet -- the shape is stable from day one and panels light up as
    # phases land (spec 3.2).
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "not yet tracked — table data_windows" in text


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


def test_write_state_reuses_a_passed_rendering(conn, tmp_path, monkeypatch):
    # tools/cli.py's `state --write` renders once and passes the text
    # through, so the printed output and STATE.md agree byte for byte --
    # rendering twice would stamp two different `now` timestamps.
    monkeypatch.chdir(tmp_path)
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    state.write_state(conn, now="2026-08-29T23:59:59Z", text=text)
    assert (tmp_path / "STATE.md").read_text(encoding="utf-8") == text


def test_evidence_reports_honest_line_when_scores_never_written(conn):
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    theories.set_status(conn, "demo_theory", "testing")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "scores never written — run score-theories" in text
    assert "no live score at v" not in text
    assert "last settle run:  never" in text


def test_standing_truncates_long_rulings_and_shows_footer(conn):
    from tools import rulings
    long_text = "x" * 150
    rulings.record(
        conn, long_text, authority="user", subject="test-subject",
        ruled_at="2026-08-29T00:00:00Z",
    )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert ("x" * 100 + "…") in text
    assert ("x" * 101) not in text
    assert (
        "full text: python -m tools.cli rulings list --status binding"
    ) in text


def test_standing_does_not_add_ellipsis_when_not_truncated(conn):
    from tools import rulings
    rulings.record(
        conn, "short ruling", authority="user", subject="test-subject",
        ruled_at="2026-08-29T00:00:00Z",
    )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "short ruling…" not in text
    assert "short ruling" in text


def test_theories_panel_shows_chain_1_for_a_fresh_theory(conn):
    # I3: register() alone writes v1's own theory_versions row -- carry_
    # chain(..., 1) is [1], so the panel must show the real figure, not
    # the old "chain ready" placeholder.
    from tools import theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "[chain 1]" in text
    assert "chain ready" not in text


def test_theories_panel_shows_chain_n_for_a_proven_carry(conn):
    from tools import theories
    from tools.domain import EquivalenceResult
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    proof = EquivalenceResult(
        theory_id="demo_theory", from_version=1, n_attempts=1,
        divergences=(), n_divergent=0, label="carry-proof/demo-v1-to-v2",
    )
    theories.bump_version(
        conn, "demo_theory", kind="carry", justification="no-op refactor",
        equivalence=proof,
    )
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "[chain 2]" in text


def test_theories_panel_stubs_when_theory_versions_is_absent(conn):
    # Defensive path (mirrors every other panel's _table_exists guard):
    # an older DB that predates this table must stub, not error, even
    # though a theory was registered before the table went away.
    from tools import db as db_mod, theories
    theories.register(conn, "demo_theory", "Demo", "theories/demo")
    with db_mod.write(conn):
        conn.execute("DROP TABLE theory_versions")
    text = state.render_state(conn, now="2026-08-29T12:00:00Z")
    assert "[chain n/a]" in text


def test_freshness_says_the_floor_is_due_when_none_has_run(conn):
    text = state.render_state(conn, now="2026-08-31T12:00:00Z")
    assert "floor duty:" in text
    assert "DUE" in text


def test_freshness_reports_a_completed_floor_and_when_the_next_is_due(conn):
    from tools import floor
    claim = floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")
    floor.complete(conn, claim["id"], now="2026-08-31T02:00:00Z")

    text = state.render_state(conn, now="2026-08-31T06:00:00Z")
    assert "floor duty:" in text
    assert "DUE" not in text, "a floor that ran 4h ago is not due"
    assert "sess-a" in text
