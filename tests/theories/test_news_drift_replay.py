"""Replay records the real procedure, while experiments stay out of ranking."""
from datetime import datetime, timezone
import json
import sqlite3


def test_replay_records_real_entries_and_quarantines_biased_training(tmp_path, monkeypatch):
    from theories.news_drift import backtest
    from tools import db

    monkeypatch.setattr(backtest, "ROOT", tmp_path)
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    (campaign / "PROTOCOL.md").write_text("Frozen synthetic test", encoding="utf-8")
    (campaign / "series_categories.json").write_text(
        json.dumps({"categories": {"KXTEST": "Politics"}}), encoding="utf-8")
    cache = tmp_path / "history.db"
    source = sqlite3.connect(cache)
    source.execute("CREATE TABLE settled_markets (ticker TEXT, series_ticker TEXT, payload TEXT)")
    source.execute("CREATE TABLE candles (ticker TEXT, period_interval INTEGER, payload TEXT)")
    for day in ("2026-07-20", "2026-08-02"):
        ts = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())
        ticker = f"KXTEST-{day}-Y"
        raw = {"ticker": ticker, "event_ticker": f"KXTEST-{day}",
               "close_time": datetime.fromtimestamp(ts + 3600, timezone.utc).isoformat(),
               "settlement_ts": datetime.fromtimestamp(ts + 7200, timezone.utc).isoformat(),
               "result": "yes", "yes_bid_dollars": "1", "volume_fp": "999999"}
        candles = [{"end_ts": ts - (4 - i) * 86400,
                    "yes_bid_close": mid - .01, "yes_ask_close": mid + .01,
                    "volume": volume, "open_interest": 200}
                   for i, (mid, volume) in enumerate(zip(
                       [.30, .31, .30, .50, .55], [10, 10, 10, 20, 30]))]
        source.execute("INSERT INTO settled_markets VALUES (?,?,?)", (ticker, "KXTEST", json.dumps(raw)))
        source.execute("INSERT INTO candles VALUES (?,1440,?)", (ticker, json.dumps(candles)))
    source.commit()
    source.close()
    conn = db.connect(":memory:")
    db.init_db(conn)
    manifest = backtest.prepare(cache, campaign)
    assert manifest["counts"]["tickers"] == 2
    result = backtest.run_campaign(cache, campaign, conn)
    assert result["phases"]["train"]["recorded"] == 1
    assert result["phases"]["holdout"]["recorded"] == 1
    assert result["pooled_score"]["n"] == 0
    attempts = conn.execute("SELECT decision_date, entry_price, edge_basis FROM opportunity_attempts ORDER BY decision_date").fetchall()
    assert [r["decision_date"] for r in attempts] == ["2026-07-20", "2026-08-02"]
    assert all(abs(r["entry_price"] - .56) < 1e-10 for r in attempts)
    assert all(r["edge_basis"] == "prior" for r in attempts)  # no usable training sample
    backtest.run_campaign(cache, campaign, conn)
    assert conn.execute("SELECT COUNT(*) FROM opportunity_attempts").fetchone()[0] == 2
    conn.close()
