from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from tools.domain import Market
from tools.theory import TheoryContext

from theories.weather_model_gap.model import (
    InsufficientHistory,
    forecast_proxy,
    predict,
    strike_satisfied,
)
from theories.weather_model_gap.theory import WeatherModelGapTheory
import theories.weather_model_gap.theory as theory_module


UTC = timezone.utc
TARGET = date(2026, 7, 1)
ENTRY = datetime(2026, 7, 1, tzinfo=UTC)
STATIONS = {
    "KXHIGHNY": {
        "station": "KNYC",
        "station_identifier": "KNYC",
        "latitude": 40.78333,
        "longitude": -73.96667,
        "elevation": 46.9392,
        "standard_utc_offset_hours": -5,
    },
    "KXHIGHLAX": {
        "station": "KLAX",
        "station_identifier": "KLAX",
        "latitude": 33.93806,
        "longitude": -118.38889,
        "elevation": 38.1,
        "standard_utc_offset_hours": -8,
    },
    "KXHIGHCHI": {
        "station": "KMDW",
        "station_identifier": "KMDW",
        "latitude": 41.78417,
        "longitude": -87.75528,
        "elevation": 188.0616,
        "standard_utc_offset_hours": -6,
    },
}


def forecast(day: date, *, offset: int = -5, maximum: float = 80.0):
    start = datetime.combine(day, datetime.min.time(), UTC) - timedelta(hours=offset)
    run = run_for(day)
    hours = int(((start + timedelta(hours=23)) - run).total_seconds() / 3600) + 1
    times = [run + timedelta(hours=i) for i in range(hours)]
    values = [70.0] * (hours - 1) + [maximum]
    coordinates = {
        -5: (40.808434, -74.0199, 46.9392),
        -8: (33.919155, -118.391525, 38.1),
        -6: (41.792618, -87.78262, 188.0616),
    }[offset]
    return {
        "latitude": coordinates[0],
        "longitude": coordinates[1],
        "elevation": coordinates[2],
        "timezone": "UTC",
        "utc_offset_seconds": 0,
        "hourly_units": {"time": "iso8601", "temperature_2m": "\N{DEGREE SIGN}F"},
        "hourly": {
            "time": [t.isoformat().replace("+00:00", "Z") for t in times],
            "temperature_2m": values,
        },
    }


def run_for(day: date) -> datetime:
    return datetime.combine(day - timedelta(days=1), datetime.min.time(), UTC) + timedelta(hours=12)


def raw_market(ticker: str, *, strike_type="between", floor=80, cap=80):
    raw = {
        "ticker": ticker,
        "event_ticker": "EV-TARGET",
        "series_ticker": "KXHIGHNY",
        "strike_type": strike_type,
        "rules_secondary": "Settlement source: The Weather Company (weather.com).",
    }
    if floor is not None:
        raw["floor_strike"] = floor
    if cap is not None:
        raw["cap_strike"] = cap
    return raw


def event(
    day: date,
    *,
    series="KXHIGHNY",
    station="KNYC",
    value=None,
    resolved_at=None,
    maximum=80.0,
    markets=None,
    event_ticker=None,
):
    return {
        "event_ticker": event_ticker or f"{series}-{day.isoformat()}",
        "series_ticker": series,
        "station": station,
        "target_date": day.isoformat(),
        "markets": list(markets or []),
        "candles": {},
        "forecast": {
            "raw_response": forecast(
                day,
                offset=STATIONS[series]["standard_utc_offset_hours"],
                maximum=maximum,
            ),
            "run": run_for(day).isoformat(),
            "request": {"params": {"models": "ecmwf_ifs"}},
            "source_digest": f"sha256:{series}-{day.isoformat()}",
        },
        "label": {
            "value": value,
            "resolved_at": resolved_at,
            "reason": None,
        },
    }


def dataset_for_target(*, errors=(0,) * 30, extra_events=()):
    history = []
    for i, error in enumerate(errors, start=1):
        day = TARGET - timedelta(days=i)
        history.append(event(
            day,
            value=80 + error,
            resolved_at=(ENTRY - timedelta(hours=1)).isoformat(),
        ))
    target = event(
        TARGET,
        markets=[
            raw_market("A", strike_type="greater", floor=79, cap=None),
            raw_market("B", strike_type="between", floor=80, cap=80),
        ],
        event_ticker="EV-TARGET",
    )
    return {
        "source_digest": "dataset-source-digest",
        "events": [*history, *extra_events, target],
    }, target


