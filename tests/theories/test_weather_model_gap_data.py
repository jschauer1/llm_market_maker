from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from theories.weather_model_gap.collect import (
    SourceDataError,
    collect,
    normalize_candle_response,
    normalize_forecast_response,
)
from theories.weather_model_gap.data import load_dataset, normalize_label
from theories.weather_model_gap.stations import STATIONS


def _market(
    ticker: str,
    *,
    result: str,
    expiration_value: str = "84.00",
    status: str = "finalized",
    settlement_ts: str = "2026-09-04T11:20:15Z",
    settlement_value_dollars: str | None = None,
    rules: str = (
        "If the maximum temperature recorded at New York City (CLINYC) "
        "is between 83-84 degrees according to The Weather Company, then "
        "the market resolves to Yes."
    ),
) -> dict:
    row = {
        "ticker": ticker,
        "event_ticker": "KXHIGHNY-26SEP03",
        "series_ticker": "KXHIGHNY",
        "status": status,
        "result": result,
        "expiration_value": expiration_value,
        "settlement_ts": settlement_ts,
        "rules_primary": rules,
    }
    row["settlement_value_dollars"] = (
        settlement_value_dollars
        if settlement_value_dollars is not None
        else ("1.0000" if result == "yes" else "0.0000")
    )
    return row


def _forecast_payload(run: str = "2026-09-02T12:00") -> dict:
    times = []
    values = []
    hour = 12
    day = 2
    for _ in range(72):
        times.append(f"2026-09-{day:02d}T{hour:02d}:00")
        values.append(70.0 + (_ % 10))
        hour += 1
        if hour == 24:
            hour = 0
            day += 1
    return {
        "latitude": 40.75,
        "longitude": -74.0,
        "elevation": STATIONS["KXHIGHNY"]["elevation"],
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "hourly_units": {"time": "iso8601", "temperature_2m": "°F"},
        "hourly": {"time": times, "temperature_2m": values},
    }


def test_station_catalog_pins_primary_metadata_and_standard_clock():
    assert STATIONS == {
        "KXHIGHNY": {
            "station": "KNYC",
            "latitude": 40.78333,
            "longitude": -73.96667,
            "elevation": 46.9392,
            "standard_utc_offset_hours": -5,
            "cli_id": "NYC",
        },
        "KXHIGHLAX": {
            "station": "KLAX",
            "latitude": 33.93806,
            "longitude": -118.38889,
            "elevation": 38.1,
            "standard_utc_offset_hours": -8,
            "cli_id": "LAX",
        },
        "KXHIGHCHI": {
            "station": "KMDW",
            "latitude": 41.78417,
            "longitude": -87.75528,
            "elevation": 188.0616,
            "standard_utc_offset_hours": -6,
            "cli_id": "MDW",
        },
    }


def test_label_requires_one_yes_and_consistent_twc_whole_degree():
    markets = [_market("A", result="yes"), _market("B", result="no")]
    assert normalize_label(markets, STATIONS["KXHIGHNY"]) == {
        "value": 84,
        "resolved_at": "2026-09-04T11:20:15+00:00",
        "reason": None,
    }
    no_cli = [
        _market(
            "A", result="yes",
            rules="The maximum temperature recorded at New York City according to The Weather Company",
        ),
        _market(
            "B", result="no",
            rules="The maximum temperature recorded at New York City according to The Weather Company",
        ),
    ]
    assert normalize_label(no_cli, STATIONS["KXHIGHNY"])["reason"] is None
    climate_word = [
        _market("A", result="yes", rules="The Weather Company climate summary CLINYC"),
        _market("B", result="no", rules="The Weather Company climate summary CLINYC"),
    ]
    assert normalize_label(climate_word, STATIONS["KXHIGHNY"])["reason"] is None

    bad_cases = [
        ([_market("A", result="yes", status="active"), _market("B", result="no")], "not_all_finalized"),
        ([_market("A", result="yes"), _market("B", result="yes")], "not_exactly_one_yes"),
        ([_market("A", result="yes"), _market("B", result="no", expiration_value="85")], "inconsistent_expiration_value"),
        ([_market("A", result="yes", expiration_value="84.5"), _market("B", result="no", expiration_value="84.5")], "expiration_value_not_whole_degree"),
        ([_market("A", result="yes", settlement_ts=""), _market("B", result="no", settlement_ts="")], "missing_or_invalid_settlement_ts"),
        ([_market("A", result="yes", settlement_value_dollars="0.5"), _market("B", result="no")], "non_binary_settlement_value"),
        ([_market("A", result="yes", settlement_value_dollars="0"), _market("B", result="no")], "settlement_value_result_mismatch"),
        ([_market("A", result="yes", rules="according to the National Weather Service CLINYC"), _market("B", result="no")], "source_rule_mismatch"),
        ([_market("A", result="yes", rules="according to The Weather Company CLILAX"), _market("B", result="no")], "station_rule_mismatch"),
    ]
    for rows, reason in bad_cases:
        assert normalize_label(rows, STATIONS["KXHIGHNY"])["reason"] == reason


