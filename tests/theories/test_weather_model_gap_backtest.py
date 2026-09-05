from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json

import pytest

from theories.weather_model_gap.backtest import reconstruct, freeze, replay, save
from theories.weather_model_gap.analysis import production_ready, RUN_ID, digest
from tools import theories


ENTRY = datetime(2026, 7, 1, tzinfo=timezone.utc)


def inputs():
    raw = dict(ticker="KXHIGHNY-26JUL01-B80.5", event_ticker="KXHIGHNY-26JUL01",
               open_time="2026-06-30T10:00:00Z", close_time="2026-07-02T04:00:00Z",
               rules_secondary="The Weather Company", strike_type="between",
               floor_strike=80, cap_strike=81, result="yes", expiration_value="80",
               settlement_ts="2026-07-02T12:00:00Z", volume=999999, yes_bid=1)
    event = dict(series_ticker="KXHIGHNY", event_ticker=raw["event_ticker"],
                 target_date="2026-07-01")
    candle = dict(end_ts=int(ENTRY.timestamp()), yes_bid_close=.39,
                  yes_ask_close=.40, volume=12, open_interest=200)
    return raw, event, candle


def test_reconstruction_uses_exact_quote_and_strips_terminal_fields():
    raw, event, candle = inputs()
    market, reason = reconstruct(raw, event, [candle], ENTRY)
    assert reason is None
    assert market.yes_ask == .4 and market.no_ask == .61
    assert market.volume == 12 and market.result is None
    assert not {"result", "expiration_value", "settlement_ts", "volume", "yes_bid"} & market.raw.keys()
    poisoned = dict(raw, result="no", expiration_value="-999", volume=0, yes_bid=0)
    other, _ = reconstruct(poisoned, event, [candle], ENTRY)
    assert other == market and other.raw == market.raw


@pytest.mark.parametrize("change,reason", [
    ({"end_ts": int(ENTRY.timestamp()) + 3600}, "entry_candle_missing"),
    ({"yes_ask_close": None}, "invalid_quote"),
    ({"yes_bid_close": .8}, "invalid_quote"),
])
def test_invalid_or_future_quotes_never_become_fills(change, reason):
    raw, event, candle = inputs()
    candle.update(change)
    assert reconstruct(raw, event, [candle], ENTRY) == (None, reason)


def test_freeze_refuses_changed_decisions(tmp_path):
    path = tmp_path / "decisions.json"
    freeze(path, [{"ticker": "A"}])
    freeze(path, [{"ticker": "A"}])
    with pytest.raises(ValueError, match="Frozen"):
        freeze(path, [{"ticker": "B"}])


def campaign(path):
    """A complete synthetic city calendar: known errors, actual contract replay."""
    (path / "PROTOCOL.md").write_text("Synthetic WG-1 fixture", encoding="utf-8")
    protocol = digest(path / "PROTOCOL.md")
    events = []
    start = date(2026, 5, 1)
    for i in range(132):
        day = start + timedelta(days=i)
        if day >= date(2026, 9, 1):
            break
        entry = datetime.combine(day, time.min, timezone.utc)
        run = entry - timedelta(hours=12)
        key = f"KXHIGHNY-{day.isoformat()}"
        raw = dict(ticker=key + "-B80.5", event_ticker=key, strike_type="between",
                   floor_strike=80, cap_strike=81, status="finalized", result="yes",
                   expiration_value="80", settlement_value_dollars="1.0000",
                   open_time=(entry-timedelta(hours=12)).isoformat(),
                   close_time=(entry+timedelta(hours=28)).isoformat(),
                   settlement_ts=(entry+timedelta(hours=36)).isoformat(),
                   rules_primary="The Weather Company climate summary CLINYC",
                   rules_secondary="The Weather Company")
        label = dict(value=80, resolved_at=raw["settlement_ts"], reason=None)
        raw_forecast = dict(latitude=40.78, longitude=-73.97, elevation=46.9392,
                            timezone="UTC", utc_offset_seconds=0,
                            hourly_units={"temperature_2m": "°F"},
                            hourly={"time": [(run+timedelta(hours=h)).isoformat() for h in range(42)],
                                    "temperature_2m": [80.0]*42})
        events.append(dict(event_ticker=key, series_ticker="KXHIGHNY", station="KNYC",
                           target_date=day.isoformat(), markets=[raw], label=label,
                           candles={raw["ticker"]: [dict(end_ts=int(entry.timestamp()),
                               yes_bid_close=.39, yes_ask_close=.4, volume=12, open_interest=200)]},
                           forecast=dict(raw_response=raw_forecast, run=run.isoformat(),
                               request={"params": {"models": "ecmwf_ifs"}}, source_digest="b"*64)))
    dataset = dict(events=events, coverage={"events": len(events)},
                   source_digest="a"*64, protocol_digest=protocol)
    save(path / "dataset.json", dataset)
    save(path / "manifest.json", dict(completed_at="2026-09-05T00:00:00Z",
                                      source_digest="a"*64, protocol_digest=protocol))


def test_real_contract_replay_proves_city_and_detects_rewritten_proof(conn, tmp_path):
    theories.register(conn, "weather_model_gap", "Weather Model Gap", "theories/weather_model_gap")
    campaign(tmp_path)
    results = replay(conn, tmp_path)
    assert results["cities"]["KXHIGHNY"]["supported"]
    assert results["pooled"]["n"] == 62
    assert production_ready(conn, "KXHIGHNY", campaign=tmp_path)
    assert not production_ready(conn, "KXHIGHLAX", campaign=tmp_path)
    # A later campaign cannot hide selected failures by rewriting both files.
    decisions = json.loads((tmp_path / "decisions.json").read_text())
    save(tmp_path / "decisions.json", decisions[:-1])
    manifest = json.loads((tmp_path / "evaluation_manifest.json").read_text())
    manifest["decisions_digest"] = digest(tmp_path / "decisions.json")
    save(tmp_path / "evaluation_manifest.json", manifest)
    assert not production_ready(conn, "KXHIGHNY", campaign=tmp_path)


def test_production_support_respects_asof_and_missing_settlements(conn, tmp_path):
    theories.register(conn, "weather_model_gap", "Weather Model Gap", "theories/weather_model_gap")
    campaign(tmp_path)
    replay(conn, tmp_path)
    assert not production_ready(conn, "KXHIGHNY", campaign=tmp_path, now=ENTRY)
    conn.execute("DELETE FROM settlements WHERE kalshi_ticker=(SELECT kalshi_ticker FROM settlements LIMIT 1)")
    conn.commit()
    assert not production_ready(conn, "KXHIGHNY", campaign=tmp_path)
