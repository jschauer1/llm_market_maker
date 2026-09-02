"""Collect daily candles for every settled KXALBUMEQUIV market.

Population, buckets, filters and decision rule are fixed in PREREG.md,
written before any calibration number existed.

Incremental and resumable per CLAUDE.md's collection rule: one JSON line
per market, flushed as it goes, and a re-run skips what is already there.
"""
import json, os, re, sys, datetime as dt
sys.path.insert(0, os.path.abspath("."))
from tools.db import connect
from tools.kalshi.history import candlesticks

SERIES = "KXALBUMEQUIV"
OUT = sys.argv[1]

# Ticker event segment ends in the tracking week's END date, e.g. ANG26SEP24.
# Verified on 33/33 board events against the title text (PREREG.md).
MON = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
EVENT_DATE = re.compile(r"(\d{2})([A-Z]{3})(\d{2})[A-Z]?$")


def window(ticker: str):
    """(W0, W1) UTC datetimes of the tracking week, from the ticker alone."""
    seg = ticker.split("-")[1]
    m = EVENT_DATE.search(seg)
    if not m:
        return None
    yy, mon, dd = m.groups()
    end = dt.datetime(2000 + int(yy), MON[mon], int(dd), tzinfo=dt.timezone.utc)
    w1 = end + dt.timedelta(days=1)      # window covers all of the end day
    w0 = w1 - dt.timedelta(days=7)
    return w0, w1


def main():
    conn = connect()
    rows = list(conn.execute(
        "SELECT kalshi_ticker, resolved_at, result FROM settlements "
        "WHERE kalshi_ticker LIKE ? AND result IN ('yes','no')", (SERIES + "%",)))
    print(f"settled markets: {len(rows)}", flush=True)

    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["ticker"])
            except Exception:
                pass
    print(f"already collected: {len(done)}", flush=True)

    n_ok = n_nocandle = 0
    with open(OUT, "a", encoding="utf-8") as fh:
        for i, (ticker, resolved_at, result) in enumerate(rows):
            if ticker in done:
                continue
            w = window(ticker)
            if w is None:
                print(f"  UNPARSEABLE {ticker}", flush=True)
                continue
            w0, w1 = w
            start = int((w0 - dt.timedelta(days=21)).timestamp())
            end = int(dt.datetime.fromisoformat(
                resolved_at.replace("Z", "+00:00")).timestamp())
            try:
                cs = candlesticks(SERIES, ticker, start, end, 1440)
                err = None
            except Exception as exc:
                cs, err = [], f"{type(exc).__name__}: {exc}"
            fh.write(json.dumps({
                "ticker": ticker, "result": result, "resolved_at": resolved_at,
                "w0": w0.isoformat(), "w1": w1.isoformat(),
                "candles": cs, "error": err,
            }) + "\n")
            fh.flush()
            if cs:
                n_ok += 1
            else:
                n_nocandle += 1
            if (i + 1) % 40 == 0:
                print(f"{i+1}/{len(rows)}  with-candles {n_ok}  empty {n_nocandle}", flush=True)
    print(f"DONE with_candles={n_ok} empty={n_nocandle}")


if __name__ == "__main__":
    main()
