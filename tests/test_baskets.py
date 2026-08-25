import sqlite3

import pytest

from tools import db, ledger, theories

TS = "2026-08-23T12:00:00Z"
LATER = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_opportunities_has_the_basket_columns(conn):
    cols = _columns(conn, "opportunities")
    assert {"position_kind", "leg_count", "max_payout"} <= cols


def test_opportunity_legs_table_exists(conn):
    cols = _columns(conn, "opportunity_legs")
    assert cols == {
        "opportunity_id", "leg_index", "kalshi_ticker", "outcome",
        "entry_price", "spread_at_call", "volume_at_call",
    }


def test_existing_single_leg_row_defaults_are_correct(conn):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="KXTEST-26",
        outcome="yes", entry_price=0.40, edge_pts_net=6.0, now=TS,
    )
    row = ledger.get_opportunity(conn, opp_id)
    assert row["position_kind"] == "single"
    assert row["leg_count"] == 1
    assert row["max_payout"] == pytest.approx(1.0)


def test_position_kind_rejects_an_unknown_value(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO opportunities (theory_id, theory_version, run_mode,"
            " run_id, kalshi_ticker, outcome, entry_price,"
            " screen_edge_pts_net, edge_pts_net, position_kind,"
            " first_seen_at, last_seen_at)"
            " VALUES ('t1', 1, 'live', 'live', 'X', 'yes', 0.4, 1.0, 1.0,"
            " 'combo', ?, ?)",
            (TS, TS),
        )


def test_basket_key_is_stable_across_leg_order():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"},
         {"kalshi_ticker": "BBB", "outcome": "no"}]
    b = list(reversed(a))
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_normalizes_case():
    a = [{"kalshi_ticker": "aaa", "outcome": "YES"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    assert ledger.basket_key(a) == ledger.basket_key(b)


def test_basket_key_differs_on_different_legs():
    a = [{"kalshi_ticker": "AAA", "outcome": "yes"}]
    b = [{"kalshi_ticker": "AAA", "outcome": "no"}]
    assert ledger.basket_key(a) != ledger.basket_key(b)


def test_basket_key_shape():
    key = ledger.basket_key([{"kalshi_ticker": "AAA", "outcome": "yes"}])
    assert key.startswith("BASKET:")
    assert len(key) == len("BASKET:") + 16


def test_basket_key_raises_on_missing_ticker():
    with pytest.raises(ValueError, match="leg 0.*kalshi_ticker.*required"):
        ledger.basket_key([{"kalshi_ticker": None, "outcome": "yes"}])


def test_basket_key_raises_on_missing_outcome():
    with pytest.raises(ValueError, match="leg 0.*outcome.*required"):
        ledger.basket_key([{"kalshi_ticker": "AAA", "outcome": None}])


def test_basket_key_prevents_delimiter_collision():
    # Without escaping, these two would produce the same hash with string joining.
    # With json.dumps(), they must be different.
    a = [{"kalshi_ticker": "123", "outcome": "yes"},
         {"kalshi_ticker": "456", "outcome": "no"}]
    b = [{"kalshi_ticker": "123", "outcome": "yes|456:no"}]
    assert ledger.basket_key(a) != ledger.basket_key(b)


def _legs():
    return [
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.40},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.55},
    ]


def _basket(conn, **overrides):
    kwargs = dict(
        theory_id="t1", theory_version=1, legs=_legs(),
        edge_pts_net=5.0, edge_basis="model", now=TS,
    )
    kwargs.update(overrides)
    return ledger.record_basket(conn, **kwargs)


def test_basket_writes_one_header_and_n_leg_rows(conn):
    opp_id, created = _basket(conn)
    assert created is True
    row = ledger.get_opportunity(conn, opp_id)
    assert row["position_kind"] == "basket"
    assert row["leg_count"] == 2
    assert row["outcome"] == "basket"
    assert row["kalshi_ticker"].startswith("BASKET:")
    assert len(ledger.get_legs(conn, opp_id)) == 2


def test_basket_entry_price_is_the_summed_cost(conn):
    opp_id, _ = _basket(conn)
    row = ledger.get_opportunity(conn, opp_id)
    assert row["entry_price"] == pytest.approx(0.95)


def test_basket_legs_are_normalized_and_ordered(conn):
    opp_id, _ = _basket(conn, legs=[
        {"kalshi_ticker": " kxa-26 ", "outcome": "YES", "entry_price": 0.40},
        {"kalshi_ticker": "KXB-26", "outcome": " No ", "entry_price": 0.55},
    ])
    legs = ledger.get_legs(conn, opp_id)
    assert [l["leg_index"] for l in legs] == [0, 1]
    assert legs[0]["kalshi_ticker"] == "KXA-26"
    assert legs[0]["outcome"] == "yes"
    assert legs[1]["outcome"] == "no"


def test_resighting_a_basket_updates_rather_than_inserts(conn):
    first, created_a = _basket(conn)
    second, created_b = _basket(conn, now=LATER, edge_pts_net=7.0)
    assert created_a is True and created_b is False
    assert first == second
    row = ledger.get_opportunity(conn, first)
    assert row["times_seen"] == 2
    assert row["last_seen_at"] == LATER
    assert len(ledger.get_legs(conn, first)) == 2


