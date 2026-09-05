from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from theories.inflation_nowcast_gap import data
from theories.inflation_nowcast_gap import collect


def test_parse_nowcasts_binds_yearless_dates_across_new_year():
    payload = [{
        "chart": {"subcaption": "2013-12", "_comment": "2026-09-04 00:00"},
        "categories": [{"category": [
            {"label": "12/30"}, {"label": "12/31"}, {"label": "01/02"},
            {"label": "CPI Dec"},
        ]}],
        "dataset": [
            {"seriesname": "CPI Inflation", "data": [
                {"value": "0.21"}, {"value": "0.22"}, {"value": "0.23"}, {"value": ""},
            ]},
            {"seriesname": "Core CPI Inflation", "data": [
                {"value": "0.11"}, {"value": "0.12"}, {"value": "0.13"}, {"value": ""},
            ]},
        ],
    }]

    parsed = data.parse_nowcasts(payload)

    assert parsed["2013-12"]["2014-01-02"] == {
        "CPI Inflation": "0.23", "Core CPI Inflation": "0.13"
    }


def test_parse_nowcasts_rejects_missing_exact_measure():
    payload = [{
        "chart": {"subcaption": "2024-1"},
        "categories": [{"category": [{"label": "01/02"}]}],
        "dataset": [{"seriesname": "CPI Inflation", "data": [{"value": "0.2"}]}],
    }]
    with pytest.raises(data.DataError, match="Core CPI Inflation"):
        data.parse_nowcasts(payload)


def test_parse_bls_archive_index_gets_target_and_release_date():
    html = """
      <a href="/news.release/archives/cpi_01162014.htm">December 2013 Consumer Price Index</a>
      <a href="/news.release/archives/cpi_12172013.htm">November 2013 Consumer Price Index</a>
      <a href="/news.release/archives/cpi_01162014.pdf">PDF</a>
    """
    rows = data.parse_bls_archive_index(html)
    assert rows == [
        {"target_month": "2013-11", "release_date": "2013-12-17", "url": "https://www.bls.gov/news.release/archives/cpi_12172013.htm"},
        {"target_month": "2013-12", "release_date": "2014-01-16", "url": "https://www.bls.gov/news.release/archives/cpi_01162014.htm"},
    ]


def test_parse_first_release_uses_embargo_timestamp_and_signed_monthly_values():
    html = """<html><body><pre>
    Transmission of material in this release is embargoed until
    8:30 a.m. (EST) Wednesday, January 16, 2014 USDL-14-0037
    Consumer Price Index - December 2013
    The Consumer Price Index for All Urban Consumers (CPI-U) increased
    0.3 percent in December on a seasonally adjusted basis.
    The index for all items less food and energy rose 0.1 percent in December.
    </pre></body></html>"""
    parsed = data.parse_bls_first_release(html, "2013-12")
    assert parsed["headline"] == "0.3"
    assert parsed["core"] == "0.1"
    assert parsed["published_at"] == "2014-01-16T08:30:00-05:00"


def test_parse_first_release_handles_decline_and_unchanged():
    html = """<pre>
    embargoed until 8:30 a.m. (EDT) Thursday, August 15, 2013
    Consumer Price Index - July 2013
    The Consumer Price Index for All Urban Consumers (CPI-U) declined 0.2 percent in July on a seasonally adjusted basis.
    The index for all items less food and energy was unchanged in July.
    </pre>"""
    parsed = data.parse_bls_first_release(html, "2013-07")
    assert parsed["headline"] == "-0.2"
    assert parsed["core"] == "0.0"


def test_parse_first_release_accepts_modern_generic_et_and_uppercase_title():
    html = """<pre>
    Transmission of material in this release is embargoed until 8:30 a.m. (ET) August 10, 2022
    CONSUMER PRICE INDEX - JULY 2022
    The Consumer Price Index for All Urban Consumers (CPI-U) was unchanged in July on a seasonally adjusted basis.
    The index for all items less food and energy rose 0.3 percent in July.
    </pre>"""
    parsed = data.parse_bls_first_release(html, "2022-07")
    assert parsed == {"headline": "0.0", "core": "0.3", "published_at": "2022-08-10T08:30:00-04:00"}


def test_parse_first_release_accepts_seasonal_phrase_before_month_and_implicit_core_month():
    html = """<pre>
    embargoed until 8:30 a.m. (ET) Wednesday, August 12, 2026
    CONSUMER PRICE INDEX - JULY 2026
    The Consumer Price Index for All Urban Consumers (CPI-U) increased 0.1 percent on a seasonally adjusted basis in July.
    The index for all items less food and energy rose 0.2 percent after being unchanged in June.
    </pre>"""
    parsed = data.parse_bls_first_release(html, "2026-07")
    assert parsed["headline"] == "0.1"
    assert parsed["core"] == "0.2"


