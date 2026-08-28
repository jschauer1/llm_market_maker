"""calendar-arb firing-rate probe over stored board snapshots.

Answers the spec's first deliverable: how often does a hard date-monotonicity
violation exist at executable top-of-book quotes, net of fees?

Grouping is strike-aware. The naive version (subject = title with the
deadline clause removed) collapses KXU3MAX-30-20 ("unemployment reaches 20%
by 2030") with KXU3MAX-27-4.5 ("reaches 4.5% by 2027") into one ladder --
they are NOT nested, both legs can lose, and trading that pair loses money.
So floor_strike/cap_strike/strike_type join the key.
"""
import collections
import json
import re
import sys

from tools import db
from tools.sizing import fee_pts

TEMP = re.compile(
    r"\b(by|before)\s+(the\s+end\s+of\s+)?"
    r"((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{4}"
    r"|end of \w+|\d{4}|Q[1-4]\s*\d{4})",
    re.I,
)
BUFFER = 0.0


def subject_key(raw):
    title = raw.get("title") or ""
    if not TEMP.search(title):
        return None
    subject = TEMP.sub("<D>", title).strip()
    return (
        (raw.get("event_ticker") or "").split("-")[0],
        subject,
        raw.get("floor_strike"),
        raw.get("cap_strike"),
        raw.get("strike_type"),
    )


def price(raw, key):
    """Snapshot payloads carry *_dollars strings, already in [0,1]."""
    v = raw.get(key + "_dollars")
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def scan(rows):
    groups = collections.defaultdict(list)
    for raw in rows:
        if raw.get("status") not in ("active", "open"):
            continue
        k = subject_key(raw)
        if k is None or not k[0]:
            continue
        groups[k].append(raw)

    checked = 0
    findings = []
    for k, ms in groups.items():
        ms = [m for m in ms if m.get("close_time")]
        if len(ms) < 2:
            continue
        ms.sort(key=lambda m: m["close_time"])
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                early, later = ms[i], ms[j]
                if early["close_time"] == later["close_time"]:
                    continue
                y = price(later, "yes_ask")
                n = price(early, "no_ask")
                if y is None or n is None or y <= 0 or n <= 0:
                    continue
                checked += 1
                cost = y + n
                fees = (fee_pts(y) + fee_pts(n)) / 100.0
                if cost + fees + 2 * BUFFER < 1.0:
                    findings.append({
                        "series": k[0],
                        "subject": k[1][:70],
                        "same_event": early.get("event_ticker")
                                      == later.get("event_ticker"),
                        "yes_ticker": later["ticker"], "yes_ask": y,
                        "no_ticker": early["ticker"], "no_ask": n,
                        "profit": round(1.0 - cost - fees, 4),
                        "yes_close": later["close_time"][:10],
                        "no_close": early["close_time"][:10],
                    })
    return checked, findings


def main():
    conn = db.connect()
    caps = [r["captured_at"] for r in conn.execute(
        "SELECT DISTINCT captured_at FROM market_snapshots "
        "WHERE platform='kalshi' ORDER BY captured_at")]
    total = []
    for cap in caps:
        rows = [json.loads(r["raw_json"]) for r in conn.execute(
            "SELECT raw_json FROM market_snapshots "
            "WHERE platform='kalshi' AND captured_at=?", (cap,))]
        checked, findings = scan(rows)
        print(f"{cap}  markets={len(rows):6d}  pairs={checked:5d}  "
              f"violations={len(findings)}")
        for f in findings:
            scope = "same-event" if f["same_event"] else "CROSS-EVENT"
            print(f"    [{scope}] {f['series']:22s} profit={f['profit']:+.4f}"
                  f"  YES {f['yes_ticker']} @{f['yes_ask']:.2f}"
                  f" ({f['yes_close']})  NO {f['no_ticker']}"
                  f" @{f['no_ask']:.2f} ({f['no_close']})")
        total.append((cap, checked, findings))
    print()
    all_f = [f for _, _, fs in total for f in fs]
    print(f"snapshots={len(total)}  total pairs checked="
          f"{sum(c for _, c, _ in total)}  total violations={len(all_f)}")
    if all_f:
        cross = [f for f in all_f if not f["same_event"]]
        print(f"cross-event violations (calendar-arb's own claim): {len(cross)}")
        print(f"median profit/basket: "
              f"{sorted(f['profit'] for f in all_f)[len(all_f)//2]:.4f}")
    json.dump(all_f, open(sys.argv[1], "w"), indent=1)


if __name__ == "__main__":
    main()