def test_resighting_with_reordered_legs_is_the_same_basket(conn):
    first, _ = _basket(conn)
    second, created = _basket(conn, legs=list(reversed(_legs())), now=LATER)
    assert created is False
    assert first == second


def test_resighting_freezes_entry_price_on_header_and_legs(conn):
    """A re-sighting at new prices must not let the ledger's own header
    row and its legs drift onto different vintages of the same bet."""
    first, _ = _basket(conn)
    second, created = _basket(conn, now=LATER, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.10},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.15},
    ])
    assert created is False
    assert first == second

    row = ledger.get_opportunity(conn, first)
    assert row["entry_price"] == pytest.approx(0.95)

    legs = ledger.get_legs(conn, first)
    assert legs[0]["entry_price"] == pytest.approx(0.40)
    assert legs[1]["entry_price"] == pytest.approx(0.55)


def test_resighting_refreshes_leg_quote_fields(conn):
    opp_id, _ = _basket(conn, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.40,
         "spread_at_call": 0.02, "volume_at_call": 100},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.55,
         "spread_at_call": 0.03, "volume_at_call": 200},
    ])
    _basket(conn, now=LATER, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.10,
         "spread_at_call": 0.09, "volume_at_call": 900},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.15,
         "spread_at_call": 0.08, "volume_at_call": 800},
    ])
    legs = ledger.get_legs(conn, opp_id)
    assert legs[0]["spread_at_call"] == pytest.approx(0.09)
    assert legs[0]["volume_at_call"] == pytest.approx(900)
    assert legs[1]["spread_at_call"] == pytest.approx(0.08)
    assert legs[1]["volume_at_call"] == pytest.approx(800)
    # entry_price stays frozen even while the quote fields refresh.
    assert legs[0]["entry_price"] == pytest.approx(0.40)
    assert legs[1]["entry_price"] == pytest.approx(0.55)


def test_resighting_keeps_header_cost_consistent_with_legs(conn):
    """The invariant the bug broke: header entry_price (the summed cost at
    first sighting) must still equal sum(leg entry_price) after a
    re-sighting at different prices, not a mix of first- and latest-seen
    values."""
    opp_id, _ = _basket(conn)
    _basket(conn, now=LATER, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 0.10},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.15},
    ])
    row = ledger.get_opportunity(conn, opp_id)
    legs = ledger.get_legs(conn, opp_id)
    assert row["entry_price"] == pytest.approx(
        sum(l["entry_price"] for l in legs)
    )


def test_basket_cost_above_one_is_allowed_when_payout_allows_it(conn):
    opp_id, _ = _basket(conn, max_payout=2.0, legs=[
        {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
        {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
    ])
    assert ledger.get_opportunity(conn, opp_id)["entry_price"] == pytest.approx(1.65)


def test_basket_cost_above_max_payout_is_refused(conn):
    with pytest.raises(ValueError, match="max_payout"):
        _basket(conn, max_payout=1.0, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "no", "entry_price": 0.80},
            {"kalshi_ticker": "KXB-26", "outcome": "no", "entry_price": 0.85},
        ])


def test_basket_refuses_empty_legs(conn):
    with pytest.raises(ValueError, match="at least one leg"):
        _basket(conn, legs=[])


def test_basket_refuses_a_leg_with_no_ticker(conn):
    with pytest.raises(ValueError, match="kalshi_ticker"):
        _basket(conn, legs=[
            {"kalshi_ticker": "", "outcome": "yes", "entry_price": 0.40},
        ])


def test_basket_refuses_a_leg_with_no_outcome(conn):
    with pytest.raises(ValueError, match="outcome"):
        _basket(conn, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "", "entry_price": 0.40},
        ])


def test_basket_refuses_a_leg_price_in_cents(conn):
    with pytest.raises(ValueError, match="decimal dollars"):
        _basket(conn, legs=[
            {"kalshi_ticker": "KXA-26", "outcome": "yes", "entry_price": 40},
        ])


def test_basket_write_is_atomic_on_leg_insert_failure(tmp_path):
    """A failure after the header write must not leave a headless row.

    The header INSERT and the leg INSERTs share one `write(conn)` block, so
    sqlite's implicit transaction has not been committed when the leg insert
    raises -- `write`'s rollback must undo the header write too, not just
    leave the legs missing. `sqlite3.Connection.executemany` cannot be
    monkeypatched directly (it is a read-only C-level attribute), so this
    forces the failure through a Connection subclass instead.
    """

    class BoomConnection(sqlite3.Connection):
        def executemany(self, sql, params=()):
            if "INSERT INTO opportunity_legs" in sql:
                raise sqlite3.IntegrityError("forced failure for atomicity test")
            return super().executemany(sql, params)

    path = tmp_path / "atomic.db"
    setup = db.connect(path)
    db.init_db(setup)
    theories.register(setup, "t1", "Theory One", "theories/t1", now=TS)
    setup.close()

    boom_conn = sqlite3.connect(str(path), timeout=30.0, factory=BoomConnection)
    boom_conn.row_factory = sqlite3.Row
    boom_conn.execute("PRAGMA foreign_keys = ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            _basket(boom_conn)

        assert boom_conn.execute(
            "SELECT COUNT(*) FROM opportunities"
        ).fetchone()[0] == 0
        assert boom_conn.execute(
            "SELECT COUNT(*) FROM opportunity_legs"
        ).fetchone()[0] == 0
    finally:
        boom_conn.close()
