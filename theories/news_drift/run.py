"""One floor command: batch history, recheck quotes, run the theory, record."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from tools import db, slices, theories
from tools.domain import Market
from tools.kalshi.markets import OPEN_STATUSES
from tools.theory import TheoryContext
from .live import collect_live, DEFAULT_DATA_DIR
from .theory import NewsDriftTheory


def record_collection(conn, collection: dict, *, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    quoted = datetime.fromisoformat(collection["quotes"]["fetch_completed_at"].replace("Z", "+00:00"))
    if quoted.tzinfo is None or not 0 <= (now - quoted).total_seconds() <= 1800:
        raise ValueError("Collection quotes are stale or future-dated; collect fresh quotes")
    board = []
    for row in collection["signals"]:
        q = row["quote"]
        market = Market.from_mapping({
            **q, "platform": "kalshi", "ticker": row["ticker"],
            "title": row.get("title"), "event_ticker": row.get("event_ticker"),
            "series_ticker": row.get("series_ticker"), "event": row["event"],
            "is_open": q["status"] in OPEN_STATUSES,
        })
        board.append(market)
    theories.register(conn, "news_drift", "News Drift", "theories/news_drift")
    histories = collection["history"]["rows_by_ticker"]
    theory = NewsDriftTheory(history_loader=lambda m, now: histories.get(m.ticker))
    ctx = TheoryContext.build(conn, board, quoted,
                              run_id=f"nd1-live-{quoted.strftime('%Y%m%dT%H%M%SZ')}")
    return theory.start(ctx).finish()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--collection", type=Path, help="reuse a complete artifact with quotes under 30 minutes old")
    args = p.parse_args()
    if args.collection:
        path = args.collection
        collection = json.loads(path.read_text(encoding="utf-8"))
    else:
        path = DEFAULT_DATA_DIR / f"nd1-live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        collection = collect_live(out_path=path)
    conn = db.connect()
    try:
        result = record_collection(conn, collection)
        subsets = []
        for subset in slices.list_slices(conn, "news_drift"):
            matches = slices.build_matcher(json.loads(subset["predicate_json"]))
            selected = [sc for sc in result.scored if matches({
                "outcome": sc.candidate.fav_side, "entry_price": sc.candidate.entry_price,
                "confidence": sc.confidence, "extra": sc.extra,
            })]
            supported = sum(sc.edge.pts_net > 0 for sc in selected)
            subsets.append({"slug": subset["slug"], "candidates": len(selected),
                            "supported_candidates": supported,
                            "reason": "no matching parent signals" if not selected else
                            ("no usable positive calibration" if not supported else "priced; check independent evidence and execution")})
        summary = {
            "collection": str(path), "quote_time": collection["quotes"]["fetch_completed_at"],
            "opportunity_ids": list(result.opportunity_ids),
            "funnel": collection["funnel"], "theory_funnel": result.funnel,
            "supported_candidates": sum(sc.edge.pts_net > 0 for sc in result.scored),
            "calibration_statuses": sorted({sc.extra["calibration_status"] for sc in result.scored}),
            "sub_theories": subsets,
        }
        path.with_suffix(".recorded.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
