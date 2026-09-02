"""Pass B: per-ticker block-trade rate on the liquid board.

Population and decision rule fixed in PREREG.md before this ran.
Writes one JSON line per ticker as it goes; resumable by skipping
tickers already present in the output file.
"""
import json, os, sys
sys.path.insert(0, os.path.abspath("."))
from tools.db import connect
from tools.board import get_board
from tools.kalshi.trades import trades, TradeFetchError

OUT = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 300
MAX_PAGES = int(sys.argv[3]) if len(sys.argv) > 3 else 3

conn = connect()
board = get_board(conn)          # no force -- the floor owns that
print(f"board: {len(board)} markets", flush=True)

pool = [
    m for m in board
    if m.is_open
    and (m.open_interest or 0) >= 500
    and (m.volume or 0) >= 1000
    and m.spread is not None and m.spread <= 0.05
]
print(f"liquid pool: {len(pool)} markets", flush=True)
pool.sort(key=lambda m: -(m.open_interest or 0))
sample = pool[:N]

done = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        try:
            done.add(json.loads(line)["ticker"])
        except Exception:
            pass
print(f"already done: {len(done)}", flush=True)

tot_tr = tot_bl = mkt_bl = 0
with open(OUT, "a", encoding="utf-8") as fh:
    for i, m in enumerate(sample):
        if m.ticker in done:
            continue
        try:
            rows = trades(m.ticker, max_pages=MAX_PAGES)
            err = None
        except (TradeFetchError, Exception) as exc:
            rows, err = [], f"{type(exc).__name__}: {exc}"
        nb = sum(1 for t in rows if t.is_block_trade)
        rec = {
            "ticker": m.ticker,
            "series": m.series_ticker,
            "open_interest": m.open_interest,
            "volume": m.volume,
            "spread": m.spread,
            "n_trades": len(rows),
            "n_block": nb,
            "oldest": rows[-1].created_time if rows else None,
            "newest": rows[0].created_time if rows else None,
            "max_count": max((t.count for t in rows), default=0),
            "error": err,
        }
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        tot_tr += len(rows); tot_bl += nb; mkt_bl += 1 if nb else 0
        if (i + 1) % 25 == 0:
            print(f"{i+1}/{len(sample)}  trades {tot_tr}  blocks {tot_bl}  mkts-with-block {mkt_bl}", flush=True)
print(f"DONE trades={tot_tr} blocks={tot_bl} markets_with_block={mkt_bl}")
