from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path

import pytest

from tests.theories.test_weather_model_gap import (
    ENTRY,
    STATIONS,
    dataset_for_target,
    forecast,
)
from theories.weather_model_gap.live import collect_live, load_live_dataset
from theories.weather_model_gap.run import record_collection
from tools import slices, theories


def live_raw(ticker: str, strike_type: str, floor, cap):
    raw = {
        "ticker": ticker,
        "event_ticker": "KXHIGHNY-26JUL01",
        "series_ticker": "KXHIGHNY",
        "title": ticker,
        "status": "active",
        "result": "",
        "strike_type": strike_type,
        "floor_strike": floor,
        "cap_strike": cap,
        "yes_bid_dollars": "0.39",
        "yes_ask_dollars": "0.40",
        "no_bid_dollars": "0.60",
        "no_ask_dollars": "0.61",
        "volume_fp": "10",
        "volume_24h_fp": "10",
        "open_interest_fp": "200",
        "rules_primary": (
            "The official value is reported by The Weather Company at CLINYC."
        ),
        "rules_secondary": (
            "Settlement source: The Weather Company (weather.com)."
        ),
    }
    return {k: v for k, v in raw.items() if v is not None}


def candle_payload(tickers):
    return {
        "markets": [
            {
                "market_ticker": ticker,
                "candlesticks": [{
                    "end_period_ts": int(ENTRY.timestamp()),
                    "yes_bid": {"close_dollars": "0.39"},
                    "yes_ask": {"close_dollars": "0.40"},
                    "volume_fp": "3",
                    "open_interest_fp": "200",
                }],
            }
            for ticker in tickers
        ]
    }


def fake_live_fetch(*, depth_size=12.0):
    markets = [
        live_raw("A", "greater", 79, None),
        live_raw("B", "between", 80, 80),
    ]
    calls = []

    def fetch(url, params=None, timeout=30):
        params = dict(params or {})
        calls.append((url, params))
        if "single-runs-api.open-meteo.com" in url:
            return [
                forecast(ENTRY.date(), offset=-5),
                forecast(ENTRY.date(), offset=-8),
                forecast(ENTRY.date(), offset=-6),
            ]
        if url.endswith("/markets/candlesticks"):
            return candle_payload(params["market_tickers"].split(","))
        if url.endswith("/markets") and "series_ticker" in params:
            rows = markets if params["series_ticker"] == "KXHIGHNY" else []
            return {"markets": rows, "cursor": ""}
        if url.endswith("/markets") and "tickers" in params:
            requested = set(params["tickers"].split(","))
            return {"markets": [row for row in markets
                                if row["ticker"] in requested]}
        if url.endswith("/orderbook"):
            return {
                "orderbook_fp": {
                    "yes_dollars": [["0.6000", "12.0"]],
                    "no_dollars": [["0.6000", str(depth_size)]],
                }
            }
        raise AssertionError((url, params))

    return fetch, calls


