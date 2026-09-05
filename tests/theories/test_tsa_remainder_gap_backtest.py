from datetime import datetime, timezone
import json

import pytest

from theories.tsa_remainder_gap import backtest


def test_frozen_evidence_cannot_be_replaced(tmp_path):
    path = tmp_path / "decisions.json"
    backtest.freeze(path, [{"ticker": "A", "side": "no"}])
    backtest.freeze(path, [{"ticker": "A", "side": "no"}])
    with pytest.raises(ValueError, match="changed"):
        backtest.freeze(path, [{"ticker": "B", "side": "yes"}])
    assert json.loads(path.read_text())[0]["ticker"] == "A"


def test_reconstruction_strips_outcomes_and_terminal_liquidity(monkeypatch):
    from theories.tsa_remainder_gap import data
    from datetime import date
    monkeypatch.setattr(data, "parse_contract", lambda raw: (
        {"week_end": date(2026, 8, 30), "strike": 2300000}, None))
    entry = datetime(2026, 8, 28, 15, tzinfo=timezone.utc)
    event = {"week_end": "2026-08-30", "event_ticker": "KXTSAW-26AUG30",
             "entry_time": entry.isoformat()}
    raw = {"ticker": "KXTSAW-26AUG30-A2.30", "rules_primary": "TSA rules",
           "rules_secondary": "the full terms", "result": "yes",
           "expiration_value": "2400000", "volume": 999999999,
           "open_interest": 999999999, "yes_ask_dollars": "1.00",
           "close_time": "2026-08-31T03:59:00Z",
           "open_time": "2026-08-25T00:00:00Z"}
    candle = {"end_ts": int(entry.timestamp()), "yes_bid_close": .32,
              "yes_ask_close": .36, "open_interest": 123, "volume": 8}
    market, reason = backtest.reconstruct(raw, event, candle, "source-sha")
    assert reason is None
    assert market.result is None and market.volume == 8
    assert market.open_interest == 123 and market.yes_ask == .36
    assert market.no_ask == pytest.approx(.68)
    assert not {"result", "expiration_value", "settlement_ts"} & market.raw.keys()
    assert market.close_time > entry.isoformat()
    raw["close_time"] = "2026-08-27T00:00:00Z"
    assert backtest.reconstruct(raw, event, candle, "source-sha")[1] == "closed_before_entry"
    raw["close_time"] = "2026-08-31T03:59:00Z"
    candle["end_ts"] += 3600
    assert backtest.reconstruct(raw, event, candle, "source-sha")[1] == "missing_exact_candle"


def test_pending_bounds_and_rounded_fees_never_imply_source_validity():
    rows = [dict(week_end="2026-08-30", settlement_day="2026-09-01",
                 side="yes", price=.35, result="yes"),
            dict(week_end="2026-09-06", settlement_day=None,
                 side="no", price=.60, result=None)]
    report = backtest.summarize(rows)
    assert report["positions"] == 2 and report["settled"] == 1
    assert report["pending"] == 1
    assert report["source_validated"] is False
    assert report["supported"] is False
    assert report["rounded_mean_net_pts"] == pytest.approx(63.0)
    assert report["pending_net_bounds"][1] - report["pending_net_bounds"][0] == pytest.approx(50)


def test_replay_records_once_and_excludes_experiment_from_production(conn, tmp_path, monkeypatch):
    import hashlib
    from datetime import timedelta
    from tools import score, theories
    from tests.theories.test_tsa_remainder_gap import _counts, _market, WEEK_END

    monkeypatch.setattr(backtest, "START", WEEK_END - timedelta(days=7))
    monkeypatch.setattr(backtest, "SPLIT", WEEK_END)
    monkeypatch.setattr(backtest, "END", WEEK_END)
    theories.register(conn, "tsa_remainder_gap", "TSA", "theories/tsa_remainder_gap")
    (tmp_path / "PROTOCOL.md").write_text("Synthetic protocol", encoding="utf-8")
    receipt = tmp_path / "source.json"
    receipt.write_text("{}", encoding="utf-8")
    receipts = [{"path": str(receipt), "sha256": backtest.digest(receipt)}]
    source_digest = hashlib.sha256(json.dumps(
        receipts, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    market = _market()
    raw = {**market.raw, "result": "yes", "settlement_ts": "2026-09-07T14:00:00Z",
           "close_time": market.close_time, "expiration_value": "201"}
    event = {"week_end": WEEK_END.isoformat(), "event_ticker": market.event_ticker,
             "entry_time": market.raw["entry_time"], "markets": [raw],
             "candles": {market.ticker: {
                 "end_ts": int(backtest.instant(market.raw["entry_time"]).timestamp()),
                 "yes_bid_close": market.yes_bid, "yes_ask_close": market.yes_ask,
                 "open_interest": 200, "volume": 10}}}
    dataset = {"schema_version": 1, "source_validated": False,
               "historical_publication_claim": False, "daily_counts": _counts(),
               "events": [event], "coverage": {"receipts": receipts},
               "source_digest": source_digest,
               "protocol_digest": backtest.digest(tmp_path / "PROTOCOL.md")}
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    first = backtest.replay(conn, tmp_path, now=now)
    second = backtest.replay(conn, tmp_path, now=now)
    assert first["partitions"]["holdout"]["settled"] == 1
    assert second["partitions"]["holdout"]["positions"] == 1
    assert conn.execute("SELECT count(*) FROM opportunities WHERE theory_id='tsa_remainder_gap'").fetchone()[0] == 1
    assert score.compute_score(conn, "tsa_remainder_gap", 1, ("live", "backtest"))["n"] == 0
    dataset["daily_counts"]["2026-09-01"] = 101
    path.write_text(json.dumps(dataset), encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        backtest.replay(conn, tmp_path, now=now)
