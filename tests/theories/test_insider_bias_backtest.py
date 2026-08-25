"""insider_bias — the tier A stage-1-screen-only backtest machinery.

No test here hits the network: `is_candidate` and `systematic_sample` are
pure; `replay_market`, `candidate_series`, and `iter_settled_survivors` are
each exercised against a monkeypatched network call so the real filtering
and reconstruction logic runs without an HTTP call.
"""

from datetime import datetime, timezone

import pytest

from theories.insider_bias.insider_judgment import backtest


def _settled(**overrides):
    base = {
        "ticker": "KXTRAITORS-26-WINNER",
        "event_ticker": "KXTRAITORS-26",
        "volume_fp": "5000.00",
        "close_time": "2026-08-30T00:00:00Z",
        "result": "yes",
    }
    base.update(overrides)
    return base


# --- is_candidate: the safe, no-network pre-filter ---------------------


def test_is_candidate_rejects_excluded_families():
    assert backtest.is_candidate(_settled(ticker="KXNFLGAME-26")) is False


def test_is_candidate_rejects_thin_final_volume():
    assert backtest.is_candidate(_settled(volume_fp="10.00")) is False


def test_is_candidate_accepts_a_plausible_market():
    assert backtest.is_candidate(_settled()) is True


def test_is_candidate_treats_missing_volume_as_zero():
    raw = _settled()
    del raw["volume_fp"]
    assert backtest.is_candidate(raw) is False


def test_is_candidate_treats_garbage_volume_as_zero():
    assert backtest.is_candidate(_settled(volume_fp="not-a-number")) is False


# --- systematic_sample ---------------------------------------------------


def _mk(ticker, close_time):
    return {"ticker": ticker, "close_time": close_time}


def test_systematic_sample_returns_everything_under_the_cap():
    items = [_mk("A", "2026-08-01T00:00:00Z"), _mk("B", "2026-08-02T00:00:00Z")]
    assert backtest.systematic_sample(items, 10) == sorted(
        items, key=lambda m: m["close_time"]
    )


def test_systematic_sample_caps_at_n_and_sorts_by_close_time():
    items = [
        _mk(str(i), f"2026-08-{(i % 28) + 1:02d}T00:00:00Z")
        for i in range(100)
    ]
    sample = backtest.systematic_sample(items, 10)
    assert len(sample) == 10
    close_times = [m["close_time"] for m in sample]
    assert close_times == sorted(close_times)


def test_systematic_sample_spans_the_full_range_not_just_the_prefix():
    # A naive items[:n] would only ever see the earliest close times.
    items = [_mk(str(i), f"2026-{(i % 12) + 1:02d}-01T00:00:00Z") for i in range(120)]
    sample = backtest.systematic_sample(items, 12)
    months = sorted({m["close_time"][5:7] for m in sample})
    assert len(months) > 1


def test_systematic_sample_handles_empty_input():
    assert backtest.systematic_sample([], 10) == []


def test_systematic_sample_handles_zero_n():
    assert backtest.systematic_sample([_mk("A", "2026-08-01T00:00:00Z")], 0) == []


# --- replay_market ---------------------------------------------------


def _candle(end_ts, yes_bid, yes_ask, volume):
    return {
        "end_ts": end_ts,
        "yes_bid_close": yes_bid,
        "yes_ask_close": yes_ask,
        "volume": volume,
    }


def _ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def test_replay_market_finds_the_first_day_that_clears_the_screen(monkeypatch):
    close_ts = _ts("2026-08-30T00:00:00Z")
    day = 86400
    # Two early days below the volume floor, then a day that clears
    # everything -- 500 combined is the MIN_VOLUME threshold.
    candles = [
        _candle(close_ts - 10 * day, 0.60, 0.62, 100.0),
        _candle(close_ts - 9 * day, 0.60, 0.62, 100.0),
        _candle(close_ts - 8 * day, 0.78, 0.80, 400.0),
    ]
    monkeypatch.setattr(
        backtest.history, "candlesticks",
        lambda series, ticker, start_ts, end_ts, period_interval=1440: candles,
    )
    result = backtest.replay_market(
        _settled(close_time="2026-08-30T00:00:00Z"), "KXTRAITORS",
    )
    assert result is not None
    assert result["fav_side"] == "yes"
    assert result["entry_price"] == pytest.approx(0.80)
    # Running volume: 100 + 100 + 400 = 600, at or above MIN_VOLUME=500.
    assert result["volume_at_call"] == pytest.approx(600.0)
    assert result["entry_day_ts"] == close_ts - 8 * day


def test_replay_market_returns_none_when_never_eligible(monkeypatch):
    close_ts = _ts("2026-08-30T00:00:00Z")
    day = 86400
    candles = [_candle(close_ts - i * day, 0.60, 0.62, 10.0) for i in range(10, 0, -1)]
    monkeypatch.setattr(
        backtest.history, "candlesticks",
        lambda series, ticker, start_ts, end_ts, period_interval=1440: candles,
    )
    result = backtest.replay_market(
        _settled(close_time="2026-08-30T00:00:00Z"), "KXTRAITORS",
    )
    assert result is None


def test_replay_market_skips_days_with_no_quote(monkeypatch):
    close_ts = _ts("2026-08-30T00:00:00Z")
    day = 86400
    candles = [
        {"end_ts": close_ts - 5 * day, "yes_bid_close": None,
         "yes_ask_close": None, "volume": 900.0},
        _candle(close_ts - 4 * day, 0.78, 0.80, 900.0),
    ]
    monkeypatch.setattr(
        backtest.history, "candlesticks",
        lambda series, ticker, start_ts, end_ts, period_interval=1440: candles,
    )
    result = backtest.replay_market(
        _settled(close_time="2026-08-30T00:00:00Z"), "KXTRAITORS",
    )
    assert result is not None
    # Volume from the no-quote day still accumulates into the running total.
    assert result["volume_at_call"] == pytest.approx(1800.0)


