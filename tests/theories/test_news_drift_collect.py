from __future__ import annotations

import json
import sqlite3

import pytest


def _market(ticker, status, **updates):
    row = {
        "ticker": ticker,
        "event_ticker": f"E-{ticker}",
        "series_ticker": "S1",
        "status": status,
        "close_time": "2026-08-10T00:00:00Z",
        "volume_fp": "0.00",
        "result": "",
    }
    row.update(updates)
    return row


def _current_candle(ts):
    return {
        "end_period_ts": ts,
        "yes_bid": {"close_dollars": "0.40"},
        "yes_ask": {"close_dollars": "0.44"},
        "price": {"close_dollars": "0.42", "mean_dollars": "0.41"},
        "volume_fp": "12.50",
        "open_interest_fp": "201.25",
    }


def _historical_candle(ts):
    return {
        "end_period_ts": ts,
        "yes_bid": {"close": "0.30"},
        "yes_ask": {"close": "0.35"},
        "price": {"close": "0.32", "mean": "0.33"},
        "volume": "7.00",
        "open_interest": "150.00",
    }


def test_collection_pages_both_market_tiers_and_keeps_every_status(tmp_path):
    """Dropping untraded/unresolved rows or one page must fail this test."""
    from theories.news_drift import collect_charts as subject

    calls = []
    live_pages = {
        "": {"markets": [
            _market("OPEN-ZERO", "active"),
            _market("PAUSED-NULL", "inactive", yes_bid_dollars=None),
            _market("DUP", "finalized", result="yes"),
        ], "cursor": "live-2"},
        "live-2": {"markets": [
            _market("DUP", "finalized", result="yes"),
            _market("CLOSED", "closed"),
        ], "cursor": ""},
    }
    historical_pages = {
        "": {"markets": [
            _market("ARCHIVED", "finalized", result="no"),
            _market("DUP", "finalized", result="yes"),
        ], "cursor": ""},
    }

    def fetch(url, params=None, timeout=30):
        params = dict(params or {})
        calls.append((url, params))
        if url.endswith("/series/S1"):
            return {"series": {"ticker": "S1", "category": "Entertainment"}}
        if url.endswith("/historical/markets"):
            return historical_pages[params.get("cursor", "")]
        if url.endswith("/markets"):
            assert "status" not in params
            return live_pages[params.get("cursor", "")]
        if url.endswith("/markets/candlesticks"):
            tickers = params["market_tickers"].split(",")
            return {"markets": [
                {"market_ticker": ticker, "candlesticks": []}
                for ticker in tickers
            ]}
        if "/historical/markets/" in url and url.endswith("/candlesticks"):
            ticker = url.split("/")[-2]
            return {"ticker": ticker, "candlesticks": []}
        raise AssertionError((url, params))

    result = subject.collect(tmp_path, fetch=fetch, series=("S1",))

    conn = sqlite3.connect(tmp_path / "history.db")
    rows = conn.execute(
        "SELECT ticker, payload FROM settled_markets ORDER BY ticker"
    ).fetchall()
    conn.close()
    assert [ticker for ticker, _ in rows] == [
        "ARCHIVED", "CLOSED", "DUP", "OPEN-ZERO", "PAUSED-NULL"
    ]
    assert json.loads(rows[3][1])["volume_fp"] == "0.00"
    assert json.loads(rows[4][1])["yes_bid_dollars"] is None
    assert result["markets"]["unique"] == 5
    assert result["markets"]["duplicates"] == 2
    assert result["markets"]["statuses"] == {
        "active": 1, "closed": 1, "finalized": 2, "inactive": 1
    }
    assert len(list((tmp_path / "raw" / "markets" / "live" / "S1").glob("*.json"))) == 2
    assert len(list((tmp_path / "raw" / "markets" / "historical" / "S1").glob("*.json"))) == 1
    listing_calls = [c for c in calls if c[0].endswith(("/markets", "/historical/markets"))]
    assert all("status" not in params for _, params in listing_calls)
    assert result["coverage_complete"] is True