def test_forecast_requires_prior_day_12z_run_and_complete_standard_day():
    station = STATIONS["KXHIGHNY"]
    request = {
        "url": "https://single-runs-api.open-meteo.com/v1/forecast",
        "params": {"run": "2026-09-02T12:00", "timezone": "GMT"},
        "location_index": 0,
    }
    out = normalize_forecast_response(
        _forecast_payload(), request, station, date(2026, 9, 3)
    )
    assert out["run"] == "2026-09-02T12:00:00+00:00"
    assert out["request"] == request
    assert out["reason"] is None
    assert len(out["raw_response"]["hourly"]["time"]) == 72
    assert len(out["standard_day_temperature_f"]) == 24
    assert out["standard_day_temperature_f"][0] == 77.0  # Sep 3 05Z
    assert len(out["source_digest"]) == 64


def test_forecast_rejects_wrong_returned_run_and_missing_hour():
    station = STATIONS["KXHIGHNY"]
    request = {
        "url": "u",
        "params": {"run": "2026-09-02T12:00", "timezone": "GMT"},
        "location_index": 0,
    }
    payload = _forecast_payload()
    payload["hourly"]["time"][0] = "2026-09-02T13:00"
    with pytest.raises(SourceDataError, match="returned run"):
        normalize_forecast_response(payload, request, station, date(2026, 9, 3))

    payload = _forecast_payload()
    payload["hourly"]["temperature_2m"][20] = None
    with pytest.raises(SourceDataError, match="missing temperature"):
        normalize_forecast_response(payload, request, station, date(2026, 9, 3))


def test_unavailable_exact_run_is_checkpointed_and_retained_as_missing(tmp_path):
    from theories.weather_model_gap import collect as subject
    from tools.http import HttpError

    def fetch(url, params=None):
        raise HttpError("GET source failed with status 400")

    result = subject._forecast_for_date(
        date(2026, 6, 11), ("KXHIGHNY",), tmp_path, fetch
    )
    forecast = result["KXHIGHNY"]
    assert forecast["raw_response"] is None
    assert forecast["run"] == "2026-06-10T12:00:00+00:00"
    assert "status 400" in forecast["reason"]
    wrapper = json.loads(
        (tmp_path / "raw" / "forecasts" / "2026-06-11.json")
        .read_text(encoding="utf-8")
    )
    assert wrapper["response"] is None
    assert "status 400" in wrapper["fetch_error"]


def test_transient_forecast_failure_is_not_permanently_checkpointed(tmp_path):
    from theories.weather_model_gap import collect as subject
    from tools.http import HttpError

    def fetch(url, params=None):
        raise HttpError("GET source failed with status 429 after retries")

    with pytest.raises(HttpError, match="429"):
        subject._forecast_for_date(
            date(2026, 6, 11), ("KXHIGHNY",), tmp_path, fetch
        )
    assert not (tmp_path / "raw" / "forecasts" / "2026-06-11.json").exists()


