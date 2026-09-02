"""Early-close anchor exposure for this theory's own cells.

**Why this exists.** `tickets/study/answer/2026-08-29-early-close-exposure-existing-backtests`
established that a market whose *stated deadline* sits well after its
*close_time* carries a contaminated time anchor, and it named this theory
explicitly: "no_side_premium deserves a specific look for that reason: its
cell B (non-mention YES favorites 0.80-0.90, claimed -3.89 net) is drawn
from exactly this population." It then *reasoned* -- and said so -- that
both cells are safe, and stopped.
`tickets/study/answer/2026-09-01-early-close-exposure-in-the-bettable-slice` measured the
same thing on `insider_judgment` and found the bias real on **both** sides
of the book, with the YES-side distortion several times larger than the
NO-side one. Cell B is a YES-side claim, so it sits on the side where the
measured distortion is biggest.

**Capture is separate from classification, and only capture is perishable.**
Kalshi ages settled markets out of its public API ~60 days after close. The
parent study measured 9.7% of its population already unreachable on
2026-09-01 against 2.9% three days earlier, so every day of delay converts
rows from classifiable to UNKNOWN permanently. `collect` therefore writes
the **complete raw payload** for every ticker this theory has ever recorded
-- settled or not -- one JSON object per line, flushed per ticker, skipping
whatever is already on disk. An interrupted run resumes; a 404 is recorded
as an answer rather than retried.

`classify` and the arms are inherited from the parent study unchanged
(`_strike_date` first, then `deadline_drift.collect_settled.parse_deadline`
over title/rules/subtitle, EXPOSED at > 3 days early), which is deliberate:
a drop-in classifier makes this theory's numbers comparable to
`insider_judgment`'s rather than merely available.

Usage:
    python -m theories.no_side_premium.exposure collect
    python -m theories.no_side_premium.exposure measure
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tools import db
from tools.http import HttpError, get_json
from tools.kalshi.markets import BASE_URL

HERE = Path(__file__).parent
DATA = HERE / "data"
RAW = DATA / "raw_markets.jsonl"

THEORY = "no_side_premium"


def tickers(conn) -> list[str]:
    """Every distinct ticker this theory has recorded, settled or not.

    Unsettled rows are captured too: they cost nothing today and they are
    the ones whose payload will be gone by the time they matter.
    """
    rows = conn.execute(
        "SELECT DISTINCT kalshi_ticker FROM opportunities "
        "WHERE theory_id = ? ORDER BY kalshi_ticker",
        (THEORY,),
    ).fetchall()
    return [r[0] for r in rows]


def done() -> set[str]:
    """Tickers already on disk, from a previous (possibly killed) run."""
    if not RAW.exists():
        return set()
    seen = set()
    for line in RAW.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            seen.add(json.loads(line)["ticker"])
        except (json.JSONDecodeError, KeyError):
            continue        # a torn final line just gets re-fetched
    return seen


def collect() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = db.connect()
    want = tickers(conn)
    have = done()
    todo = [t for t in want if t not in have]
    print(f"{len(want)} tickers recorded by {THEORY}; {len(have)} already "
          f"captured; {len(todo)} to fetch", flush=True)

    gone = 0
    with RAW.open("a", encoding="utf-8") as fh:
        for i, ticker in enumerate(todo, 1):
            try:
                payload = get_json(f"{BASE_URL}/markets/{ticker}")
                rec = {"ticker": ticker, "ok": True,
                       "market": payload.get("market")}
            except HttpError as exc:
                gone += 1
                rec = {"ticker": ticker, "ok": False, "error": str(exc)[:200]}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()          # per ticker: a kill loses at most one row
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}  unreachable so far: {gone}",
                      flush=True)

    print(f"done. {len(todo)} fetched, {gone} unreachable -> {RAW}",
          flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "collect"
    if cmd == "collect":
        collect()
    else:
        from theories.no_side_premium import exposure_measure
        exposure_measure.main()