def board_market(ticker: str, market_raw: dict, **changes) -> Market:
    base = dict(
        platform="kalshi",
        ticker=ticker,
        title=ticker,
        yes_bid=0.39,
        yes_ask=0.40,
        no_bid=0.60,
        no_ask=0.61,
        mid=0.395,
        spread=0.01,
        volume=10.0,
        volume_24h=10.0,
        open_interest=200.0,
        status="active",
        is_open=True,
        event_ticker="EV-TARGET",
        series_ticker="KXHIGHNY",
        raw={**market_raw, "_wg1_entry_ts": int(ENTRY.timestamp()),
             "_wg1_entry_volume": 3.0},
    )
    base.update(changes)
    return Market(**base)


def context(board, *, mode="backtest", now=ENTRY):
    return TheoryContext(
        conn=None,
        board=list(board),
        now=now,
        run_id="backtest/wg1-test",
        run_mode=mode,
    )


def test_forecast_proxy_uses_fixed_standard_day_and_half_up_rounding():
    raw = forecast(TARGET, maximum=79.5)
    assert forecast_proxy(raw, STATIONS["KXHIGHNY"], TARGET, run_for(TARGET)) == 80

    raw["hourly"]["temperature_2m"][-1] = 78.5
    raw["hourly"]["temperature_2m"][0] = 78.4
    assert forecast_proxy(raw, STATIONS["KXHIGHNY"], TARGET, run_for(TARGET)) == 79


def test_forecast_proxy_rejects_missing_hour_and_wrong_run():
    raw = forecast(TARGET)
    raw["hourly"]["time"].pop(20)
    raw["hourly"]["temperature_2m"].pop(20)
    with pytest.raises(ValueError, match="24 complete"):
        forecast_proxy(raw, STATIONS["KXHIGHNY"], TARGET, run_for(TARGET))

    with pytest.raises(ValueError, match="12:00 UTC on D-1"):
        forecast_proxy(forecast(TARGET), STATIONS["KXHIGHNY"], TARGET,
                       run_for(TARGET) + timedelta(hours=6))

    with pytest.raises(ValueError, match="station coordinates"):
        forecast_proxy(forecast(TARGET), STATIONS["KXHIGHLAX"], TARGET,
                       run_for(TARGET))


def test_integer_strikes_are_applied_exactly():
    assert strike_satisfied(raw_market("B", floor=80, cap=81), 80)
    assert strike_satisfied(raw_market("B", floor=80, cap=81), 81)
    assert not strike_satisfied(raw_market("B", floor=80, cap=81), 82)
    assert strike_satisfied(raw_market("L", strike_type="less", floor=None,
                                       cap=80), 79)
    assert not strike_satisfied(raw_market("L", strike_type="less", floor=None,
                                           cap=80), 80)
    assert strike_satisfied(raw_market("G", strike_type="greater", floor=80,
                                       cap=None), 81)
    assert not strike_satisfied(raw_market("G", strike_type="greater", floor=80,
                                           cap=None), 80)


def test_predict_never_uses_future_settlements_or_pending_labels():
    future_day = TARGET - timedelta(days=31)
    future = event(
        future_day,
        value=200,
        resolved_at=(ENTRY + timedelta(seconds=1)).isoformat(),
    )
    pending = event(TARGET - timedelta(days=32), value=None, resolved_at=None)
    dataset, target = dataset_for_target(extra_events=(future, pending))

    out = predict(dataset, target, ENTRY, stations=STATIONS)

    assert out.training_n == 30
    assert {p.ticker: p.q_yes for p in out.markets} == {
        "A": pytest.approx(30.5 / 31),
        "B": pytest.approx(30.5 / 31),
    }


def test_history_is_station_specific_and_requires_thirty_rows():
    dataset, target = dataset_for_target(errors=(0,) * 29)
    lax = event(
        TARGET - timedelta(days=40),
        series="KXHIGHLAX",
        station="KLAX",
        value=200,
        resolved_at=(ENTRY - timedelta(hours=1)).isoformat(),
    )
    dataset["events"].insert(0, lax)

    with pytest.raises(InsufficientHistory, match="29"):
        predict(dataset, target, ENTRY, stations=STATIONS)

    mixed = {**target, "station": "KLAX"}
    with pytest.raises(ValueError, match="station"):
        predict(dataset, mixed, ENTRY, stations=STATIONS)

    wrong_model = {**target, "forecast": {
        **target["forecast"],
        "request": {"params": {"models": "ecmwf_ifs025"}},
    }}
    with pytest.raises(ValueError, match="ecmwf_ifs"):
        predict(dataset, wrong_model, ENTRY, stations=STATIONS)

    full, target = dataset_for_target()
    full["events"][0]["forecast"]["request"] = {
        "params": {"models": "ecmwf_ifs025"}
    }
    with pytest.raises(InsufficientHistory, match="29"):
        predict(full, target, ENTRY, stations=STATIONS)


