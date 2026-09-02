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

Run: python theories/no_side_premium/studies/answer/2026-08-29-side-asymmetry-extension/measure.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools import db, snapshot                         # noqa: E402
from tools.kalshi import markets as km                 # noqa: E402
from theories.insider_bias import screen as scr        # noqa: E402

DATA = Path(__file__).resolve().parent / "data"

#: (close day, snapshot captured_at). Each snapshot precedes its day's
#: settlements, which is what makes the price point-in-time.
TARGETS = [
    # The earliest capture in the DB, and the only close-day before 08-25
    # it can price. Added 2026-09-01 to reach an 8th day WITHOUT admitting
    # a partial one -- the decision to add it was recorded before its
    # number was computed (NOTES.md 2026-09-01).
    ("2026-08-24", "2026-08-24T01:34:44Z"),
    # 2026-09-01: the 2026-08-27 study's three days, re-measured here with
    # ITS OWN snapshot pairs (STUDY.md lines 30-34) so the whole series
    # carries one vintage. Re-measuring matters: 08-28 moved +32.60 ->
    # +28.97 and 08-29 +9.49 -> +4.10 once their remaining markets settled,
    # so days frozen at an older settlement state are not comparable to
    # days measured today.
    ("2026-08-25", "2026-08-24T22:34:54Z"),
    ("2026-08-26", "2026-08-24T22:34:54Z"),
    ("2026-08-27", "2026-08-27T01:06:07Z"),
    ("2026-08-28", "2026-08-27T23:18:30Z"),
    # Re-measured 2026-09-01: this day was 24-of-70 settled when first
    # written and the study flagged it "will move". It is complete now.
    ("2026-08-29", "2026-08-29T00:06:13Z"),
    # Added 2026-09-01, per the study's pre-registered follow-on ("re-run
    # with a new (close day, snapshot) pair each session"). The snapshot is
    # always the latest capture preceding the day's settlements.
    ("2026-08-30", "2026-08-29T13:14:32Z"),
    ("2026-08-31", "2026-08-31T00:38:34Z"),
    ("2026-09-01", "2026-09-01T02:06:51Z"),
]


def fee_pts(price: float) -> float:
    return min(0.07 * price * (1.0 - price), 0.035) * 100.0


def population(conn, captured_at: str, close_day: str):
    # NOT `WHERE captured_at = ?`. Dedup-on-write (spec 5.2 phase 2,
    # 2026-08-30) stopped writing a row for a market whose payload did not
    # change, so an exact-stamp filter returns "markets that moved at this
    # pull" -- a liquidity-correlated subset, silently. It costs 46% of the
    # 2026-08-31 board and 24% of 2026-09-01's, and the bias runs straight
    # through side and price, which is exactly what this study measures.
    rows = snapshot.board_as_of(conn, "kalshi", captured_at)
    mkts = []
    for r in rows:
        try:
            mkts.append(km.normalize(
                json.loads(snapshot.payload_text(r["raw_json"]))))
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
