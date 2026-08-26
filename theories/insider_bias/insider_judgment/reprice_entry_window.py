"""Reprice every judged market at a fixed 3-to-2-days-before-close entry.

Analysis, not procedure (2026-08-26, user-directed): the judged backtests
enter at each market's FIRST screen-qualifying day inside the 14-day
window, but the user's live experience favors entries a couple of days
before close. Rather than merely filtering the first-qualifying entries
by timing (which conflates "when it first qualified" with "when you
entered"), this replays a uniform strategy from the durable candle cache:

    At the daily candle closest to close-minus-2.5 days (accepted only
    within [close-3d, close-2d]), apply the unmodified screen conditions
    (favorite side by mid, ask in [0.65, 0.97], spread <= 0.07, running
    volume >= 500 reconstructed with the same warm-up undercount as the
    original walk), buy the favorite at that snapshot's ask, and attach
    the market's judged bucket.

The snapshot rule is fixed and outcome-independent, so this is tier-A
mechanics layered on the tier-B buckets (whose assignment was made blind
and is unchanged). The favorite side at this snapshot may differ from
the first-qualifying entry's side; that is the point — it is what a
2.5-days-out bettor would actually have seen. Markets whose candles are
not in the cache, or that have no candle / fail the screen inside the
window, are counted and reported, never silently dropped.

Run:  python -m theories.insider_bias.insider_judgment.reprice_entry_window
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from tools.kalshi import cache as history_cache
from tools.sizing import fee_pts
from theories.insider_bias import screen

JUDGED_RUN_PREFIX = "backtest-2026-08-26-insider-judged-%"
SOURCE_RUN = "backtest-2026-08-25-insider-fullcov"
WINDOW_LO_DAYS = 3.0
WINDOW_HI_DAYS = 2.0
TARGET_DAYS = 2.5


def _parse_ts(iso):
    if not iso:
        return None
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def binom_p(k, n, probs):
    dp = [1.0]
    for p in probs:
        nd = [0.0] * (len(dp) + 1)
        for i, v in enumerate(dp):
            nd[i] += v * (1 - p)
            nd[i + 1] += v * p
        dp = nd
    return sum(dp[k:])


def load_judged(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """select o.kalshi_ticker, o.confidence, o.extra_json, s.result
           from opportunities o
           join settlements s on s.kalshi_ticker = o.kalshi_ticker
           where o.run_id like ? and s.result in ('yes','no')""",
        (JUDGED_RUN_PREFIX,),
    ).fetchall()
    out = []
    for r in rows:
        x = json.loads(r["extra_json"])
        out.append(dict(ticker=r["kalshi_ticker"], bucket=r["confidence"],
                        event=x["event_ticker"], result=r["result"],
                        diverge=x.get("rules_diverge_from_title")))
    return out


def snapshot(cache_conn: sqlite3.Connection, ticker: str,
             close_ts: int) -> dict | None:
    """The market state at the candle nearest close-2.5d, or a skip reason."""
    row = cache_conn.execute(
        "SELECT payload FROM candles WHERE ticker = ? AND period_interval = 1440",
        (ticker,),
    ).fetchone()
    if row is None:
        return {"skip": "no_cache"}
    candles = json.loads(row[0])
    if not candles:
        return {"skip": "no_candles"}
    lo = close_ts - int(WINDOW_LO_DAYS * 86400)
    hi = close_ts - int(WINDOW_HI_DAYS * 86400)
    target = close_ts - int(TARGET_DAYS * 86400)
    in_window = [c for c in candles if lo <= c["end_ts"] <= hi]
    if not in_window:
        return {"skip": "no_candle_in_window"}
    best = min(in_window, key=lambda c: abs(c["end_ts"] - target))
    yes_bid, yes_ask = best.get("yes_bid_close"), best.get("yes_ask_close")
    if yes_bid is None or yes_ask is None:
        return {"skip": "no_quotes"}
    running_volume = sum((c.get("volume") or 0.0) for c in candles
                        if c["end_ts"] <= best["end_ts"])
    mid = (yes_bid + yes_ask) / 2.0
    side = "yes" if mid >= 0.5 else "no"
    price = yes_ask if side == "yes" else 1.0 - yes_bid
    spread = yes_ask - yes_bid
    if not (screen.MIN_FAVORITE_PRICE <= price <= screen.MAX_FAVORITE_PRICE):
        return {"skip": "price_band"}
    if spread > screen.MAX_SPREAD:
        return {"skip": "spread"}
    if running_volume < screen.MIN_VOLUME:
        return {"skip": "volume"}
    return {"side": side, "price": price}


def main() -> None:
    conn = sqlite3.connect("db/market_edge.db")
    conn.row_factory = sqlite3.Row
    close_by_ticker = {}
    for r in conn.execute(
        "select kalshi_ticker, extra_json from opportunities where run_id = ?",
        (SOURCE_RUN,),
    ):
        x = json.loads(r["extra_json"])
        close_by_ticker[r["kalshi_ticker"]] = int(
            x["entry_day_ts"] + x["days_to_close_at_entry"] * 86400)

    cache_conn = history_cache.connect()
    judged = load_judged(conn)
    skips = defaultdict(int)
    bets = []
    for j in judged:
        close_ts = close_by_ticker.get(j["ticker"])
        if close_ts is None:
            skips["no_close_time"] += 1
            continue
        snap = snapshot(cache_conn, j["ticker"], close_ts)
        if snap is None or "skip" in snap:
            skips[snap["skip"]] += 1
            continue
        won = j["result"] == snap["side"]
        bets.append(dict(bucket=j["bucket"], side=snap["side"],
                         p=snap["price"], won=won, event=j["event"],
                         diverge=j["diverge"],
                         net=((1.0 if won else 0.0) - snap["price"]) * 100
                             - fee_pts(snap["price"])))
    print(f"judged rows: {len(judged)}; repriced bets at 3-2d: {len(bets)}; "
          f"skips: {dict(skips)}")

    def cell(sub, label):
        n = len(sub)
        if n == 0:
            print(f"{label:26s} n=0")
            return
        wins = sum(d["won"] for d in sub)
        probs = [d["p"] for d in sub]
        net = sum(d["net"] for d in sub) / n
        ev = len(set(d["event"] for d in sub))
        print(f"{label:26s} n={n:4d} ev={ev:4d} win={wins/n:.3f} "
              f"price={sum(probs)/n:.3f} net={net:+6.2f} "
              f"p_fair={binom_p(wins, n, probs):.4f}")

    print("\n=== uniform 3-2d entry, bucket x side ===")
    for b in ("strong", "moderate", "weak"):
        for side in ("no", "yes"):
            cell([d for d in bets if d["bucket"] == b and d["side"] == side],
                 f"{b} {side.upper()}")
    print()
    cell([d for d in bets if d["side"] == "no"], "ALL NO")
    cell([d for d in bets if d["side"] == "yes"], "ALL YES")
    cell([d for d in bets
          if d["side"] == "no" and d["bucket"] in ("strong", "moderate")],
         "BET RULE str+mod NO")
    cell(bets, "EVERYTHING")


if __name__ == "__main__":
    main()
