from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest


def make_cohort(path):
    from theories.news_drift.collect_charts import SERIES

    path.mkdir()
    (path / "PROTOCOL.md").write_text("Synthetic frozen ND-1 population", encoding="utf-8")
    (path / "previously_exposed_events.json").write_text('{"event_tickers": []}', encoding="utf-8")
    (path / "series_categories.json").write_text(
        json.dumps({"categories": {s: "Entertainment" for s in SERIES}}), encoding="utf-8")
    (path / "manifest.json").write_text(json.dumps({
        "coverage_complete": True, "series": list(SERIES),
        "window": {"start_ts": int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()),
                   "end_ts": int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())},
        "markets": {"unique": 60}, "candles": {"stored": 60, "missing_requests": []},
    }), encoding="utf-8")
    conn = sqlite3.connect(path / "history.db")
    conn.execute("CREATE TABLE settled_markets (ticker TEXT, series_ticker TEXT, payload TEXT)")
    conn.execute("CREATE TABLE candles (ticker TEXT, period_interval INTEGER, payload TEXT)")
    for start in (datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 5, 1, tzinfo=timezone.utc)):
        for i in range(30):
            entered = start + timedelta(days=i)
            ts = int(entered.timestamp())
            ticker = f"KXTOPSONG-{entered.strftime('%y%m%d')}-Y"
            raw = {"ticker": ticker, "event_ticker": ticker.rsplit("-", 1)[0],
                   "close_time": (entered + timedelta(hours=1)).isoformat(),
                   "settlement_ts": (entered + timedelta(hours=2)).isoformat(), "result": "yes"}
            bars = [{"end_ts": ts - (4 - j) * 86400,
                     "yes_bid_close": mid - .01, "yes_ask_close": mid + .01,
                     "volume": vol, "open_interest": 200}
                    for j, (mid, vol) in enumerate(zip([.3, .3, .3, .5, .55], [10, 10, 10, 20, 30]))]
            conn.execute("INSERT INTO settled_markets VALUES (?,?,?)", (ticker, "KXTOPSONG", json.dumps(raw)))
            conn.execute("INSERT INTO candles VALUES (?,1440,?)", (ticker, json.dumps(bars)))
    conn.commit()
    conn.close()


def test_partial_or_changed_source_cannot_become_clean_validation(tmp_path, monkeypatch):
    from theories.news_drift import backtest_charts as bt

    monkeypatch.setattr(bt, "ROOT", tmp_path)
    campaign = tmp_path / "cohort"
    make_cohort(campaign)
    bt.freeze_manifest(campaign)
    p = campaign / "manifest.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["coverage_complete"] = False
    p.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Incomplete"):
        bt.freeze_manifest(campaign)
    raw["coverage_complete"] = True
    p.write_text(json.dumps(raw), encoding="utf-8")
    connection = sqlite3.connect(campaign / "history.db")
    connection.execute("INSERT INTO candles VALUES ('EXTRA',1440,'[]')")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="changed"):
        bt.freeze_manifest(campaign)


def test_clean_holdout_uses_frozen_model_before_its_result_is_known(tmp_path, monkeypatch):
    from tools import db
    from theories.news_drift import backtest_charts as bt, theory

    monkeypatch.setattr(bt, "ROOT", tmp_path)
    monkeypatch.setattr(theory, "REPO_ROOT", tmp_path)
    campaign = tmp_path / "cohort"
    make_cohort(campaign)
    conn = db.connect(":memory:")
    db.init_db(conn)
    result = bt.replay(campaign, conn)
    holdout = result["phases"]["holdout"]
    assert result["phases"]["train"]["recorded"] == 30
    assert holdout["recorded"] == 30
    assert holdout["positive_forecasts"]["n"] == 30
    assert result["calibration"]["eligible_for_production"] is False
    recorded = conn.execute(
        "SELECT edge_basis, model_prob, edge_pts_net FROM opportunity_attempts WHERE run_id=?",
        (bt.VALIDATION_RUN,),
    ).fetchall()
    assert len(recorded) == 30
    assert all(r["edge_basis"] == "model" and r["model_prob"] == 1.0
               and r["edge_pts_net"] > 0 for r in recorded)
    assert holdout["unexposed_positive_forecasts"]["positive_statistical_bar"] is True
    conn.close()
