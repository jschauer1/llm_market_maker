"""Prevent settlement leakage and stale/future quote use in ND-1 replay."""
from datetime import datetime, timezone

import pytest


def test_reconstruction_keeps_terminal_prices_and_outcomes_out_of_screen():
    from theories.news_drift.data import reconstruct

    raw = {"ticker": "KXTEST-26A-Y", "event_ticker": "KXTEST-26A",
           "title": "Test", "result": "yes", "status": "settled",
           "yes_bid_dollars": "1", "yes_ask_dollars": "1",
           "volume_fp": "99999", "close_time": "2026-08-03T00:00:00Z",
           "settlement_value_dollars": "1", "expiration_value": "leaky"}
    candles = [{"end_ts": 100, "yes_bid_close": .39,
                "yes_ask_close": .43, "volume": 12, "open_interest": 200},
               {"end_ts": 200, "yes_bid_close": .9,
                "yes_ask_close": .95, "volume": 90, "open_interest": 900}]
    market = reconstruct(raw, candles, "Politics", 100)
    assert market.yes_bid == .39
    assert market.yes_ask == .43
    assert market.no_ask == pytest.approx(.61)
    assert market.open_interest == 200
    assert market.volume is None  # a daily candle is not lifetime volume
    assert market.volume_24h == 12
    assert market.result is None
    assert market.close_time is None  # realized close is not a known deadline
    assert market.raw == {}
    assert market.is_open
    assert reconstruct(raw, candles, "Politics", 99) is None


@pytest.mark.parametrize("close", ["1970-01-01T00:01:40Z",
                                    "1970-01-01T00:01:39Z", None, "unknown"])
def test_historical_entry_must_precede_actual_trading_close(close):
    from theories.news_drift.data import reconstruct

    raw = {"ticker": "KXTEST-A-Y", "close_time": close}
    candle = {"end_ts": 100, "yes_bid_close": .4, "yes_ask_close": .44}
    assert reconstruct(raw, [candle], "Politics", 100) is None


def test_live_history_normalizes_quotes_and_excludes_incomplete_candle(tmp_path):
    from theories.news_drift.data import load_live_history
    from tools.domain import Market

    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    ts = int(now.timestamp())
    calls = []

    def fetch(url, params=None, timeout=30):
        calls.append((url, params))
        return {"candlesticks": [
            {"end_period_ts": ts, "yes_bid": {"close_dollars": ".4"},
             "yes_ask": {"close_dollars": ".44"}, "volume_fp": "30",
             "open_interest_fp": "400"},
            {"end_period_ts": ts + 86400, "yes_bid": {"close_dollars": ".9"},
             "yes_ask": {"close_dollars": ".94"}, "volume_fp": "300",
             "open_interest_fp": "4000"}]}

    market = Market("kalshi", "KXTEST-A-Y", series_ticker="KXTEST")
    rows = load_live_history(market, now, fetch=fetch, cache_dir=tmp_path)
    assert [r["end_ts"] for r in rows] == [ts]
    assert rows[0]["yes_ask_close"] == .44
    assert rows[0]["volume"] == 30
    assert calls[0][1]["end_ts"] == ts
    assert load_live_history(market, now, fetch=fetch, cache_dir=tmp_path) == rows
    assert len(calls) == 1


def test_training_requires_outcomes_known_before_cutoff_and_deduplicates():
    from theories.news_drift.analysis import fit_calibration

    rows = [{"ticker": f"T-{i}", "event_ticker": f"E-{i}",
             "entry_ts": 100, "resolved_ts": 150, "side": "yes",
             "result": "yes", "directional_mid": .7} for i in range(30)]
    # Terminal outcomes observed later may never fit an earlier forecast.
    late = dict(rows[0], ticker="LATE", entry_ts=100, resolved_ts=300,
                result="no")
    future = dict(late, ticker="FUTURE", entry_ts=250, resolved_ts=260)
    pending = dict(late, ticker="PENDING", result=None, resolved_ts=None)
    result = fit_calibration(rows + rows + [late, future, pending], cutoff_ts=200,
                             source_digest="a" * 64)
    assert result["n"] == 30
    assert result["event_clusters"] == 30
    assert result["residual"] == pytest.approx(.3)
    assert result["eligible_for_production"] is False


def test_cluster_uncertainty_does_not_treat_siblings_as_independent():
    from theories.news_drift.analysis import cluster_interval

    rows = [{"event_ticker": "A", "net": 10},
            {"event_ticker": "B", "net": -10},
            {"event_ticker": "C", "net": 0}]
    single = cluster_interval(rows, "net", "event_ticker")
    siblings = cluster_interval(rows * 100, "net", "event_ticker")
    assert siblings["clusters"] == 3
    assert siblings["se"] == pytest.approx(single["se"])
    assert siblings["interval"] == pytest.approx(single["interval"])


def test_positive_gross_edge_can_lose_after_payable_ask_and_rounded_fee():
    from theories.news_drift.analysis import measure

    # 61 wins / 100 vs .60 mid is +1 point gross, but .61 ask plus fees loses.
    rows = [{"ticker": f"T-{i}", "event_ticker": f"E-{i}",
             "settlement_day": f"2026-08-{i % 20 + 1:02d}",
             "result": "yes" if i < 61 else "no", "side": "yes",
             "directional_mid": .6, "entry_price": .61,
             "reverse_price": .41} for i in range(100)]
    stats = measure(rows)
    assert stats["gross_mid_pts"] == pytest.approx(1)
    assert stats["net_pts"] < 0
    assert stats["net_one_contract_pts"] == pytest.approx(-2)
    assert stats["reversal"]["net_pts"] < 0


def test_pending_outcomes_are_kept_as_bounds_not_silently_scored_losses():
    from theories.news_drift.analysis import summarize

    rows = [{"ticker": "A", "event_ticker": "E1", "settlement_day": "2026-08-01",
             "side": "no", "result": "no", "entry_price": .5,
             "directional_mid": .49, "reverse_price": .52},
            {"ticker": "B", "event_ticker": "E2", "settlement_day": None,
             "side": "yes", "result": None, "entry_price": .5,
             "directional_mid": .49, "reverse_price": .52}]
    result = summarize(rows)
    assert result["total_n"] == 2
    assert result["n"] == 1
    assert result["pending_n"] == 1
    assert result["net_pts"] == 48.25  # realized row, not the full portfolio
    assert result["pending_worst_case_net_pts"] == -1.75
    assert result["pending_best_case_net_pts"] == 48.25
    assert result["positive_statistical_bar"] is False