def test_replay_market_no_side_candidate(monkeypatch):
    close_ts = _ts("2026-08-30T00:00:00Z")
    day = 86400
    candles = [_candle(close_ts - 3 * day, 0.10, 0.12, 900.0)]
    monkeypatch.setattr(
        backtest.history, "candlesticks",
        lambda series, ticker, start_ts, end_ts, period_interval=1440: candles,
    )
    result = backtest.replay_market(
        _settled(close_time="2026-08-30T00:00:00Z"), "KXTRAITORS",
    )
    assert result is not None
    assert result["fav_side"] == "no"
    assert result["entry_price"] == pytest.approx(1.0 - 0.10)


def test_replay_market_returns_none_without_a_parseable_close_time():
    assert backtest.replay_market(_settled(close_time=None), "KXTRAITORS") is None


# --- candidate_series -----------------------------------------------


def _series(ticker, category="Entertainment", days_ago=1, **overrides):
    ts = datetime.now(timezone.utc).timestamp() - days_ago * 86400
    last_updated = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    base = {"ticker": ticker, "category": category, "last_updated_ts": last_updated}
    base.update(overrides)
    return base


def test_candidate_series_drops_no_categories(monkeypatch):
    all_series = [_series("KXTRAITORS", "Entertainment"), _series("KXBTCD", "Crypto")]
    monkeypatch.setattr(
        backtest, "get_json", lambda url, params=None: {"series": all_series}
    )
    result = backtest.candidate_series()
    assert [s["ticker"] for s in result] == ["KXTRAITORS"]


def test_candidate_series_drops_excluded_ticker_prefixes(monkeypatch):
    all_series = [_series("KXTRAITORS"), _series("KXNFLGAME")]
    monkeypatch.setattr(
        backtest, "get_json", lambda url, params=None: {"series": all_series}
    )
    result = backtest.candidate_series()
    assert [s["ticker"] for s in result] == ["KXTRAITORS"]


def test_candidate_series_drops_stale_series(monkeypatch):
    all_series = [
        _series("KXFRESH", days_ago=1),
        _series("KXSTALE", days_ago=999),
    ]
    monkeypatch.setattr(
        backtest, "get_json", lambda url, params=None: {"series": all_series}
    )
    result = backtest.candidate_series(recency_days=60)
    assert [s["ticker"] for s in result] == ["KXFRESH"]


def test_candidate_series_keeps_series_with_no_category_or_timestamp(monkeypatch):
    # Erring toward inclusion on missing metadata, same as gate.py does.
    all_series = [{"ticker": "KXMYSTERY"}]
    monkeypatch.setattr(
        backtest, "get_json", lambda url, params=None: {"series": all_series}
    )
    result = backtest.candidate_series()
    assert [s["ticker"] for s in result] == ["KXMYSTERY"]


# --- iter_settled_survivors / settled_survivors -----------------------


def test_iter_settled_survivors_scopes_each_call_by_series(monkeypatch):
    calls = []

    def fake_list_settled(**kwargs):
        calls.append(kwargs["series_ticker"])
        return [_settled(ticker=f"{kwargs['series_ticker']}-1")]

    monkeypatch.setattr(backtest.markets, "list_settled", fake_list_settled)
    series_list = [{"ticker": "KXA"}, {"ticker": "KXB"}]
    results = list(backtest.iter_settled_survivors(series_list, 0, 100))

    assert calls == ["KXA", "KXB"]
    assert [t for t, _ in results] == ["KXA", "KXB"]


def test_iter_settled_survivors_tags_each_row_with_its_series(monkeypatch):
    monkeypatch.setattr(
        backtest.markets, "list_settled",
        lambda **kwargs: [_settled(ticker="X-1")],
    )
    _, survivors = next(
        backtest.iter_settled_survivors([{"ticker": "KXA"}], 0, 100)
    )
    assert survivors[0]["series_ticker"] == "KXA"


def test_iter_settled_survivors_skips_series_with_no_ticker(monkeypatch):
    calls = []
    monkeypatch.setattr(
        backtest.markets, "list_settled",
        lambda **kwargs: calls.append(kwargs) or [],
    )
    list(backtest.iter_settled_survivors([{"category": "Entertainment"}], 0, 100))
    assert calls == []


def test_settled_survivors_collects_across_all_series(monkeypatch):
    monkeypatch.setattr(
        backtest.markets, "list_settled",
        lambda **kwargs: [_settled(ticker=f"{kwargs['series_ticker']}-1")],
    )
    series_list = [{"ticker": "KXA"}, {"ticker": "KXB"}]
    result = backtest.settled_survivors(0, 100, series_list=series_list)
    assert sorted(m["ticker"] for m in result) == ["KXA-1", "KXB-1"]


def test_settled_survivors_uses_candidate_series_by_default(monkeypatch):
    monkeypatch.setattr(backtest, "candidate_series", lambda: [{"ticker": "KXA"}])
    monkeypatch.setattr(
        backtest.markets, "list_settled",
        lambda **kwargs: [_settled(ticker="KXA-1")],
    )
    result = backtest.settled_survivors(0, 100)
    assert [m["ticker"] for m in result] == ["KXA-1"]