def test_outside_live_window_skips_every_input_and_write(tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("outside-window collection touched an input")

    result = collect_live(
        now=ENTRY + timedelta(hours=1),
        fetch=forbidden,
        base_dataset=forbidden,
        data_dir=tmp_path,
    )

    assert result["status"] == "outside_entry_window"
    assert not list(tmp_path.iterdir())


def test_live_collection_sources_current_event_exact_candle_and_cached_run(tmp_path):
    base, _ = dataset_for_target()
    fetch, calls = fake_live_fetch()
    now = ENTRY + timedelta(minutes=20)

    result = collect_live(
        now=now,
        fetch=fetch,
        clock=lambda: now + timedelta(seconds=2),
        base_dataset=base,
        data_dir=tmp_path,
        validation_check=lambda conn, series: False,
    )

    assert result["status"] == "complete"
    assert result["funnel"]["target_events"] == 1
    assert result["funnel"]["markets_with_entry_candle"] == 2
    assert result["funnel"]["signals"] == 1
    assert result["signals"][0]["edge_basis"] == "prior"
    assert result["signals"][0]["depth_contracts"] >= 1
    assert Path(result["dataset_path"]).exists()
    merged = load_live_dataset(result["dataset_path"], base_dataset=base)
    assert merged["source_digest"] != base["source_digest"]
    target = next(row for row in merged["events"]
                  if row["event_ticker"] == "KXHIGHNY-26JUL01")
    assert target["forecast"]["request"]["params"]["models"] == "ecmwf_ifs"
    assert target["candles"]["A"][0]["end_ts"] == int(ENTRY.timestamp())

    def no_network(*args, **kwargs):
        raise AssertionError("resume ignored immutable checkpoints")

    resumed = collect_live(
        now=now,
        fetch=no_network,
        clock=lambda: now + timedelta(seconds=30),
        base_dataset=base,
        data_dir=tmp_path,
        validation_check=lambda conn, series: False,
    )
    assert resumed["signals"] == result["signals"]
    assert any("single-runs-api.open-meteo.com" in url for url, _ in calls)


def test_record_collection_dedupes_station_date_and_reports_all_cities(
    tmp_path, conn
):
    base, _ = dataset_for_target()
    fetch, _ = fake_live_fetch()
    now = ENTRY + timedelta(minutes=20)
    collection = collect_live(
        now=now,
        fetch=fetch,
        clock=lambda: now + timedelta(seconds=2),
        base_dataset=base,
        data_dir=tmp_path,
        validation_check=lambda conn, series: False,
    )
    merged = load_live_dataset(collection["dataset_path"], base_dataset=base)

    first = record_collection(
        conn,
        collection,
        now=now + timedelta(minutes=1),
        dataset=merged,
        validation_check=lambda conn, series: False,
    )
    second = record_collection(
        conn,
        collection,
        now=now + timedelta(minutes=2),
        dataset=merged,
        validation_check=lambda conn, series: False,
    )

    assert len(first["opportunity_ids"]) == 1
    assert second["opportunity_ids"] == []
    assert second["duplicate_station_dates"] == 1
    assert [row["segment"] for row in first["segments"]] == [
        "parent", "nyc", "lax", "chicago"
    ]
    assert [row["candidates"] for row in first["segments"]] == [1, 1, 0, 0]
    attempt_count = conn.execute(
        "SELECT count(*) FROM opportunity_attempts"
    ).fetchone()[0]
    assert attempt_count == 1


def test_record_collection_rejects_after_entry_window_even_with_fresh_quote(
    tmp_path, conn
):
    base, _ = dataset_for_target()
    fetch, _ = fake_live_fetch()
    now = ENTRY + timedelta(minutes=59)
    collection = collect_live(
        now=now,
        fetch=fetch,
        clock=lambda: now,
        base_dataset=base,
        data_dir=tmp_path,
        validation_check=lambda conn, series: False,
    )
    merged = load_live_dataset(collection["dataset_path"], base_dataset=base)

    with pytest.raises(ValueError, match="outside the WG-1 entry window"):
        record_collection(
            conn,
            collection,
            now=ENTRY + timedelta(hours=1, minutes=9),
            dataset=merged,
            validation_check=lambda conn, series: False,
        )


def test_segments_follow_registered_slice_predicates_and_keep_city_fallbacks(
    tmp_path, conn
):
    theories.register(
        conn,
        "weather_model_gap",
        "Weather Model Gap",
        "theories/weather_model_gap",
    )
    slices.register_slice(
        conn,
        "weather_model_gap",
        "new-york-control",
        predicate={"extra": {"series_ticker": "KXHIGHNY"}},
        hypothesis="A future New York control slice.",
        origin="Predeclared live reporting control.",
    )
    result = record_collection(conn, {
        "status": "outside_entry_window",
        "funnel": {"entry_window": 0},
    })

    assert [row["segment"] for row in result["segments"]] == [
        "parent", "nyc", "lax", "chicago", "new-york-control"
    ]
    control = result["segments"][-1]
    assert control["reason"] == "A future New York control slice."

    base, _ = dataset_for_target()
    fetch, _ = fake_live_fetch()
    now = ENTRY + timedelta(minutes=20)
    collection = collect_live(
        now=now,
        fetch=fetch,
        clock=lambda: now + timedelta(seconds=2),
        base_dataset=base,
        data_dir=tmp_path,
        validation_check=lambda conn, series: False,
    )
    merged = load_live_dataset(collection["dataset_path"], base_dataset=base)
    recorded = record_collection(
        conn,
        collection,
        now=now + timedelta(minutes=1),
        dataset=merged,
        validation_check=lambda conn, series: False,
    )
    assert recorded["segments"][-1]["candidates"] == 1


def test_duplicate_lookup_is_date_bounded_and_recording_starts_write_lock(
    tmp_path, conn
):
    base, _ = dataset_for_target()
    fetch, _ = fake_live_fetch()
    now = ENTRY + timedelta(minutes=20)
    collection = collect_live(
        now=now,
        fetch=fetch,
        clock=lambda: now + timedelta(seconds=2),
        base_dataset=base,
        data_dir=tmp_path,
        validation_check=lambda conn, series: False,
    )
    merged = load_live_dataset(collection["dataset_path"], base_dataset=base)
    statements = []
    conn.set_trace_callback(statements.append)

    record_collection(
        conn,
        collection,
        now=now + timedelta(minutes=1),
        dataset=merged,
        validation_check=lambda conn, series: False,
    )

    duplicate_query = next(
        sql for sql in statements
        if "FROM opportunity_attempts a" in sql
    )
    assert "a.decision_date=" in duplicate_query
    begin_index = next(
        i for i, sql in enumerate(statements)
        if sql.strip().upper() == "BEGIN IMMEDIATE"
    )
    duplicate_index = statements.index(duplicate_query)
    opportunity_insert_index = next(
        i for i, sql in enumerate(statements)
        if "INSERT INTO opportunities" in sql
    )
    assert begin_index < duplicate_index < opportunity_insert_index


def test_validated_live_signal_still_requires_one_contract_of_depth(tmp_path):
    base, _ = dataset_for_target()
    now = ENTRY + timedelta(minutes=20)
    deep_fetch, _ = fake_live_fetch(depth_size=3)
    deep = collect_live(
        now=now,
        fetch=deep_fetch,
        clock=lambda: now + timedelta(seconds=2),
        base_dataset=base,
        data_dir=tmp_path / "deep",
        validation_check=lambda conn, series: True,
    )
    assert deep["signals"][0]["edge_basis"] == "model"
    assert deep["signals"][0]["disposition"] == "screened"

    shallow_fetch, _ = fake_live_fetch(depth_size=0.5)
    shallow = collect_live(
        now=now,
        fetch=shallow_fetch,
        clock=lambda: now + timedelta(seconds=2),
        base_dataset=base,
        data_dir=tmp_path / "shallow",
        validation_check=lambda conn, series: True,
    )
    assert shallow["signals"][0]["edge_basis"] == "prior"
    assert shallow["signals"][0]["disposition"] == "rejected"
    assert shallow["signals"][0]["depth_contracts"] == pytest.approx(0.5)