def test_theory_selects_only_the_best_ticker_per_event(monkeypatch):
    dataset, target = dataset_for_target()
    monkeypatch.setattr(theory_module, "_load_stations", lambda: STATIONS)
    a = board_market("A", target["markets"][0])
    b = board_market("B", target["markets"][1])
    theory = WeatherModelGapTheory(dataset=dataset)

    result = theory.screen(context([b, a]))
    scored = theory.price(context([b, a]), list(result.candidates))

    assert [candidate.ticker for candidate in result.candidates] == ["A"]
    assert result.funnel["candidates"] == 1
    assert result.gate_removed["lower_ranked"] == 1
    assert scored[0].edge.basis == "model"
    assert scored[0].extra["training_n"] == 30
    assert scored[0].extra["event_ticker"] == "EV-TARGET"
    assert scored[0].extra["entry_ts"] == int(ENTRY.timestamp())
    assert scored[0].extra["source_digest"] == "dataset-source-digest"
    assert scored[0].extra["forecast_source_digest"].startswith("sha256:")


def test_screen_reports_each_execution_gate(monkeypatch):
    dataset, target = dataset_for_target()
    monkeypatch.setattr(theory_module, "_load_stations", lambda: STATIONS)
    oi_raw = raw_market("OI", strike_type="greater", floor=79, cap=None)
    spread_raw = raw_market("SPREAD", strike_type="greater", floor=79, cap=None)
    volume_raw = raw_market("VOLUME", strike_type="greater", floor=79, cap=None)
    closed_raw = raw_market("CLOSED", strike_type="greater", floor=79, cap=None)
    rows = [
        board_market("OI", oi_raw, open_interest=99),
        board_market("SPREAD", spread_raw, spread=0.05, yes_bid=0.35),
        board_market("VOLUME", volume_raw, raw={
            **volume_raw,
            "_wg1_entry_ts": int(ENTRY.timestamp()),
            "_wg1_entry_volume": 0,
        }),
        board_market("CLOSED", closed_raw, is_open=False),
    ]

    result = WeatherModelGapTheory(dataset=dataset).screen(context(rows))

    assert result.candidates == ()
    assert result.gate_removed == {
        "open_interest": 1,
        "spread": 1,
        "no_entry_activity": 1,
        "not_open": 1,
    }


def test_live_requotes_and_remains_prior_until_validated(monkeypatch):
    dataset, target = dataset_for_target()
    monkeypatch.setattr(theory_module, "_load_stations", lambda: STATIONS)
    stale = board_market("A", target["markets"][0], yes_bid=0.89, yes_ask=0.90,
                         spread=0.01)

    def fetch(url, params=None, timeout=30):
        assert url.endswith("/markets")
        return {"markets": [{
            **target["markets"][0],
            "status": "active",
            "yes_bid_dollars": "0.39",
            "yes_ask_dollars": "0.40",
            "open_interest_fp": "200",
            "volume_fp": "10",
            "volume_24h_fp": "10",
        }]}

    now = ENTRY + timedelta(minutes=30)
    theory = WeatherModelGapTheory(
        dataset=dataset,
        validation_check=lambda conn, series: False,
        fetch=fetch,
    )
    ctx = context([stale], mode="live", now=now)
    result = theory.screen(ctx)
    scored = theory.price(ctx, list(result.candidates))

    assert result.candidates[0].entry_price == pytest.approx(0.40)
    assert scored[0].edge.basis == "prior"
    assert scored[0].edge.pts_net == 0.0
    assert scored[0].extra["model_prob"] == pytest.approx(30.5 / 31)

    outside = context([stale], mode="live", now=ENTRY + timedelta(hours=1))
    blocked = theory.screen(outside)
    assert blocked.candidates == ()
    assert blocked.gate_removed == {"outside_entry_window": 1}