def test_candle_requires_single_bar_ending_exactly_at_entry():
    payload = {
        "candlesticks": [{
            "end_period_ts": 1788390000,
            "yes_bid": {"close_dollars": "0.39"},
            "yes_ask": {"close_dollars": "0.42"},
            "volume_fp": "4.0",
            "open_interest_fp": "120.0",
        }, {
            "end_period_ts": 1788393600,
            "yes_bid": {"close_dollars": "0.41"},
            "yes_ask": {"close_dollars": "0.44"},
            "volume_fp": "12.5",
            "open_interest_fp": "123.0",
        }]
    }
    assert normalize_candle_response(payload, 1788393600) == [{
        "end_ts": 1788393600,
        "yes_bid_close": 0.41,
        "yes_ask_close": 0.44,
        "volume": 12.5,
        "open_interest": 123.0,
    }]
    payload["candlesticks"][1]["end_period_ts"] -= 3600
    with pytest.raises(SourceDataError, match="exact entry"):
        normalize_candle_response(payload, 1788393600)


def test_collector_retains_wrong_timestamp_as_explicit_missing_candle():
    from theories.weather_model_gap import collect as subject

    payload = {"candlesticks": [{"end_period_ts": 1788390000}]}
    bars, reason = subject._normalize_candle_or_missing(payload, 1788393600)
    assert bars == []
    assert reason == "candle response must contain one bar ending at exact entry"


def test_collection_checkpoints_raw_before_forecast_schema_failure(tmp_path: Path):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("frozen", encoding="utf-8")

    market = _market("KXHIGHNY-26SEP03-B83.5", result="yes")
    market.update({
        "open_time": "2026-09-01T00:00:00Z",
        "close_time": "2026-09-04T05:00:00Z",
    })
    other = _market("KXHIGHNY-26SEP03-B85.5", result="no")
    other.update({
        "open_time": "2026-09-01T00:00:00Z",
        "close_time": "2026-09-04T05:00:00Z",
    })

    def fetch(url, params=None):
        params = params or {}
        if url.endswith("/stations/KNYC"):
            return {
                "geometry": {"coordinates": [-73.96667, 40.78333]},
                "properties": {
                    "stationIdentifier": "KNYC",
                    "elevation": {"unitCode": "wmoUnit:m", "value": 46.9392},
                },
            }
        if "weather.com/kalshi/api/climate/primary" in url:
            return {"results": [{"station": {"icao": "KNYC", "cliId": "NYC"}}]}
        if url.endswith("/markets"):
            return {"markets": [market, other], "cursor": ""}
        if url.endswith("/historical/markets"):
            return {"markets": [], "cursor": ""}
        if "single-runs-api" in url:
            return {"malformed": True}
        raise AssertionError((url, params))

    with pytest.raises(SourceDataError):
        collect(
            tmp_path,
            fetch=fetch,
            series=("KXHIGHNY",),
            start_date=date(2026, 9, 3),
            end_date=date(2026, 9, 3),
            protocol_path=protocol,
        )
    raw = tmp_path / "raw" / "forecasts" / "2026-09-03.json"
    wrapper = json.loads(raw.read_text(encoding="utf-8"))
    assert wrapper["params"]["run"] == "2026-09-02T12:00"
    assert wrapper["response"] == {"malformed": True}


def test_load_dataset_checks_digests(tmp_path: Path):
    payload = {
        "events": [],
        "coverage": {"events": 0},
        "source_digest": "a" * 64,
        "protocol_digest": "b" * 64,
    }
    (tmp_path / "dataset.json").write_text(json.dumps(payload), encoding="utf-8")
    assert load_dataset(tmp_path) == payload
    payload["protocol_digest"] = "bad"
    (tmp_path / "dataset.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="protocol_digest"):
        load_dataset(tmp_path)
