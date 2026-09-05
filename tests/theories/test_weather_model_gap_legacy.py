from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json

import pytest

from tests.theories.test_weather_model_gap import forecast, run_for
from theories.weather_model_gap import data
from theories.weather_model_gap.stations import STATIONS
from tools import score, theories
from tools.domain import Market
from tools.theory import TheoryContext


UTC = timezone.utc


def _nws_market(day: date, *, result="yes", station="KNYC") -> dict:
    place = {
        "KNYC": "Central Park, New York",
        "KLAX": "Los Angeles Airport, CA",
        "KMDW": "Chicago Midway, IL",
    }[station]
    entry = datetime.combine(day, time.min, UTC)
    return {
        "ticker": f"NWS-{station}-{day}-T79",
        "event_ticker": f"NWS-{station}-{day}",
        "series_ticker": {
            "KNYC": "KXHIGHNY",
            "KLAX": "KXHIGHLAX",
            "KMDW": "KXHIGHCHI",
        }[station],
        "title": f"High at {place}",
        "status": "finalized",
        "result": result,
        "expiration_value": "80",
        "settlement_value_dollars": "1" if result == "yes" else "0",
        "settlement_ts": (entry + timedelta(hours=36)).isoformat(),
        "open_time": (entry - timedelta(hours=12)).isoformat(),
        "close_time": (entry + timedelta(hours=29)).isoformat(),
        "strike_type": "greater",
        "floor_strike": 79,
        "rules_primary": (
            f"The highest temperature at {place} according to the National "
            "Weather Service's Climatological Report (Daily)."
        ),
        "rules_secondary": (
            "The official final value is from the corresponding NWS "
            "Climatological Report (Daily)."
        ),
    }


def _nws_event(day: date, *, station="KNYC") -> dict:
    series = {
        "KNYC": "KXHIGHNY",
        "KLAX": "KXHIGHLAX",
        "KMDW": "KXHIGHCHI",
    }[station]
    offset = STATIONS[series]["standard_utc_offset_hours"]
    raw = _nws_market(day, station=station)
    entry = datetime.combine(day, time.min, UTC)
    return {
        "event_ticker": raw["event_ticker"],
        "series_ticker": series,
        "station": station,
        "target_date": day.isoformat(),
        "markets": [raw],
        "candles": {raw["ticker"]: [{
            "end_ts": int(entry.timestamp()),
            "yes_bid_close": 0.39,
            "yes_ask_close": 0.40,
            "volume": 4,
            "open_interest": 200,
        }]},
        "forecast": {
            "raw_response": forecast(day, offset=offset, maximum=80),
            "run": run_for(day).isoformat(),
            "request": {"params": {"models": "ecmwf_ifs"}},
            "source_digest": hashlib.sha256(
                f"forecast:{series}:{day}".encode()
            ).hexdigest(),
        },
        "label": {
            "value": None,
            "resolved_at": None,
            "reason": "source_rule_mismatch",
        },
    }


def _base_campaign(path):
    path.mkdir(parents=True)
    protocol = path / "PROTOCOL.md"
    protocol.write_text("Synthetic immutable WG-1 base", encoding="utf-8")
    protocol_digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
    events = [
        _nws_event(date(2026, 3, 1) + timedelta(days=i))
        for i in range(63)
    ]
    dataset = {
        "events": events,
        "coverage": {"events": len(events)},
        "source_digest": "a" * 64,
        "protocol_digest": protocol_digest,
    }
    (path / "dataset.json").write_text(
        json.dumps(dataset, sort_keys=True), encoding="utf-8"
    )
    (path / "manifest.json").write_text(json.dumps({
        "completed_at": "2026-09-05T00:00:00Z",
        "source_digest": dataset["source_digest"],
        "protocol_digest": protocol_digest,
    }), encoding="utf-8")
    return dataset


def test_nws_label_policy_requires_provider_in_both_rules_and_station_in_primary():
    market = _nws_market(date(2026, 5, 1))
    label = data.normalize_label(
        [market], STATIONS["KXHIGHNY"], source_policy="nws"
    )
    assert label["value"] == 80 and label["reason"] is None

    mixed = dict(market, rules_secondary="The Weather Company")
    assert data.normalize_label(
        [mixed], STATIONS["KXHIGHNY"], source_policy="nws"
    )["reason"] == "source_rule_mismatch"
    wrong_station = dict(
        market,
        rules_primary=market["rules_primary"].replace(
            "Central Park, New York", "Los Angeles Airport, CA"
        ),
    )
    assert data.normalize_label(
        [wrong_station], STATIONS["KXHIGHNY"], source_policy="nws"
    )["reason"] == "station_rule_mismatch"
    with pytest.raises(ValueError, match="source_policy"):
        data.normalize_label([market], STATIONS["KXHIGHNY"], source_policy="other")


