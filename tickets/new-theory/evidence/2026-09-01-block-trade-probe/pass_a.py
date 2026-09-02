"""Pass A: board-wide block-trade base rate.

Walks Kalshi's board-wide trade feed (no ticker filter) newest-first and
counts is_block_trade. Writes every page to JSONL as it goes -- the fetch
is the expensive part and a dead session must not cost it.
"""
import json, sys, os, time
sys.path.insert(0, os.path.abspath("."))
from tools.http import get_json
from tools.kalshi.markets import BASE_URL

OUT = sys.argv[1]
MAX_PAGES = int(sys.argv[2]) if len(sys.argv) > 2 else 40

cursor = None
seen = set()
n = 0
blocks = 0
with open(OUT, "a", encoding="utf-8") as fh:
    for page in range(MAX_PAGES):
        params = {"limit": 1000}
        if cursor:
            params["cursor"] = cursor
        payload = get_json(f"{BASE_URL}/markets/trades", params)
        batch = payload.get("trades") or []
        for raw in batch:
            fh.write(json.dumps(raw) + "\n")
        fh.flush()
        n += len(batch)
        blocks += sum(1 for r in batch if r.get("is_block_trade"))
        cursor = payload.get("cursor")
        oldest = batch[-1]["created_time"] if batch else "-"
        print(f"page {page+1}: {len(batch)} trades, cum {n}, blocks {blocks}, oldest {oldest}", flush=True)
        if not cursor or not batch or cursor in seen:
            break
        seen.add(cursor)
print(f"DONE total={n} blocks={blocks} rate={blocks/n if n else 0:.6f}")
