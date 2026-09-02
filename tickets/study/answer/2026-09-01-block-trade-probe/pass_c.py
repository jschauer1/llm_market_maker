"""Pass C: block rate on a RANDOM board-wide sample, no liquidity filter."""
import json, os, sys, random
sys.path.insert(0, os.path.abspath("."))
from tools.db import connect
from tools.board import get_board
from tools.kalshi.trades import trades

OUT = sys.argv[1]; N = int(sys.argv[2]); MAX_PAGES = int(sys.argv[3])
conn = connect()
board = [m for m in get_board(conn) if m.is_open]
random.Random(20260901).shuffle(board)
sample = board[:N]
done = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(line)["ticker"])
        except Exception: pass
tot = bl = mk = 0
with open(OUT, "a", encoding="utf-8") as fh:
    for i, m in enumerate(sample):
        if m.ticker in done: continue
        try:
            rows = trades(m.ticker, max_pages=MAX_PAGES); err = None
        except Exception as exc:
            rows, err = [], f"{type(exc).__name__}: {exc}"
        nb = sum(1 for t in rows if t.is_block_trade)
        fh.write(json.dumps({
            "ticker": m.ticker, "series": m.series_ticker,
            "open_interest": m.open_interest, "volume": m.volume,
            "spread": m.spread, "n_trades": len(rows), "n_block": nb,
            "oldest": rows[-1].created_time if rows else None,
            "max_count": max((t.count for t in rows), default=0), "error": err,
        }) + "\n"); fh.flush()
        tot += len(rows); bl += nb; mk += 1 if nb else 0
        if (i+1) % 50 == 0: print(f"{i+1}/{N} trades {tot} blocks {bl} mkts {mk}", flush=True)
print(f"DONE trades={tot} blocks={bl} markets_with_block={mk}")