def test_nws_subclass_is_confined_to_exact_backtest_lane(tmp_path, conn):
    from theories.weather_model_gap.legacy import (
        LegacyNWSDiagnosticTheory,
        RUN_ID,
        derive_dataset,
    )

    base_path = tmp_path / "base"
    _base_campaign(base_path)
    campaign = tmp_path / "experiment"
    campaign.mkdir()
    (campaign / "PROTOCOL.md").write_text("Frozen NWS diagnostic", encoding="utf-8")
    dataset, _ = derive_dataset(campaign, base_path)
    event = next(e for e in dataset["events"] if e["target_date"] == "2026-05-01")
    raw = event["markets"][0]
    entry = datetime(2026, 5, 1, tzinfo=UTC)
    board = [Market(
        platform="kalshi", ticker=raw["ticker"], title=raw["title"],
        yes_bid=.39, yes_ask=.40, no_bid=.60, no_ask=.61,
        mid=.395, spread=.01, volume=4, volume_24h=4,
        open_interest=200, status="active", is_open=True,
        event_ticker=event["event_ticker"], series_ticker=event["series_ticker"],
        raw={**raw, "_wg1_entry_ts": int(entry.timestamp()),
             "_wg1_entry_volume": 4},
    )]
    theory = LegacyNWSDiagnosticTheory(dataset=dataset)

    wrong = TheoryContext.build(
        conn, board, entry, run_id="wg1-nws-wrong", run_mode="backtest"
    )
    live = TheoryContext.build(
        conn, board, entry, run_id=RUN_ID, run_mode="live"
    )
    right = TheoryContext.build(
        conn, board, entry, run_id=RUN_ID, run_mode="backtest"
    )
    assert theory.start(wrong).screen_result.gate_removed == {
        "experiment_scope": 1
    }
    assert theory.start(live).screen_result.gate_removed == {
        "experiment_scope": 1
    }
    selected = theory.start(right).finish(dry_run=True).scored
    assert len(selected) == 1
    assert selected[0].extra["protocol"] == "WG-1-NWS"
    assert selected[0].extra["source_policy"] == "nws"


def test_legacy_replay_freezes_small_identity_and_stays_out_of_production(
    tmp_path, conn
):
    from theories.weather_model_gap.legacy import RUN_ID, prepare, replay

    theories.register(
        conn,
        "weather_model_gap",
        "Weather Model Gap",
        "theories/weather_model_gap",
    )
    base_path = tmp_path / "base"
    _base_campaign(base_path)
    campaign = tmp_path / "experiment"
    campaign.mkdir()
    (campaign / "PROTOCOL.md").write_text("Frozen NWS diagnostic", encoding="utf-8")

    _, decisions, _, manifest = prepare(conn, campaign, base_path)
    assert len(decisions) == 2
    assert all("result" not in row for row in decisions)
    identity = json.loads((campaign / "derived_identity.json").read_text())
    assert identity["source_policy"] == "nws"
    assert identity["base_dataset_path"] == str(base_path / "dataset.json")
    assert not (campaign / "dataset.json").exists()
    assert manifest["run_id"] == RUN_ID

    result = replay(conn, campaign, base_path)
    assert result["pooled"]["total_n"] == 2
    assert list(result["cities"]) == [
        "KXHIGHNY", "KXHIGHLAX", "KXHIGHCHI"
    ]
    assert result["cities"]["KXHIGHLAX"]["total_n"] == 0
    registered = conn.execute(
        "SELECT tier,uses_llm_judgment FROM backtest_runs WHERE run_id=?",
        (RUN_ID,),
    ).fetchone()
    assert tuple(registered) == ("A", 0)
    attempt = conn.execute(
        "SELECT a.extra_json,o.lane FROM opportunity_attempts a "
        "JOIN opportunities o ON o.id=a.opportunity_id WHERE a.run_id=?",
        (RUN_ID,),
    ).fetchone()
    assert attempt["lane"] == RUN_ID
    assert json.loads(attempt["extra_json"])["source_policy"] == "nws"
    assert score.compute_score(
        conn, "weather_model_gap", 1, "backtest"
    )["n"] == 0
