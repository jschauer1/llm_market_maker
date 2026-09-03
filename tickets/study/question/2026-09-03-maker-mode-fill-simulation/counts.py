"""Population census for the maker-mode study — and the one pass over the corpus.

This script **cannot read a settlement outcome**: every corpus row goes
through `sim.market_view()`, which drops `result` before returning. That
is the pre-registration's claim about what was looked at, enforced in
code rather than promised in prose. It is also why the study is tier A
without an argument: settlement is never read, here or in `run.py` — the
primary statistic is a cost comparison between two arms that end holding
the same contract, so the outcome cancels algebraically and is never
needed.

It streams `settled_trades.jsonl` once, applies the pre-registered
inclusion rules, writes one structural record per surviving market to
`data/markets.jsonl`, and prints the census plus the spread and staleness
distributions. `run.py` computes the contrast from the intermediate.

Writes incrementally (repo data convention): an interrupted run resumes
from the tickers already in the intermediate rather than restarting.

    python tickets/study/question/2026-09-03-maker-mode-fill-simulation/counts.py
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mm_sim", _HERE / "sim.py")
sim = importlib.util.module_from_spec(_spec)
sys.modules["mm_sim"] = sim
_spec.loader.exec_module(sim)

REPO = _HERE.parents[3]
CORPUS = REPO / "theories" / "taker_flow" / "backtests" / "settled_trades.jsonl"
OUT_DIR = _HERE / "data"
OUT = OUT_DIR / "markets.jsonl"

# Pre-registered constants. Changing one of these is a different study.
DECISION_H = 48.0      # T = resolved_at - 48h
HORIZON_H = 24.0       # order rests until T + 24h
MAX_AGE_H = 72.0       # a book side staler than this is not observable
MIN_SPREAD = 0.02      # below this, "bid + 1c" IS the ask
PRICE_LO, PRICE_HI = 0.02, 0.98
IMPROVEMENT = 0.01


def _load_done() -> set[str]:
    if not OUT.exists():
        return set()
    done = set()
    with OUT.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    done.add(json.loads(line)["ticker"])
                except (ValueError, KeyError):
                    continue
    return done


def main() -> int:
    if not CORPUS.exists():
        print(f"corpus missing: {CORPUS}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = _load_done()
    if done:
        print(f"resuming: {len(done)} markets already in {OUT.name}")

    drops = Counter()
    kept = 0
    seen = 0
    spreads: list[float] = []
    ages: list[float] = []
    asks: list[float] = []

    with CORPUS.open(encoding="utf-8") as fh, OUT.open("a", encoding="utf-8") as out:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            seen += 1
            if seen % 500 == 0:
                print(f"  ...{seen} rows, {kept} kept", flush=True)
            try:
                row = json.loads(line)
            except ValueError:
                drops["unparseable row"] += 1
                continue
            if row.get("ticker") in done:
                continue

            # RULE 1 is applied by run.py's caller only in the sense that a
            # row with no settled result is not in this corpus at all; the
            # field is dropped here before it can be read either way.
            if not row.get("resolved_at"):
                drops["no resolved_at"] += 1
                continue
            view = sim.market_view(row)
            prints = view["prints"]
            if not prints:
                drops["no trades"] += 1
                continue

            resolved = sim.parse_ts(view["resolved_at"])
            t = resolved - _dt.timedelta(hours=DECISION_H)
            end = t + _dt.timedelta(hours=HORIZON_H)

            # RULE 2: both sides observable and fresh at T.
            q_t = sim.quote_at(prints, t, max_age_h=MAX_AGE_H)
            if q_t is None:
                drops["book not observable at T"] += 1
                continue
            # Rule 2 applied at T+H as well: the fallback arm PAYS that ask,
            # so it must be executable by the same standard. Data
            # availability only -- no outcome is consulted.
            q_end = sim.quote_at(prints, end, max_age_h=MAX_AGE_H)
            if q_end is None:
                drops["fallback ask not observable at T+H"] += 1
                continue
            # RULE 3: coherent book.
            if not (q_t.bid < q_t.ask):
                drops["crossed reconstruction"] += 1
                continue
            # RULE 4: something to capture.
            if q_t.spread < MIN_SPREAD - 1e-9:
                drops["spread under 2c"] += 1
                continue
            # RULE 5: price range.
            if not (PRICE_LO <= q_t.ask <= PRICE_HI):
                drops["ask outside [0.02, 0.98]"] += 1
                continue

            limit = round(q_t.bid + IMPROVEMENT, 4)
            hit = sim.fills(prints, limit=limit, start=t, end=end)
            # Pre-declared secondary 3, the BUY-NO mirror: posting a YES
            # ask one cent inside the existing one.
            limit_no = round(q_t.ask - IMPROVEMENT, 4)
            hit_no = sim.fills_ask(prints, limit=limit_no, start=t, end=end)

            rec = {
                "ticker": view["ticker"],
                "resolved_at": view["resolved_at"],
                "day": view["resolved_at"][:10],
                "series": view["ticker"].split("-")[0],
                "event": "-".join(view["ticker"].split("-")[:2]),
                "bid_t": q_t.bid,
                "ask_t": q_t.ask,
                "spread_t": round(q_t.spread, 4),
                "bid_age_h": round(q_t.bid_age_h, 3),
                "ask_age_h": round(q_t.ask_age_h, 3),
                "bid_end": q_end.bid,
                "ask_end": q_end.ask,
                "limit": limit,
                "filled": hit is not None,
                "fill_price": hit.price if hit else None,
                "limit_no": limit_no,
                "filled_no": hit_no is not None,
                "n_prints": len(prints),
            }
            out.write(json.dumps(rec) + "\n")
            out.flush()
            kept += 1
            spreads.append(q_t.spread)
            ages.append(max(q_t.bid_age_h, q_t.ask_age_h))
            asks.append(q_t.ask)

    def pct(vals, q):
        if not vals:
            return float("nan")
        s = sorted(vals)
        return s[min(len(s) - 1, int(q * len(s)))]

    print()
    print("=" * 62)
    print("POPULATION CENSUS -- structural only, no outcome read")
    print("=" * 62)
    print(f"corpus rows scanned          : {seen}")
    print(f"markets KEPT                 : {kept}")
    print()
    print("dropped, by pre-registered rule:")
    for reason, n in drops.most_common():
        print(f"  {reason:<38} {n:>6}")
    print()
    if kept:
        print("reconstructed spread at T (cents):")
        for q in (0.10, 0.25, 0.50, 0.75, 0.90):
            print(f"  p{int(q*100):<3}                                {pct(spreads, q)*100:>6.1f}")
        print(f"  mean                                 {sum(spreads)/len(spreads)*100:>6.1f}")
        print()
        print("worst-side quote staleness at T (hours):")
        for q in (0.25, 0.50, 0.75, 0.90):
            print(f"  p{int(q*100):<3}                                {pct(ages, q):>6.2f}")
        print()
        print("ask at T, by pre-declared band:")
        bands = [(0.02, 0.20), (0.20, 0.50), (0.50, 0.80), (0.80, 0.98)]
        for lo, hi in bands:
            n = sum(1 for a in asks if lo <= a < hi or (hi == 0.98 and a == 0.98))
            print(f"  [{lo:.2f}, {hi:.2f})                          {n:>6}")
        print()
        days = {r for r in (x[:10] for x in [])} or None
    print(f"intermediate written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
