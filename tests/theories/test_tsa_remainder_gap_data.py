from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json

import pytest

from theories.tsa_remainder_gap import collect as collector

from theories.tsa_remainder_gap.data import (
    DataError,
    entry_for,
    load_dataset,
    normalize_candle,
    parse_contract,
    parse_tsa_html,
)


def market(**overrides):
    row = {
        "ticker": "TSAW-24JUN30-A2.50",
        "event_ticker": "TSAW-24JUN30",
        "open_time": "2024-06-24T14:00:00Z",
        "strike_type": "greater",
        "floor_strike": 2_500_000,
        "rules_primary": (
            "If weekly average TSA airport screenings are above 2.5 million "
            "for the week ending June 30, 2024, according to the TSA, then "
            "the market resolves to Yes."
        ),
    }
    row.update(overrides)
    return row


def test_contract_uses_rules_date_and_friday_entry_not_close_time():
    parsed, reason = parse_contract(market(close_time="2024-06-25T00:00:00Z"))
    assert reason is None
    assert parsed == {"week_end": date(2024, 6, 30), "strike": 2_500_000}
    assert entry_for(parsed["week_end"]) == datetime(2024, 6, 28, 15, tzinfo=timezone.utc)

    _, reason = parse_contract(market(rules_primary="Average screenings above 2.5 million."))
    assert reason == "rules_not_explicit_tsa_weekly_strict_above"
    _, reason = parse_contract(market(event_ticker="TSAW-24JUN23"))
    assert reason == "rules_event_date_mismatch"
    _, reason = parse_contract(market(floor_strike="not-a-number"))
    assert reason == "rules_strike_invalid"
    repeated = market()["rules_primary"] + " " + market()["rules_primary"]
    _, reason = parse_contract(market(rules_primary=repeated))
    assert reason == "rules_ambiguous_contract"


def test_tsa_parser_accepts_only_two_column_year_table_and_rejects_comparison_trap():
    html = """<table><thead><tr><th>Date</th><th>Numbers</th></tr></thead>
    <tbody><tr><td>6/28/2024</td><td>2,652,462</td></tr></tbody></table>"""
    assert parse_tsa_html(html, 2024) == {"2024-06-28": 2_652_462}

    shifted = """<table><tr><th>Date</th><th>2024</th><th>2023</th></tr>
    <tr><td>6/28/2024</td><td>2,652,462</td><td>2,450,000</td></tr></table>"""
    with pytest.raises(DataError, match="two-column"):
        parse_tsa_html(shifted, 2024)


def test_exact_candle_and_dataset_digest_are_fail_closed(tmp_path):
    entry = int(datetime(2024, 6, 28, 15, tzinfo=timezone.utc).timestamp())
    payload = {"candlesticks": [{
        "end_period_ts": entry,
        "yes_bid": {"close_dollars": "0.4100"},
        "yes_ask": {"close_dollars": "0.4400"},
        "price": {"close_dollars": "0.4200"},
        "volume_fp": "151.00",
        "open_interest_fp": "222.00",
    }]}
    assert normalize_candle(payload, entry) == {
        "end_ts": entry, "yes_bid_close": 0.41, "yes_ask_close": 0.44,
        "open_interest": 222.0, "volume": 151.0,
    }
    payload["candlesticks"][0]["yes_bid"] = {"close": 1}
    payload["candlesticks"][0]["yes_ask"] = {"close": 44}
    assert normalize_candle(payload, entry)["yes_bid_close"] == 0.01
    assert normalize_candle(payload, entry)["yes_ask_close"] == 0.44
    payload["candlesticks"][0]["yes_bid"] = {"close": "0.9500"}
    payload["candlesticks"][0]["yes_ask"] = {"close": "1.0000"}
    assert normalize_candle(payload, entry)["yes_bid_close"] == 0.95
    assert normalize_candle(payload, entry)["yes_ask_close"] == 1.0
    with pytest.raises(DataError, match="exactly one"):
        normalize_candle({"candlesticks": []}, entry)

    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("frozen", encoding="utf-8")
    source = tmp_path / "source.json"
    source.write_text("{}", encoding="utf-8")
    receipts = [{"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "url": "https://example.test/source"}]
    document = {
        "schema_version": 1,
        "source_validated": False,
        "historical_publication_claim": False,
        "daily_counts": {"2024-06-28": 1},
        "events": [],
        "coverage": {"receipts": receipts},
        "source_digest": hashlib.sha256(json.dumps(receipts, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
        "protocol_digest": hashlib.sha256(protocol.read_bytes()).hexdigest(),
    }
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps(document), encoding="utf-8")
    assert load_dataset(dataset)["daily_counts"]["2024-06-28"] == 1
    document["protocol_digest"] = "0" * 64
    dataset.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(DataError, match="protocol digest"):
        load_dataset(dataset)


def test_collect_keeps_closed_market_in_denominator_without_fetching_its_candle(tmp_path, monkeypatch):
    sources = tmp_path / "sources"
    sources.mkdir()
    for year in range(2019, 2027):
        (sources / f"tsa_{year}.html").write_text(
            f"<table><tr><th>Date</th><th>Numbers</th></tr><tr><td>1/1/{year}</td><td>1,000</td></tr></table>",
            encoding="utf-8",
        )
    monkeypatch.setattr(collector, "SOURCES", sources)
    monkeypatch.setattr(collector, "START", date(2024, 6, 30))
    monkeypatch.setattr(collector, "END", date(2024, 6, 30))
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    (campaign / "PROTOCOL.md").write_text("frozen", encoding="utf-8")
    live = market(close_time="2024-07-01T03:59:00Z")
    closed = market(ticker="TSAW-24JUN30-A2.45", floor_strike=2_450_000,
                    rules_primary=market()["rules_primary"].replace("2.5", "2.45"),
                    close_time="2024-06-28T14:59:00Z")
    candle_calls = []

    def fetch(url, params):
        if url == collector.CURRENT_CANDLES:
            candle_calls.append(params["market_tickers"])
            entry = int(entry_for(date(2024, 6, 30)).timestamp())
            return {"markets": [{"market_ticker": live["ticker"], "candlesticks": [{
                "end_period_ts": entry, "yes_bid": {"close": 40}, "yes_ask": {"close": 45},
                "volume": 10, "open_interest": 20,
            }]}]}
        if url == collector.CURRENT_MARKETS and params["series_ticker"] == "KXTSAW":
            return {"markets": [live, closed], "cursor": ""}
        return {"markets": [], "cursor": ""}

    data = collector.collect(campaign, fetch=fetch, fetch_html=lambda _: b"", workers=1)
    event = data["events"][0]
    assert event["candles"][live["ticker"]]["yes_ask_close"] == 0.45
    assert event["candles"][closed["ticker"]] is None
    assert event["candle_reasons"][closed["ticker"]] == "market_closed_by_entry"
    assert candle_calls == [live["ticker"]]
    assert data["coverage"]["calendar"][0]["reason"] is None
    assert load_dataset(campaign / "dataset.json")["events"][0]["week_end"] == "2024-06-30"
