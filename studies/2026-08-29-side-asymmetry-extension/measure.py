"""Extend the 2026-08-27 settlement-day-clustering study by two close-days.

Method is that study's, unchanged, so the days compose into one series:

  population = theories.insider_bias.screen.screen() at pinned defaults,
  run over a point-in-time board snapshot captured BEFORE the day's
  settlements, restricted to markets whose close_time falls on the target
  day. Outcome fetched now. Edge = (win_rate - mean favorite ask) * 100,
  net of min(0.07*P*(1-P), 0.035), exactly as tools/score.py computes it.

What this adds: the paired WITHIN-DAY NO-minus-YES statistic, which is the
quantity no_side_premium actually claims. The day effect cancels in the
pairing, so it has far more power per day than the pooled calibration edge
the theory is currently scored on.

Run: python studies/2026-08-29-side-asymmetry-extension/measure.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import db                                   # noqa: E402
from tools.kalshi import markets as km                 # noqa: E402
from theories.insider_bias import screen as scr        # noqa: E402

DATA = Path(__file__).resolve().parent / "data"

#: (close day, snapshot captured_at). Each snapshot precedes its day's
#: settlements, which is what makes the price point-in-time.
TARGETS = [
    ("2026-08-28", "2026-08-27T23:18:30Z"),
    ("2026-08-29", "2026-08-29T00:06:13Z"),
]


def fee_pts(price: float) -> float:
    return min(0.07 * price * (1.0 - price), 0.035) * 100.0


def population(conn, captured_at: str, close_day: str):
    rows = conn.execute(
        "SELECT raw_json FROM market_snapshots "
        "WHERE captured_at = ? AND platform = 'kalshi'",
        (captured_at,),
    ).fetchall()
    mkts = []
    for r in rows:
        try:
            mkts.append(km.normalize(json.loads(r["raw_json"])))
        except Exception:
            continue
    # `now` MUST be the snapshot's own capture time. screen() filters on
    # days-to-close, so defaulting to the wall clock drops every market
    # that has since closed -- i.e. exactly the settled population this
    # study measures. Left as the default it returns ~0 rows.
    now = datetime.strptime(captured_at, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    cands = scr.screen(mkts, now=now)
    out = []
    for c in cands:
        leg = c.legs[0]
        if (leg.market.close_time or "")[:10] != close_day:
            continue
        out.append({"ticker": leg.market.ticker, "side": leg.side,
                    "ask": leg.price, "title": leg.market.title})
    return out


def main() -> None:
    conn = db.connect()
    DATA.mkdir(parents=True, exist_ok=True)
    series = []
    for close_day, captured_at in TARGETS:
        pop = population(conn, captured_at, close_day)
        tickers = [p["ticker"] for p in pop]
        quotes = km.quotes(tickers) if tickers else {}
        for p in pop:
            m = quotes.get(p["ticker"])
            p["result"] = getattr(m, "result", None) if m else None
            p["status"] = getattr(m, "status", None) if m else None
        settled = [p for p in pop if p["result"] in ("yes", "no")]
        path = DATA / f"close-{close_day}.json"
        path.write_text(json.dumps(
            {"close_day": close_day, "captured_at": captured_at,
             "n_population": len(pop), "n_settled": len(settled),
             "markets": pop}, indent=1))
        series.append((close_day, settled))
        print(f"{close_day}: population {len(pop)}, settled {len(settled)} "
              f"-> {path.name}")

    def edge(rs):
        if not rs:
            return None
        wr = sum(r["result"] == r["side"] for r in rs) / len(rs)
        ask = sum(r["ask"] for r in rs) / len(rs)
        fee = sum(fee_pts(r["ask"]) for r in rs) / len(rs)
        return {"n": len(rs), "win_rate": round(wr, 4),
                "implied": round(ask, 4),
                "edge": round((wr - ask) * 100, 2),
                "net": round((wr - ask) * 100 - fee, 2)}

    print()
    print("close day  | all favorites            | YES                      "
          "| NO                       | NO-YES net")
    for day, settled in series:
        a = edge(settled)
        y = edge([r for r in settled if r["side"] == "yes"])
        n = edge([r for r in settled if r["side"] == "no"])
        d = (round(n["net"] - y["net"], 2)
             if (y and n) else None)
        def f(e):
            return (f"n={e['n']:<3} net={e['net']:+7.2f}" if e else "n=0")
        print(f"{day} | {f(a):24} | {f(y):24} | {f(n):24} | {d}")


if __name__ == "__main__":
    main()
