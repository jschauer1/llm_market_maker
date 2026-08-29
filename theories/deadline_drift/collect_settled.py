"""Persist the settled allowlist history the hazard estimate rests on.

**Why this exists as a script and not as a one-off.** Kalshi archives
settled markets out of its public API roughly 60 days after close. The 112
markets this theory's first estimate used are not a sample -- they are the
entire fetchable history for this population, and it shrinks every day.
Anything not on disk when it is fetched is unrecoverable upstream later.

Writes three things, incrementally and resumably:

  data/settled_raw.json     complete list_settled payloads, untouched
  data/anchors.json         per market: parsed deadline, actual close, the
                            gap between them, result. The gap is the whole
                            correction in a6302a8 -- a NO market closes at
                            its deadline, a YES market closes when the event
                            fires, a median of 210 days earlier.
  data/candles.json         daily candles per market, with days measured
                            from BOTH anchors so the contaminated and
                            corrected views are both reconstructable.

Run: python -m theories.deadline_drift.collect_settled
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

from tools.kalshi import history
from tools.kalshi import markets as km

DATA = Path(__file__).parent / "data"
ARCHIVE_DAYS = 60

_MON = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DEADLINE = re.compile(
    rf"\b(?:before|by|on or before|no later than)\s+"
    rf"({_MON})\w*\s+(\d{{1,2}}),?\s*(\d{{4}})", re.IGNORECASE)
_MONI = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def parse_deadline(rules: str | None) -> str | None:
    """The deadline STATED IN THE RULES -- the only sound time anchor.

    Actual close is a function of the outcome on a 'by D' market, so it can
    never define the decision point: see the 2026-08-29 correction in
    NOTES.md.
    """
    hit = _DEADLINE.search(rules or "")
    if not hit:
        return None
    return dt.datetime(int(hit.group(3)), _MONI[hit.group(1)[:3].title()],
                       int(hit.group(2)), tzinfo=dt.timezone.utc).isoformat()


def _load(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(name: str, obj) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj), encoding="utf-8")


def _ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def collect(series: list[str], *, fetch=None) -> dict:
    """Walk each series, persisting after every one. Resumable by design."""
    raw = _load("settled_raw.json")
    anchors = _load("anchors.json")
    candles = _load("candles.json")
    floor = int(time.time()) - ARCHIVE_DAYS * 24 * 3600

    for s in series:
        if s not in raw:
            try:
                got = km.list_settled(series_ticker=s, min_close_ts=floor,
                                      fetch=fetch)
                raw[s] = [m.raw for m in got if m.result]
            except Exception as exc:
                raw[s] = {"__error__": f"{type(exc).__name__}: {exc}"}
            _save("settled_raw.json", raw)

        rows = raw[s] if isinstance(raw[s], list) else []
        for m in rows:
            tk = m["ticker"]
            if tk not in anchors:
                dl = parse_deadline(m.get("rules_primary"))
                anchors[tk] = {
                    "series": s, "result": m.get("result"),
                    "close_time": m.get("close_time"), "deadline": dl,
                    "closed_early_days": (
                        round((_ts(dl) - _ts(m["close_time"])) / 86400.0, 2)
                        if dl and m.get("close_time") else None),
                }
                _save("anchors.json", anchors)
            if tk in candles or not anchors[tk].get("deadline"):
                continue
            close_ts = _ts(anchors[tk]["close_time"])
            dl_ts = _ts(anchors[tk]["deadline"])
            try:
                cs = history.candlesticks(s, tk, close_ts - 45 * 86400,
                                          close_ts, 1440)
            except Exception as exc:
                candles[tk] = {"__error__": type(exc).__name__}
                _save("candles.json", candles)
                continue
            candles[tk] = [
                {"end_ts": c["end_ts"], "yes_ask": c["yes_ask_close"],
                 "volume": c["volume"],
                 # Both anchors kept, so the contaminated and corrected
                 # views are each reconstructable from disk.
                 "days_to_close": round((close_ts - c["end_ts"]) / 86400.0, 2),
                 "days_to_deadline": round((dl_ts - c["end_ts"]) / 86400.0, 2)}
                for c in cs
                if c.get("yes_ask_close") is not None
            ]
            _save("candles.json", candles)
    return {"series": len(raw), "markets": len(anchors),
            "with_candles": sum(1 for v in candles.values()
                                if isinstance(v, list))}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools import board as bt, db
    from theories.deadline_drift import screen as dd
    conn = db.connect()
    board = bt.get_board(conn)
    series = sorted({m.series_ticker for m in dd.population(board)})
    print(f"walking {len(series)} allowlist series...")
    print(collect(series))