def test_current_batch_and_historical_candles_record_empty_and_missing(tmp_path):
    """An explicit empty result is data; an omitted requested ticker is missing."""
    from theories.news_drift import collect_charts as subject

    start, end = subject.START_TS, subject.END_TS
    markets = {
        "CURRENT": {"raw": _market("CURRENT", "active"), "series_ticker": "S1",
                    "sources": ["live"]},
        "MISSING": {"raw": _market("MISSING", "active"), "series_ticker": "S1",
                    "sources": ["live"]},
        "HIST": {"raw": _market("HIST", "finalized", result="yes"),
                 "series_ticker": "S1", "sources": ["historical"]},
    }
    calls = []

    def fetch(url, params=None, timeout=30):
        params = dict(params or {})
        calls.append((url, params))
        if url.endswith("/markets/candlesticks"):
            assert params == {
                "market_tickers": "CURRENT,MISSING",
                "start_ts": start,
                "end_ts": end,
                "period_interval": 1440,
            }
            return {"markets": [
                {"market_ticker": "CURRENT", "candlesticks": []},
            ]}
        if url.endswith("/historical/markets/HIST/candlesticks"):
            assert params == {"start_ts": start, "end_ts": end,
                              "period_interval": 1440}
            return {"ticker": "HIST", "candlesticks": [_historical_candle(start)]}
        raise AssertionError((url, params))

    conn = subject.connect_cache(tmp_path / "history.db")
    try:
        stats = subject.collect_candles(
            markets, conn, tmp_path / "raw" / "candles", fetch=fetch
        )
    finally:
        conn.close()

    conn = sqlite3.connect(tmp_path / "history.db")
    stored = dict(conn.execute("SELECT ticker, payload FROM candles"))
    conn.close()
    assert json.loads(stored["CURRENT"]) == []
    assert json.loads(stored["HIST"]) == [{
        "end_ts": start,
        "open": None,
        "high": None,
        "low": None,
        "close": 0.32,
        "mean": 0.33,
        "yes_bid_close": 0.30,
        "yes_ask_close": 0.35,
        "volume": 7.0,
        "open_interest": 150.0,
    }]
    assert "MISSING" not in stored
    assert stats["requested"] == 3
    assert stats["stored"] == 2
    assert stats["empty"] == 1
    assert stats["missing_requests"] == ["MISSING"]


def test_normalization_rejects_candles_outside_the_frozen_window():
    """A response outside the requested dates must not leak into replay."""
    from theories.news_drift import collect_charts as subject

    with pytest.raises(ValueError, match="outside frozen window"):
        subject.normalize_candles([_current_candle(subject.END_TS + 1)])

    malformed = _current_candle(subject.START_TS)
    malformed["end_period_ts"] = "not-a-timestamp"
    with pytest.raises(ValueError, match="end_period_ts"):
        subject.normalize_candles([malformed])


def test_calendar_disjoint_markets_are_explicit_empty_without_historical_calls(tmp_path):
    """Availability pruning must save the denominator and avoid archived calls."""
    from theories.news_drift import collect_charts as subject

    before = _market(
        "BEFORE", "finalized", result="no",
        open_time="2025-01-01T00:00:00Z",
        close_time="2026-05-31T23:59:59Z",
    )
    after = _market(
        "AFTER", "active",
        open_time="2026-08-18T00:00:00Z",
        close_time="2026-09-01T00:00:00Z",
    )
    inside = _market(
        "INSIDE", "active",
        open_time="2026-07-01T00:00:00Z",
        close_time="2026-08-10T00:00:00Z",
    )
    markets = {
        "BEFORE": {"raw": before, "series_ticker": "S1",
                   "sources": ["historical"]},
        "AFTER": {"raw": after, "series_ticker": "S1", "sources": ["live"]},
        "INSIDE": {"raw": inside, "series_ticker": "S1", "sources": ["live"]},
    }
    calls = []

    def fetch(url, params=None, timeout=30):
        calls.append(url)
        if url.endswith("/markets/candlesticks"):
            return {"markets": [
                {"market_ticker": "INSIDE", "candlesticks": []},
            ]}
        raise AssertionError(f"calendar-disjoint market was fetched: {url}")

    conn = subject.connect_cache(tmp_path / "history.db")
    try:
        stats = subject.collect_candles(
            markets, conn, tmp_path / "raw", fetch=fetch
        )
    finally:
        conn.close()

    conn = sqlite3.connect(tmp_path / "history.db")
    stored = dict(conn.execute("SELECT ticker, payload FROM candles"))
    conn.close()
    assert set(stored) == {"AFTER", "BEFORE", "INSIDE"}
    assert all(json.loads(stored[ticker]) == [] for ticker in stored)
    assert calls == [calls[0]]
    assert calls[0].endswith("/markets/candlesticks")
    assert stats["missing_requests"] == []
    assert stats["excluded_by_calendar_availability"] == {
        "closed_at_or_before_window": 1,
        "opened_at_or_after_window": 1,
    }


