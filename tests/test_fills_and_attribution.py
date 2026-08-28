"""Taking a bet names its theory, and every fill is kept."""

import pytest

from tools import db, ledger, theories
from tools.sizing import fee_pts

TS = "2026-08-26T12:00:00Z"
TS2 = "2026-08-29T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    for slug in ("t1", "t2"):
        theories.register(c, slug, slug, f"theories/{slug}", now=TS)
    yield c
    c.close()


def _rec(conn, theory="t1", ticker="A", price=0.60):
    opp, _ = ledger.record_opportunity(
        conn, theory_id=theory, theory_version=1, kalshi_ticker=ticker,
        outcome="yes", entry_price=price, edge_pts_net=6.0, now=TS,
    )
    return opp


def test_taking_a_bet_requires_naming_the_theory(conn):
    opp = _rec(conn)
    with pytest.raises(ValueError, match="--theory"):
        ledger.mark_user_action(conn, opp, "taken", size=25)


def test_naming_the_wrong_theory_raises(conn):
    opp = _rec(conn, theory="t1")
    with pytest.raises(ValueError, match="t2"):
        ledger.mark_user_action(
            conn, opp, "taken", size=25, theory_id="t2"
        )


def test_skipping_does_not_require_a_theory(conn):
    opp = _rec(conn)
    ledger.mark_user_action(conn, opp, "skipped", reason="too thin")
    assert ledger.get_opportunity(conn, opp)["user_action"] == "skipped"


def test_a_second_theory_cannot_also_take_the_same_market(conn):
    a = _rec(conn, theory="t1")
    b = _rec(conn, theory="t2")
    ledger.mark_user_action(conn, a, "taken", size=25, theory_id="t1", now=TS)
    with pytest.raises(ValueError, match="already taken"):
        ledger.mark_user_action(
            conn, b, "taken", size=25, theory_id="t2", now=TS
        )


def test_two_fills_are_both_kept(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, price=0.80, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, price=0.90, theory_id="t1", now=TS2,
    )
    got = [(f["filled_on"], f["size"], f["price"])
           for f in ledger.fills(conn, opp)]
    assert got == [("2026-08-26", 25.0, 0.80), ("2026-08-29", 10.0, 0.90)]


def test_user_size_is_the_sum_of_fills(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, theory_id="t1", now=TS2,
    )
    row = ledger.get_opportunity(conn, opp)
    assert row["user_size"] == 35.0
    assert row["user_action"] == "taken"


def test_unmarking_clears_the_fills(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(conn, opp, "untouched")
    assert ledger.fills(conn, opp) == []
    row = ledger.get_opportunity(conn, opp)
    assert row["user_action"] == "untouched"
    assert row["user_size"] is None


def test_unmarking_also_clears_the_reason(conn):
    """A stale reason must not survive onto an untouched row.

    compare-theories mines divergences off any row with a non-NULL
    user_reason and does not check user_action at all -- so a reason left
    behind by an earlier skip/take would be mined as a live divergence
    signal for a position the user is no longer in.
    """
    opp = _rec(conn)
    ledger.mark_user_action(conn, opp, "skipped", reason="too thin")
    ledger.mark_user_action(conn, opp, "untouched")
    row = ledger.get_opportunity(conn, opp)
    assert row["user_reason"] is None
    assert row["user_size"] is None
    assert ledger.fills(conn, opp) == []


def test_fill_price_rejects_cents(conn):
    opp = _rec(conn)
    with pytest.raises(ValueError, match="entry_price"):
        ledger.mark_user_action(
            conn, opp, "taken", size=25, price=85, theory_id="t1", now=TS,
        )


def test_fill_price_accepts_decimal_dollars(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, price=0.85, theory_id="t1", now=TS,
    )
    got = ledger.fills(conn, opp)
    assert got[0]["price"] == pytest.approx(0.85)


def test_fill_price_may_be_omitted(conn):
    opp = _rec(conn)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, theory_id="t1", now=TS,
    )
    got = ledger.fills(conn, opp)
    assert got[0]["price"] is None


def test_roi_taken_uses_the_price_actually_paid(conn):
    from tools import score

    opp = _rec(conn, ticker="A", price=0.50)
    score.record_settlement(conn, "A", "yes", resolved_at=TS)
    # Proposed at 0.50, actually bought at 0.25. ROI must reflect the 0.25.
    ledger.mark_user_action(
        conn, opp, "taken", size=10, price=0.25, theory_id="t1", now=TS,
    )
    result = score.compute_score(conn, "t1", 1)
    # Pinned exactly, not just bounded -- the exact value also pins the
    # fee handling, which a loose bound would let drift unnoticed.
    cost = 0.25 + fee_pts(0.25) / 100.0
    assert result["roi_taken"] == pytest.approx((1.0 - cost) / cost)


def test_roi_taken_falls_back_to_the_proposed_ask(conn):
    from tools import score

    opp = _rec(conn, ticker="B", price=0.50)
    score.record_settlement(conn, "B", "yes", resolved_at=TS)
    ledger.mark_user_action(
        conn, opp, "taken", size=10, theory_id="t1", now=TS,
    )
    result = score.compute_score(conn, "t1", 1)
    assert 0.8 < result["roi_taken"] < 1.0


def test_roi_taken_weights_multiple_fills_by_size(conn):
    """The expression this task exists to add: a position bought in two
    fills of different sizes and prices must land on the size-weighted
    average, not the naive mean of the two prices -- 25 @ 0.80 and 10 @
    0.90 average to 0.8286, not 0.85.
    """
    from tools import score

    opp = _rec(conn, ticker="C", price=0.50)
    score.record_settlement(conn, "C", "yes", resolved_at=TS)
    ledger.mark_user_action(
        conn, opp, "taken", size=25, price=0.80, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, price=0.90, theory_id="t1", now=TS2,
    )
    obs = score._single_leg_observations(conn, "t1", 1, "live", "all", None)
    assert len(obs) == 1
    weighted = (25 * 0.80 + 10 * 0.90) / 35
    assert obs[0]["fill_price"] == pytest.approx(weighted)
    # Not the naive mean -- confirms the fixture actually distinguishes
    # weighted-by-size from an unweighted average.
    assert weighted != pytest.approx((0.80 + 0.90) / 2)

    result = score.compute_score(conn, "t1", 1)
    cost = weighted + fee_pts(weighted) / 100.0
    assert result["roi_taken"] == pytest.approx((1.0 - cost) / cost)


def test_roi_taken_blends_a_partially_priced_fill_at_the_reference_price(
    conn,
):
    """One fill records a price, the other doesn't. The unpriced fill
    still contributes its size to the weighted average -- at the
    position's own reference price, the same one a fully-unpriced
    position falls back to -- rather than being dropped from the blend
    or treated as free.
    """
    from tools import score

    opp = _rec(conn, ticker="D", price=0.50)
    score.record_settlement(conn, "D", "yes", resolved_at=TS)
    ledger.mark_user_action(
        conn, opp, "taken", size=10, price=0.30, theory_id="t1", now=TS,
    )
    ledger.mark_user_action(
        conn, opp, "taken", size=10, theory_id="t1", now=TS2,
    )
    obs = score._single_leg_observations(conn, "t1", 1, "live", "all", None)
    assert len(obs) == 1
    weighted = (10 * 0.30 + 10 * 0.50) / 20  # unpriced fill blends at 0.50
    assert obs[0]["fill_price"] == pytest.approx(weighted)
