import time

import pytest

from tools.kalshi import history

RAW_CANDLE = {
    "end_period_ts": 1784952000,
    "open_interest_fp": "38434.75",
    "volume_fp": "236.31",
    "price": {
        "open_dollars": "0.8500",
        "high_dollars": "0.8600",
        "low_dollars": "0.8400",
        "close_dollars": "0.8500",
        "mean_dollars": "0.8500",
    },
    "yes_bid": {"close_dollars": "0.8300"},
    "yes_ask": {"close_dollars": "0.8600"},
}


def test_candlesticks_normalizes_nested_prices(monkeypatch):
    monkeypatch.setattr(
        history, "get_json",
        lambda *a, **k: {"candlesticks": [RAW_CANDLE]},
    )
    candles = history.candlesticks("S", "T", 0, 100)
    candle = candles[0]
    assert candle["close"] == pytest.approx(0.85)
    assert candle["high"] == pytest.approx(0.86)
    assert candle["yes_bid_close"] == pytest.approx(0.83)
    assert candle["yes_ask_close"] == pytest.approx(0.86)
    assert candle["volume"] == pytest.approx(236.31)
    assert candle["end_ts"] == 1784952000


def test_candlesticks_sorts_ascending(monkeypatch):
    late = dict(RAW_CANDLE, end_period_ts=200)
    early = dict(RAW_CANDLE, end_period_ts=100)
    monkeypatch.setattr(
        history, "get_json",
        lambda *a, **k: {"candlesticks": [late, early]},
    )
    assert [c["end_ts"] for c in history.candlesticks("S", "T", 0, 300)] == \
        [100, 200]


def test_candlesticks_rejects_invalid_interval():
    with pytest.raises(ValueError, match="period_interval"):
        history.candlesticks("S", "T", 0, 100, period_interval=5)


def test_candlesticks_handles_empty_response(monkeypatch):
    monkeypatch.setattr(history, "get_json", lambda *a, **k: {})
    assert history.candlesticks("S", "T", 0, 100) == []


def test_candlesticks_tolerates_missing_bid_ask(monkeypatch):
    raw = {k: v for k, v in RAW_CANDLE.items() if k not in ("yes_bid", "yes_ask")}
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": [raw]}
    )
    candle = history.candlesticks("S", "T", 0, 100)[0]
    assert candle["yes_bid_close"] is None
    assert candle["yes_ask_close"] is None
    assert candle["close"] == pytest.approx(0.85)


def test_candlesticks_raises_on_missing_end_period_ts(monkeypatch):
    raw = {k: v for k, v in RAW_CANDLE.items() if k != "end_period_ts"}
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": [raw]}
    )
    with pytest.raises(ValueError, match="end_period_ts"):
        history.candlesticks("S", "T", 0, 100)


def test_candlesticks_raises_on_unparseable_close_price(monkeypatch):
    raw = dict(RAW_CANDLE)
    raw["price"] = dict(raw["price"], close_dollars="not-a-number")
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": [raw]}
    )
    with pytest.raises(ValueError, match="close_dollars"):
        history.candlesticks("S", "T", 0, 100)


def test_point_in_time_returns_the_last_candle_at_or_before(monkeypatch):
    candles = [
        dict(RAW_CANDLE, end_period_ts=100),
        dict(RAW_CANDLE, end_period_ts=200),
        dict(RAW_CANDLE, end_period_ts=300),
    ]
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": candles}
    )
    state = history.point_in_time("S", "T", as_of_ts=250)
    assert state["end_ts"] == 200, "must not peek at the future candle"


def test_point_in_time_includes_the_exact_boundary(monkeypatch):
    candles = [dict(RAW_CANDLE, end_period_ts=100),
               dict(RAW_CANDLE, end_period_ts=200)]
    monkeypatch.setattr(
        history, "get_json", lambda *a, **k: {"candlesticks": candles}
    )
    assert history.point_in_time("S", "T", as_of_ts=200)["end_ts"] == 200


def test_point_in_time_returns_none_when_nothing_precedes(monkeypatch):
    monkeypatch.setattr(
        history, "get_json",
        lambda *a, **k: {"candlesticks": [dict(RAW_CANDLE,
                                               end_period_ts=500)]},
    )
    assert history.point_in_time("S", "T", as_of_ts=100) is None


def test_point_in_time_returns_none_for_no_data(monkeypatch):
    monkeypatch.setattr(history, "get_json", lambda *a, **k: {})
    assert history.point_in_time("S", "T", as_of_ts=100) is None


@pytest.mark.network
def test_live_candlesticks_reach_back_months():
    now = int(time.time())
    candles = history.candlesticks(
        "KXOAIANTH", "KXOAIANTH-40-ANTH",
        start_ts=now - 86400 * 180, end_ts=now, period_interval=1440,
    )
    assert len(candles) > 100, "expected months of daily history"
    assert candles[0]["end_ts"] < candles[-1]["end_ts"]
    assert any(c["yes_ask_close"] is not None for c in candles), \
        "historical ask is required for executable backtest prices"
