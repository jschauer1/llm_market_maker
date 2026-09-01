import pytest

from tools.kalshi import trades

RAW_TRADE = {
    "count_fp": "32.80",
    "created_time": "2026-09-01T06:10:34.9916Z",
    "is_block_trade": False,
    "no_price_dollars": "0.5600",
    "taker_book_side": "bid",
    "taker_outcome_side": "yes",
    "taker_side": "yes",
    "ticker": "KXNFLWINS-27BAL-12",
    "trade_id": "07213506-e161-8abd-8870-402c00589d3f",
    "yes_price_dollars": "0.4400",
}

RAW_NO_TRADE = dict(
    RAW_TRADE,
    taker_side="no",
    taker_outcome_side="no",
    taker_book_side="ask",
    trade_id="no-side-trade",
)


def test_normalize_reads_prices_and_size():
    trade = trades.normalize(RAW_TRADE)
    assert trade.taker_side == "yes"
    assert trade.yes_price == pytest.approx(0.44)
    assert trade.no_price == pytest.approx(0.56)
    assert trade.count == pytest.approx(32.80)
    assert trade.is_block_trade is False
    assert trade.raw is RAW_TRADE


def test_normalize_accepts_both_measured_taker_shapes():
    assert trades.normalize(RAW_TRADE).taker_side == "yes"
    assert trades.normalize(RAW_NO_TRADE).taker_side == "no"


def test_normalize_raises_on_unmeasured_taker_shape():
    """The aggressor side is the whole value of this feed.

    A combination outside the two measured shapes means the collinearity
    that lets three fields collapse to one bit no longer holds, so this
    must fail loudly rather than record a side that means something else.
    """
    drifted = dict(RAW_TRADE, taker_book_side="ask")
    with pytest.raises(ValueError, match="taker field combination"):
        trades.normalize(drifted)


def test_normalize_raises_on_unparseable_price():
    with pytest.raises(ValueError, match="yes_price_dollars"):
        trades.normalize(dict(RAW_TRADE, yes_price_dollars="cheap"))


def test_trades_pages_until_cursor_runs_out():
    pages = [
        {"trades": [RAW_TRADE], "cursor": "c1"},
        {"trades": [RAW_NO_TRADE], "cursor": ""},
    ]
    calls = []

    def fake(url, params):
        calls.append(params)
        return pages[len(calls) - 1]

    rows = trades.trades("T", fetch=fake, max_pages=10)
    assert [r.taker_side for r in rows] == ["yes", "no"]
    assert "cursor" not in calls[0]
    assert calls[1]["cursor"] == "c1"


def test_trades_stops_at_max_pages():
    def fake(url, params):
        return {"trades": [RAW_TRADE], "cursor": f"c{params.get('cursor', '0')}"}

    rows = trades.trades("T", fetch=fake, max_pages=3)
    assert len(rows) == 3


def test_trades_raises_when_cursor_stops_advancing():
    def fake(url, params):
        return {"trades": [RAW_TRADE], "cursor": "stuck"}

    with pytest.raises(trades.TradeFetchError, match="stopped advancing"):
        trades.trades("T", fetch=fake, max_pages=10)


def test_imbalance_is_volume_weighted_not_trade_counted():
    """One 300-lot must not read the same as three 1-lots."""
    rows = [
        trades.normalize(dict(RAW_TRADE, count_fp="300", trade_id="a")),
        trades.normalize(dict(RAW_NO_TRADE, count_fp="1", trade_id="b")),
        trades.normalize(dict(RAW_NO_TRADE, count_fp="1", trade_id="c")),
        trades.normalize(dict(RAW_NO_TRADE, count_fp="1", trade_id="d")),
    ]
    assert trades.imbalance(rows) == pytest.approx((300 - 3) / 303)


def test_imbalance_is_none_without_volume():
    assert trades.imbalance([]) is None
    zero = [trades.normalize(dict(RAW_TRADE, count_fp="0"))]
    assert trades.imbalance(zero) is None


def test_imbalance_signs_point_at_the_aggressor():
    yes_only = [trades.normalize(RAW_TRADE)]
    no_only = [trades.normalize(RAW_NO_TRADE)]
    assert trades.imbalance(yes_only) == pytest.approx(1.0)
    assert trades.imbalance(no_only) == pytest.approx(-1.0)
