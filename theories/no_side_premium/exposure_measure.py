"""The exposure measurement, exactly as NOTES.md 2026-09-01 pre-registered it.

Nothing here chooses a threshold, an arm or a population: all three are
fixed in the notebook entry written before this file computed anything.
The classifier is inherited from
`tickets/study/answer/2026-09-01-early-close-exposure-in-the-bettable-slice/measure.py`
without modification -- deliberately, so this theory's arms are comparable
to `insider_judgment`'s rather than merely available.

Scoring goes through `tools.score.observations` + `aggregate`, never
re-implemented arithmetic: partitioning that list and calling `aggregate`
on a part is exactly `compute_score` on that part, same identity, decision
and cluster semantics, because it is the same rows.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from tools import db, score
from tools.timeutil import parse_deadline

HERE = Path(__file__).parent
RAW = HERE / "data" / "raw_markets.jsonl"

THEORY = "no_side_premium"
VERSION = 1

#: Inherited unchanged: a median 3h early is settlement mechanics, a 3+ day
#: gap is a contaminated anchor.
EARLY_DAYS = 3.0

#: Pre-committed floor. Below this in either arm the contrast is reported
#: NOT MEASURED rather than reinterpreted.
MIN_CLUSTERS = 10

#: The parent study's measured EXPOSED - CLEAN gaps, out of sample. Used
#: ONLY as a stated assumption for the contamination bound when this
#: theory's own gap is under-powered. Never as this theory's measurement.
PARENT_D_NO = -4.51
PARENT_D_YES = +4.98

_MONI = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _iso(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _strike_date(custom_strike) -> dt.datetime | None:
    if not isinstance(custom_strike, dict):
        return None
    raw = custom_strike.get("Date")
    if not raw:
        return None
    text = str(raw).strip()
    before = text.lower().startswith("before")
    body = text[6:].strip() if before else text
    parts = body.replace(",", " ").split()
    if len(parts) < 3:
        return None
    mon = _MONI.get(parts[0][:3].title())
    if not mon:
        return None
    try:
        return dt.datetime(int(parts[2]), mon, int(parts[1]),
                           tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def load_markets() -> dict:
    out = {}
    if not RAW.exists():
        return out
    for line in RAW.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("ok") and rec.get("market"):
            out[rec["ticker"]] = rec["market"]
        else:
            out.setdefault(rec["ticker"], None)
    return out


def classify(market: dict | None) -> dict:
    """EXPOSED / UNEXPOSED / UNKNOWN / GONE, with the source that decided."""
    if market is None:
        return {"state": "GONE", "source": None, "days_early": None}
    close = _iso(market.get("close_time"))
    if close is None:
        return {"state": "UNKNOWN", "source": "no-close-time",
                "days_early": None}
    deadline, source = _strike_date(market.get("custom_strike")), "custom_strike"
    if deadline is None:
        for field in ("title", "rules_primary", "subtitle", "yes_sub_title"):
            got = parse_deadline(market.get(field))
            if got:
                deadline, source = _iso(got), "parse:" + field
                break
    if deadline is None:
        return {"state": "UNKNOWN", "source": "no-deadline",
                "days_early": None}
    days_early = (deadline - close).total_seconds() / 86400.0
    return {
        "state": "EXPOSED" if days_early > EARLY_DAYS else "UNEXPOSED",
        "source": source,
        "days_early": days_early,
    }


def welch(a: dict, b: dict) -> tuple[float | None, float | None]:
    ea, eb = a.get("calibration_edge_net"), b.get("calibration_edge_net")
    sa, sb = a.get("clustered_se"), b.get("clustered_se")
    if None in (ea, eb, sa, sb):
        return None, None
    se = math.sqrt(sa ** 2 + sb ** 2)
    if se == 0:
        return None, None
    t = (ea - eb) / se
    return t, math.erfc(abs(t) / math.sqrt(2))


def arm(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "n_clusters": 0, "calibration_edge_net": None,
                "clustered_se": None, "win_rate": None}
    return score.aggregate(rows)


def line(label: str, a: dict) -> str:
    e, se, wr = (a.get("calibration_edge_net"), a.get("clustered_se"),
                 a.get("win_rate"))
    es = ("%+.2f" % e) if e is not None else "n/a"
    ss = ("%.2f" % se) if se is not None else "n/a"
    ws = ("%.3f" % wr) if wr is not None else "n/a"
    return ("  {:<38} n {:>4}  clusters {:>3}  edge_net {:>7}  se {:>6}  "
            "win {}".format(label, a.get("n", 0), a.get("n_clusters", 0),
                            es, ss, ws))


#: The two registered slice predicates, unchanged.
CELLS = (
    ("CELL A  cell-a-no-favorite   (outcome=no,  ask >= 0.85)",
     lambda r: (str(r.get("outcome")).lower() == "no"
                and (r.get("entry_price") or 0) >= 0.85),
     PARENT_D_NO),
    ("CELL B  cell-b-yes-avoid     (outcome=yes, ask 0.80-0.90)",
     lambda r: (str(r.get("outcome")).lower() == "yes"
                and 0.80 <= (r.get("entry_price") or 0) <= 0.90),
     PARENT_D_YES),
)


def main() -> None:
    conn = db.connect()
    markets = load_markets()
    cls = {t: classify(m) for t, m in markets.items()}

    fetched = sum(1 for m in markets.values() if m)
    gone = sum(1 for m in markets.values() if m is None)
    print("CAPTURE: {} tickers on disk, {} fetched, {} aged out of the API "
          "({:.1%})".format(len(markets), fetched, gone,
                            gone / max(len(markets), 1)))

    states = Counter(c["state"] for c in cls.values())
    sources = Counter(c["source"] for c in cls.values()
                      if c["state"] in ("EXPOSED", "UNEXPOSED"))
    print("EXPOSURE over every captured ticker: {}".format(dict(states)))
    print("  deadline source used: {}".format(dict(sources)))
    early = [c["days_early"] for c in cls.values() if c["state"] == "EXPOSED"]
    if early:
        early.sort()
        print("  days early among EXPOSED: median {:.1f}, p90 {:.1f}, "
              "max {:.1f}".format(statistics.median(early),
                                  early[int(0.9 * (len(early) - 1))],
                                  max(early)))

    rows = score.observations(conn, THEORY, VERSION, "live", "all")
    print("\nOBSERVATIONS: {} settled live rows for {} v{}".format(
        len(rows), THEORY, VERSION))

    def split(subset):
        def st(r):
            return cls.get(r.get("kalshi_ticker"), {}).get("state")
        return ([r for r in subset if st(r) == "EXPOSED"],
                [r for r in subset if st(r) == "UNEXPOSED"],
                [r for r in subset if st(r) in (None, "UNKNOWN")],
                [r for r in subset if st(r) == "GONE"])

    for label, pred, parent_d in CELLS:
        subset = [r for r in rows if pred(r)]
        ex, un, unk, gone_r = split(subset)
        clean = un + unk
        a_all, a_ex, a_clean = arm(subset), arm(ex), arm(clean)
        print("\n" + label)
        print(line("whole cell (headline)", a_all))
        print(line("EXPOSED", a_ex))
        print(line("UNEXPOSED (deadline found, on time)", arm(un)))
        print(line("UNKNOWN (no deadline -> not exposed)", arm(unk)))
        print(line("CLEAN = UNEXPOSED + UNKNOWN", a_clean))
        print(line("aged out of the API (unclassifiable)", arm(gone_r)))

        f = a_ex["n"] / max(a_all["n"], 1)
        print("  -> exposed fraction f = {}/{} = {:.1%}".format(
            a_ex["n"], a_all["n"], f))

        if (a_ex["n_clusters"] < MIN_CLUSTERS
                or a_clean["n_clusters"] < MIN_CLUSTERS):
            print("  -> CONTRAST NOT MEASURED: an arm is below the "
                  "pre-committed floor of {} event clusters.".format(
                      MIN_CLUSTERS))
        else:
            t, p = welch(a_ex, a_clean)
            d = a_ex["calibration_edge_net"] - a_clean["calibration_edge_net"]
            tail = ("t {:+.2f}   p {:.4f}".format(t, p) if t is not None
                    else "SE unavailable")
            print("  -> EXPOSED - CLEAN = {:+.2f} pts   {}".format(d, tail))

        own_d = (None if a_ex["calibration_edge_net"] is None
                 or a_clean["calibration_edge_net"] is None
                 else a_ex["calibration_edge_net"]
                 - a_clean["calibration_edge_net"])
        print("  -> CONTAMINATION BOUND  f*d")
        print("       parent study OOS d = {:+.2f}: {:+.3f} pts of the "
              "headline".format(parent_d, f * parent_d))
        if own_d is not None:
            print("       this cell's own (under-powered) d = {:+.2f}: "
                  "{:+.3f} pts".format(own_d, f * own_d))
        if (a_all["calibration_edge_net"] is not None
                and a_clean["calibration_edge_net"] is not None):
            print("       headline {:+.2f} -> clean {:+.2f}".format(
                a_all["calibration_edge_net"],
                a_clean["calibration_edge_net"]))


if __name__ == "__main__":
    main()