def test_entry_for_uses_latest_source_business_day_and_dst():
    release = datetime(2024, 3, 12, 8, 30, tzinfo=ZoneInfo("America/New_York"))
    entry = data.entry_for(release, ["2024-03-08", "2024-03-11"])
    assert entry.isoformat() == "2024-03-11T12:00:00-04:00"
    assert data.entry_for(release, ["2024-03-08"]).date().isoformat() == "2024-03-08"
    with pytest.raises(data.DataError, match="last source business day"):
        data.entry_for(release, ["2024-03-06"])


def test_parse_contract_requires_exact_series_month_and_strict_above():
    raw = {
        "ticker": "KXCPI-26MAY-T0.3", "event_ticker": "KXCPI-26MAY",
        "strike_type": "greater", "floor_strike": 0.3,
        "rules_primary": "If the Consumer Price Index (CPI) increases by more than 0.3% (single-decimal) in May 2026, then the market resolves to Yes.",
    }
    parsed, reason = data.parse_contract(raw)
    assert reason is None
    assert parsed == {"series_ticker": "KXCPI", "event_ticker": "KXCPI-26MAY", "target_month": "2026-05", "strike": Decimal("0.3")}
    raw["rules_primary"] = raw["rules_primary"].replace("more than", "at least")
    assert data.parse_contract(raw)[1] == "rules_not_strict_above"


def test_normalize_candle_requires_exact_end_and_converts_legacy_cents():
    payload = {"candlesticks": [{
        "end_period_ts": 1710172800,
        "yes_bid": {"close": 47}, "yes_ask": {"close_dollars": "0.5200"},
        "volume": 3, "open_interest": 120,
    }]}
    bar = data.normalize_candle(payload, 1710172800)
    assert bar == {
        "end_ts": 1710172800, "yes_bid_close": "0.47", "yes_ask_close": "0.5200",
        "open_interest": "120", "volume": "3",
    }
    with pytest.raises(data.DataError, match="exactly one"):
        data.normalize_candle(payload, 1710176400)


def test_load_dataset_verifies_protocol_source_and_raw_receipts(tmp_path: Path, monkeypatch):
    protocol = tmp_path / "PROTOCOL.md"
    protocol.write_text("frozen", encoding="utf-8")
    raw = tmp_path / "raw.json"
    raw.write_text("{}", encoding="utf-8")
    receipt = {"path": "raw.json", "sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}
    critical = {"training_rows": [], "events": [], "receipts": [receipt]}
    dataset = {
        "schema_version": "inflation-nowcast-gap/v1", "campaign": "x",
        "collected_at": "2026-09-05T12:00:00+00:00",
        "protocol_digest": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "source_digest": hashlib.sha256(json.dumps(critical, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "sources": {"cleveland": {}, "bls": [], "kalshi": {"receipts": [receipt]}},
        "training_rows": [], "events": [], "coverage": {}, "_receipts": [receipt],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    monkeypatch.setattr(data, "ROOT", tmp_path)
    assert data.load_dataset(path)["campaign"] == "x"
    raw.write_text("tampered", encoding="utf-8")
    with pytest.raises(data.DataError, match="receipt digest"):
        data.load_dataset(path)


def test_make_training_rows_selects_latest_pre_release_vintage_for_both_series():
    nowcasts = {"2024-02": {
        "2024-03-08": {"CPI Inflation": "0.19", "Core CPI Inflation": "0.28"},
        "2024-03-11": {"CPI Inflation": "0.21", "Core CPI Inflation": "0.31"},
    }}
    releases = {"2024-02": {
        "target_month": "2024-02", "published_at": "2024-03-12T08:30:00-04:00",
        "headline": "0.4", "core": "0.4", "sha256": "b" * 64,
    }}
    rows, excluded = collect.make_training_rows(nowcasts, releases, "a" * 64)
    assert excluded == {}
    assert [row["series_ticker"] for row in rows] == ["KXCPI", "KXCPICORE"]
    assert rows[0]["forecast_observation_date"] == "2024-03-11"
    assert rows[0]["cutoff_ts"] == "2024-03-11T12:00:00-04:00"
    assert rows[0]["forecast_value"] == "0.21"
    assert rows[0]["actual_value"] == "0.4"
