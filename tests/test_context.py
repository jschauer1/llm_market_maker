"""A theory runs against a fake TheoryContext: ten hand-built markets, no
live connection, no network, no monkeypatch (spec section 7)."""

from datetime import datetime, timezone

from tests.test_theory import Mechanical, fake_ctx, mkm
from tools import db
from tools.theory import TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def test_a_theory_runs_on_a_ten_market_fake_board():
    board = [mkm(f"KXT-{i}", yes_ask=0.30 + i * 0.05) for i in range(10)]
    result = Mechanical().start(fake_ctx(board)).finish(dry_run=True)
    assert result.funnel["candidates"] == 5      # asks 0.30..0.50 inclusive
    assert all(s.edge.basis == "model" for s in result.scored)


def test_build_binds_bucket_rates_to_the_connection(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    ctx = TheoryContext.build(conn=conn, board=[], now=NOW)
    assert ctx.bucket_rates("nonexistent_theory", 1) == {}
    conn.close()


def test_fetch_injection_needs_no_monkeypatch():
    from tools.kalshi import markets

    def fake(url, params=None, timeout=30):
        return {"events": [], "cursor": ""}

    assert markets.list_open(fetch=fake) == []
