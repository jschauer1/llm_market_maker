"""ND-1 cached-history diagnostic. Exp lanes never authorize live calibration.

Run --prepare to freeze coverage and hashes without computing any return.
Then run without --prepare to replay the same theory, checkpoint each ticker,
record train/holdout separately, and report executable returns with uncertainty.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from tools import db, score, theories
from tools.theory import TheoryContext
from . import analysis, data

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAMPAIGN = Path(__file__).resolve().parent / "backtests" / "nd1-cache-20260905"
CATEGORIES = {"Politics", "Elections", "Economics", "Entertainment", "World"}
CUTOFF = int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp())
VALIDATION_END = int(datetime(2026, 8, 18, tzinfo=timezone.utc).timestamp())


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def records(cache: Path, categories: dict):
    conn = sqlite3.connect(cache.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        query = """SELECT s.ticker, s.series_ticker, s.payload, c.payload
                     FROM settled_markets s JOIN candles c USING(ticker)
                    WHERE c.period_interval = 1440 ORDER BY s.ticker"""
        for ticker, series, raw, candles in conn.execute(query):
            category = categories.get(series)
            if category not in CATEGORIES:
                continue
            raw = json.loads(raw)
            raw["series_ticker"] = series
            yield raw, json.loads(candles), category
    finally:
        conn.close()


def prepare(cache: Path, campaign: Path) -> dict:
    category_path = campaign / "series_categories.json"
    protocol_path = campaign / "PROTOCOL.md"
    if not protocol_path.exists():
        raise ValueError("Freeze PROTOCOL.md before preparing the corpus")
    categories = json.loads(category_path.read_text(encoding="utf-8"))["categories"]
    counts = Counter()
    by_category = Counter()
    tickers = []
    for raw, candles, category in records(cache, categories):
        counts["tickers"] += 1
        counts["candles"] += len(candles)
        counts["tickers_with_five_candles"] += len(candles) >= 5
        by_category[category] += 1
        tickers.append(raw["ticker"])
    manifest = {
        "protocol": "ND-1", "cache": str(cache.relative_to(ROOT)),
        "source_digest": digest(cache), "categories_digest": digest(category_path),
        "protocol_digest": digest(protocol_path), "counts": dict(counts),
        "category_counts": dict(by_category), "tickers": tickers,
        "training_end": "2026-08-01T00:00:00Z",
        "validation_end_exclusive": "2026-08-18T00:00:00Z",
        "eligible_for_production": False,
        "limitations": ["insider-screen category and final-volume selection",
                        "45-day histories anchored to realized close",
                        "settled-only partial collection; no population denominator",
                        "current structural category mapping with excluded conflicts",
                        "daily quote closes, no historical depth or guaranteed fills"],
    }
    path = campaign / "manifest.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Frozen manifest changed; create a separately declared campaign")
    else:
        save(path, manifest)
    return {k: v for k, v in manifest.items() if k != "tickers"}


def decision_rows(cache: Path, campaign: Path, source_digest: str) -> list[dict]:
    from .theory import NewsDriftTheory

    category_map = json.loads((campaign / "series_categories.json").read_text(encoding="utf-8"))["categories"]
    checkpoint = campaign / "decisions.jsonl"
    done = set()
    rows = []
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item["source_digest"] != source_digest:
                raise ValueError("Checkpoint belongs to a different source")
            done.add(item["ticker"])
            if item["decision"] is not None:
                rows.append(item["decision"])
    with checkpoint.open("a", encoding="utf-8") as out:
        for raw, candles, category in records(cache, category_map):
            if raw["ticker"] in done:
                continue
            found = None
            theory = NewsDriftTheory(history_loader=lambda m, now: candles,
                                    calibration={})
            for candle in sorted(candles, key=lambda c: c["end_ts"])[4:]:
                ts = candle["end_ts"]
                if ts >= VALIDATION_END:
                    break
                market = data.reconstruct(raw, candles, category, ts)
                if market is None:
                    continue
                ctx = TheoryContext(None, [market], datetime.fromtimestamp(ts, timezone.utc),
                                    run_id="exp/nd1-cache-20260905/discovery",
                                    run_mode="backtest")
                run = theory.start(ctx)
                if not run.candidates:
                    continue
                c = run.candidates[0]
                settled = datetime.fromisoformat(raw["settlement_ts"].replace("Z", "+00:00"))
                if settled.timestamp() <= ts or raw.get("result") not in {"yes", "no"}:
                    continue
                found = {
                    "ticker": raw["ticker"], "event_ticker": c.key,
                    "category": category, "entry_ts": ts, "side": c.fav_side,
                    "entry_price": c.entry_price,
                    "directional_mid": market.mid if c.fav_side == "yes" else 1 - market.mid,
                    "reverse_price": market.no_ask if c.fav_side == "yes" else market.yes_ask,
                    "resolved_ts": int(settled.timestamp()),
                    "settlement_day": settled.date().isoformat(),
                    "result": raw["result"],
                }
                rows.append(found)
                break
            out.write(json.dumps({"ticker": raw["ticker"], "source_digest": source_digest,
                                  "decision": found}) + "\n")
            out.flush()
    return rows


def run_campaign(cache: Path, campaign: Path, conn) -> dict:
    from .theory import NewsDriftTheory

    manifest = prepare(cache, campaign)
    rows = decision_rows(cache, campaign, manifest["source_digest"])
    artifact = analysis.fit_calibration(rows, cutoff_ts=CUTOFF,
                                        source_digest=manifest["source_digest"])
    save(campaign / "diagnostic_calibration.json", artifact)
    train = [r for r in rows if r["entry_ts"] < CUTOFF and r["resolved_ts"] < CUTOFF]
    holdout = [r for r in rows if CUTOFF <= r["entry_ts"] < VALIDATION_END]
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    categories = json.loads((campaign / "series_categories.json").read_text(encoding="utf-8"))["categories"]
    raw_by_ticker = {raw["ticker"]: (raw, candles, cat)
                     for raw, candles, cat in records(cache, categories)}
    counts = {}
    for phase, phase_rows in (("train", train), ("holdout", holdout)):
        run_id = f"exp/nd1-cache-20260905/{phase}"
        if not conn.execute("SELECT 1 FROM backtest_runs WHERE run_id=?", (run_id,)).fetchone():
            score.record_backtest_run(
                conn, run_id, "news_drift", 1, tier="A", uses_llm_judgment=False,
                notes="ND-1 diagnostic only; insider-filtered settled-only cache; exp lane "
                      "excluded from production scores. See " + str(campaign.relative_to(ROOT)),
            )
        count = 0
        positive = []
        for r in phase_rows:
            raw, candles, cat = raw_by_ticker[r["ticker"]]
            m = data.reconstruct(raw, candles, cat, r["entry_ts"])
            theory = NewsDriftTheory(history_loader=lambda m, now: candles,
                                    calibration=artifact if phase == "holdout" else {})
            ctx = TheoryContext.build(conn, [m], datetime.fromtimestamp(r["entry_ts"], timezone.utc),
                                      run_id=run_id, run_mode="backtest")
            result = theory.start(ctx).finish()
            count += len(result.opportunity_ids)
            if any(sc.edge.pts_net > 0 for sc in result.scored):
                positive.append(r)
            existing = conn.execute("SELECT result FROM settlements WHERE kalshi_ticker=?",
                                    (r["ticker"],)).fetchone()
            if existing and existing["result"].lower() != r["result"]:
                raise ValueError(f"Conflicting settlement for {r['ticker']}")
            if not existing:
                score.record_settlement(conn, r["ticker"], r["result"],
                                        datetime.fromtimestamp(r["resolved_ts"], timezone.utc).isoformat())
        counts[phase] = {"run_id": run_id, "recorded": count,
                         "all_signals": analysis.measure(phase_rows),
                         "positive_forecasts": analysis.measure(positive)}
    result = {"protocol": "ND-1", "eligible_for_production": False,
              "calibration": artifact, "phases": counts,
              "limitations": manifest["limitations"],
              "pooled_score": score.compute_score(conn, "news_drift", 1, run_mode="backtest")}
    if result["pooled_score"]["n"] != 0:
        raise AssertionError("Diagnostic campaign contaminated the production score")
    save(campaign / "results.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--cache", type=Path, default=ROOT / "db/history_cache.db")
    args = p.parse_args()
    if args.prepare:
        print(json.dumps(prepare(args.cache, DEFAULT_CAMPAIGN), indent=2))
    else:
        conn = db.connect()
        try:
            print(json.dumps(run_campaign(args.cache, DEFAULT_CAMPAIGN, conn), indent=2))
        finally:
            conn.close()


if __name__ == "__main__":
    main()