def test_complete_zero_market_enumeration_is_not_a_collection_failure(tmp_path):
    """A terminal empty page is a complete denominator, not a missing page."""
    from theories.news_drift import collect_charts as subject

    def fetch(url, params=None, timeout=30):
        if url.endswith("/series/S1"):
            return {"series": {"ticker": "S1", "category": "Entertainment"}}
        if url.endswith(("/markets", "/historical/markets")):
            return {"markets": [], "cursor": ""}
        raise AssertionError(url)

    result = subject.collect(tmp_path, fetch=fetch, series=("S1",))

    assert result["markets"]["unique"] == 0
    assert result["candles"]["requested"] == 0
    assert result["coverage_complete"] is True
    assert json.loads((tmp_path / "denominator.json").read_text())["tickers"] == []


def test_repeated_pagination_cursor_stops_instead_of_looping(tmp_path):
    """A stuck API cursor must leave a visible partial capture and abort."""
    from theories.news_drift import collect_charts as subject

    def fetch(url, params=None, timeout=30):
        if url.endswith("/markets"):
            return {"markets": [], "cursor": "stuck"}
        raise AssertionError(url)

    with pytest.raises(RuntimeError, match="same cursor"):
        subject.paginated_markets(
            "S1", "live", tmp_path, fetch=fetch
        )
    assert (tmp_path / "page-0001.json").exists()
    assert (tmp_path / "page-0002.json").exists()


def test_category_metadata_records_conflicts_without_inventing_a_category(tmp_path):
    """A changed/missing exchange category must remain visible to the campaign."""
    from theories.news_drift import collect_charts as subject

    def fetch(url, params=None, timeout=30):
        ticker = url.rsplit("/", 1)[-1]
        category = "Economics" if ticker == "S2" else None
        return {"series": {"ticker": ticker, "category": category}}

    artifact = subject.collect_series_metadata(
        ("S1", "S2"), tmp_path, fetch=fetch
    )

    assert artifact["categories"] == {"S2": "Economics"}
    assert artifact["conflicts"] == {"S1": None, "S2": "Economics"}


def test_collection_reuses_a_frozen_inventory_without_refetching_it(tmp_path):
    """A longer candle window must retain the exact prior market census."""
    from theories.news_drift import collect_charts as subject

    source = tmp_path / "short"

    def empty_inventory(url, params=None, timeout=30):
        if url.endswith("/series/S1"):
            return {"series": {"ticker": "S1", "category": "Entertainment"}}
        if url.endswith(("/markets", "/historical/markets")):
            return {"markets": [], "cursor": ""}
        raise AssertionError(url)

    subject.collect(source, fetch=empty_inventory, series=("S1",))
    original = (source / "raw" / "markets" / "live" / "S1" /
                "page-0001.json").read_bytes()

    def no_network(url, params=None, timeout=30):
        raise AssertionError(f"frozen inventory was refetched: {url}")

    destination = tmp_path / "long"
    result = subject.collect(
        destination,
        fetch=no_network,
        series=("S1",),
        start_ts=10,
        end_ts=20,
        inventory_from=source,
    )

    copied = (destination / "raw" / "markets" / "live" / "S1" /
              "page-0001.json").read_bytes()
    assert copied == original
    assert result["protocol"] == "ND-1"
    assert result["campaign"] == "long"
    assert result["inventory_reused_from"] == str(source.resolve())
    assert result["inventory_tree_sha256"]
    assert result["window"]["start_ts"] == 10
    assert result["window"]["end_ts"] == 20


def test_custom_window_controls_requests_pruning_and_database_bounds(tmp_path):
    """Hardcoded short-campaign dates must not leak into the long capture."""
    from theories.news_drift import collect_charts as subject

    start, end = 100, 200
    markets = {
        "INSIDE": {
            "raw": _market(
                "INSIDE", "active",
                open_time="1970-01-01T00:02:00Z",
                close_time="1970-01-01T00:03:00Z",
            ),
            "series_ticker": "S1", "sources": ["live"],
        },
        "BEFORE": {
            "raw": _market(
                "BEFORE", "finalized",
                open_time="1970-01-01T00:00:01Z",
                close_time="1970-01-01T00:01:40Z",
            ),
            "series_ticker": "S1", "sources": ["historical"],
        },
    }

    def fetch(url, params=None, timeout=30):
        assert params["start_ts"] == start
        assert params["end_ts"] == end
        return {"markets": [
            {"market_ticker": "INSIDE", "candlesticks": []},
        ]}

    conn = subject.connect_cache(tmp_path / "history.db")
    try:
        stats = subject.collect_candles(
            markets, conn, tmp_path / "raw", fetch=fetch,
            start_ts=start, end_ts=end,
        )
    finally:
        conn.close()

    conn = sqlite3.connect(tmp_path / "history.db")
    bounds = set(conn.execute("SELECT start_ts, end_ts FROM candles"))
    conn.close()
    assert bounds == {(start, end)}
    assert stats["excluded_by_calendar_availability"] == {
        "closed_at_or_before_window": 1,
    }
