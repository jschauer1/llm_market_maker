"""The measurement, exactly as STUDY.md pre-registered it.

Nothing here chooses a threshold, a population or a contrast: all three
are fixed in STUDY.md, written before this file computed anything. The
one judgment call this script makes is which deadline source to trust
first, and STUDY.md fixes that order too (published field, then the
parser the study being extended used, then UNKNOWN).

Scoring goes through `tools.score.observations` + `aggregate` rather than
re-implementing the arithmetic. That seam exists for exactly this:
"partitioning this list and calling `aggregate` on a part is exactly
`compute_score` on that part -- same identity, decision, and cluster
semantics, because it is the same rows." A study that recomputed
calibration edge by hand would be measuring its own arithmetic as much as
the theory's.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from pathlib import Path

from tools import db, score
from theories.deadline_drift.collect_settled import parse_deadline

HERE = Path(__file__).parent
RAW = HERE / "raw_markets.jsonl"

THEORY = "insider_judgment"
OOS_RUNS = {"backtest-2026-08-26-insider-judged-s200b",
            "backtest-2026-08-26-insider-judged-s57"}
IS_RUNS = {"backtest-2026-08-26-insider-judged-s200"}

#: Inherited unchanged from the study being extended: a median 3h early is
#: settlement mechanics, a 3+ day gap is a contaminated anchor.
EARLY_DAYS = 3.0

#: STUDY.md's pre-committed floor. Below this in either arm the contrast is
#: reported NOT MEASURED rather than reinterpreted.
MIN_CLUSTERS = 10

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
    """`custom_strike.Date` -- the published deadline field.

    Seen in two shapes: 'Before Jul 1, 2026' (a by-deadline market) and
    'Jul 1, 2026' (a date-certain one). Both parse to the same instant;
    only the first is a deadline the market may close early against, so
    the caller keeps the 'Before' flag.
    """
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
            out.setdefault(rec["ticker"], None)      # aged out of the API
    return out


def classify(market: dict | None) -> dict:
    """EXPOSED / UNEXPOSED / UNKNOWN / GONE, with the source that decided."""
    if market is None:
        return {"state": "GONE", "source": None, "days_early": None}

    close = _iso(market.get("close_time"))
    if close is None:
        return {"state": "UNKNOWN", "source": "no-close-time",
                "days_early": None}

    # 1. the published structured field
    deadline, source = _strike_date(market.get("custom_strike")), "custom_strike"
    # 2. the parser the 2026-08-29 study used, over title then rules
    if deadline is None:
        for field in ("title", "rules_primary", "subtitle",
                      "yes_sub_title"):
            got = parse_deadline(market.get(field))
            if got:
                deadline, source = _iso(got), f"parse:{field}"
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


def sibling_maxclose(markets: dict) -> dict:
    """Parse-free cross-check: the latest close among an event's siblings."""
    by_event: dict[str, list] = {}
    for tick, m in markets.items():
        if not m:
            continue
        ev = m.get("event_ticker") or tick.rsplit("-", 1)[0]
        c = _iso(m.get("close_time"))
        if c:
            by_event.setdefault(ev, []).append(c)
    return {ev: max(v) for ev, v in by_event.items()}


def welch(a: dict, b: dict) -> tuple[float | None, float | None]:
    """t and two-sided p for two independent clustered means."""
    ea, eb = a.get("calibration_edge_net"), b.get("calibration_edge_net")
    sa, sb = a.get("clustered_se"), b.get("clustered_se")
    if None in (ea, eb, sa, sb) or (sa == 0 and sb == 0):
        return None, None
    se = math.sqrt(sa ** 2 + sb ** 2)
    if se == 0:
        return None, None
    t = (ea - eb) / se
    # normal approximation; cluster counts here are small but the report
    # states them beside every number so the reader can discount it.
    p = math.erfc(abs(t) / math.sqrt(2))
    return t, p


def arm(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "n_clusters": 0, "calibration_edge_net": None,
                "clustered_se": None, "win_rate": None}
    return score.aggregate(rows)


def line(label: str, a: dict) -> str:
    e = a.get("calibration_edge_net")
    se = a.get("clustered_se")
    wr = a.get("win_rate")
    return (f"  {label:<34} n {a.get('n', 0):>4}  clusters "
            f"{a.get('n_clusters', 0):>3}  "
            f"edge_net {('%+.2f' % e) if e is not None else '   n/a':>7}  "
            f"se {('%.2f' % se) if se is not None else 'n/a':>6}  "
            f"win {('%.3f' % wr) if wr is not None else 'n/a'}")


def main() -> None:
    conn = db.connect()
    markets = load_markets()
    cls = {t: classify(m) for t, m in markets.items()}

    fetched = sum(1 for m in markets.values() if m)
    gone = sum(1 for m in markets.values() if m is None)
    print(f"CAPTURE: {len(markets)} tickers on disk, {fetched} fetched, "
          f"{gone} aged out of the API ({gone / max(len(markets), 1):.1%})")

    from collections import Counter
    states = Counter(c["state"] for c in cls.values())
    sources = Counter(c["source"] for c in cls.values() if c["state"] in
                      ("EXPOSED", "UNEXPOSED"))
    print(f"EXPOSURE over every captured ticker: {dict(states)}")
    print(f"  deadline source used: {dict(sources)}")
    early = [c["days_early"] for c in cls.values()
             if c["state"] == "EXPOSED"]
    if early:
        early.sort()
        print(f"  days early among EXPOSED: median "
              f"{statistics.median(early):.1f}, p90 "
              f"{early[int(0.9 * (len(early) - 1))]:.1f}, max {max(early):.1f}")

    # --- observations, straight from the scoring seam -------------------
    rows = []
    for v in range(1, 8):
        try:
            rows.extend(score.observations(conn, THEORY, v, "backtest", "all"))
        except Exception:
            pass
    seen, uniq = set(), []
    for r in rows:
        key = (r.get("kalshi_ticker"), r.get("outcome"),
               tuple(sorted(r.get("run_ids") or [r.get("run_id")])))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    rows = uniq
    print(f"\nOBSERVATIONS: {len(rows)} settled backtest rows for {THEORY}")

    def in_runs(r, runs):
        got = set(r.get("run_ids") or [])
        if r.get("run_id"):
            got.add(r["run_id"])
        return bool(got & runs)

    def slice_rows(runs, outcome="no"):
        return [r for r in rows
                if in_runs(r, runs)
                and str(r.get("outcome")).lower() == outcome
                and str(r.get("confidence")) in ("strong", "moderate")]

    def split(subset):
        ex = [r for r in subset
              if cls.get(r.get("kalshi_ticker"), {}).get("state") == "EXPOSED"]
        un = [r for r in subset
              if cls.get(r.get("kalshi_ticker"), {}).get("state") == "UNEXPOSED"]
        unk = [r for r in subset
               if cls.get(r.get("kalshi_ticker"), {}).get("state")
               in (None, "UNKNOWN")]
        gone_rows = [r for r in subset
                     if cls.get(r.get("kalshi_ticker"), {}).get("state")
                     == "GONE"]
        return ex, un, unk, gone_rows

    results = {}
    for label, runs in (("PRIMARY  out-of-sample (s200b + s57)", OOS_RUNS),
                        ("SECONDARY in-sample (s200, mined_from)", IS_RUNS)):
        subset = slice_rows(runs)
        ex, un, unk, gone_r = split(subset)
        # STUDY.md's classifier says UNKNOWN means "no by-deadline deadline
        # could be established, so the market carries no exposure by this
        # mechanism" -- so UNEXPOSED + UNKNOWN is the pre-registered CLEAN
        # arm. Rows whose market has aged out of the API are genuinely
        # unclassifiable and stay out of both arms.
        clean = un + unk
        a_all, a_ex, a_un, a_unk = arm(subset), arm(ex), arm(un), arm(unk)
        a_clean, a_gone = arm(clean), arm(gone_r)
        print(f"\n{label}  --  slice predicate: outcome=no, "
              f"confidence in (strong, moderate)")
        print(line("whole slice arm (headline)", a_all))
        print(line("EXPOSED", a_ex))
        print(line("UNEXPOSED (deadline found, on time)", a_un))
        print(line("UNKNOWN (no deadline -> not exposed)", a_unk))
        print(line("CLEAN = UNEXPOSED + UNKNOWN", a_clean))
        print(line("aged out of the API (unclassifiable)", a_gone))
        kill = (a_clean["calibration_edge_net"] is not None
                and a_clean["calibration_edge_net"] < 2.0
                and a_ex["calibration_edge_net"] is not None
                and a_ex["calibration_edge_net"]
                > a_clean["calibration_edge_net"])
        print(f"  -> pre-registered KILL criterion (clean arm < +2.0 net "
              f"AND exposed above it): "
              f"{'TRIGGERED' if kill else 'NOT triggered'}")
        if (a_ex["n_clusters"] < MIN_CLUSTERS
                or a_clean["n_clusters"] < MIN_CLUSTERS):
            print(f"  -> CONTRAST NOT MEASURED: an arm is below the "
                  f"pre-committed floor of {MIN_CLUSTERS} event clusters.")
            results[label] = ("not_measured", None, None)
        else:
            t, p = welch(a_ex, a_clean)
            diff = (a_ex["calibration_edge_net"]
                    - a_clean["calibration_edge_net"])
            print(f"  -> EXPOSED - CLEAN = {diff:+.2f} pts   "
                  f"t {t:+.2f}   p {p:.4f}"
                  if t is not None else "  -> contrast: SE unavailable")
            results[label] = ("measured", diff, p)

    # --- negative control: the YES side of the same runs ---------------
    print("\nNEGATIVE CONTROL (outside the Holm family): YES side, "
          "same runs, same buckets")
    for label, runs in (("control OOS  yes-side", OOS_RUNS),
                        ("control IS   yes-side", IS_RUNS)):
        subset = slice_rows(runs, outcome="yes")
        ex, un, unk, _g = split(subset)
        print(f"\n{label}")
        print(line("EXPOSED", arm(ex)))
        print(line("CLEAN = UNEXPOSED + UNKNOWN", arm(un + unk)))

    # --- Holm across the two primary contrasts -------------------------
    fam = [(k, v[2]) for k, v in results.items()
           if v[0] == "measured" and v[2] is not None]
    if fam:
        print("\nHOLM across the primary family "
              f"({len(fam)} test(s)):")
        for i, (k, p) in enumerate(sorted(fam, key=lambda x: x[1])):
            adj = p * (len(fam) - i)
            print(f"  {k}: p {p:.4f} -> Holm {min(adj, 1.0):.4f}")
    else:
        print("\nHOLM: no contrast cleared the power floor; nothing to "
              "correct.")

    # --- the parse-free cross-check ------------------------------------
    sib = sibling_maxclose(markets)
    agree = disagree = 0
    for tick, m in markets.items():
        if not m or cls[tick]["state"] not in ("EXPOSED", "UNEXPOSED"):
            continue
        ev = m.get("event_ticker") or tick.rsplit("-", 1)[0]
        c, mx = _iso(m.get("close_time")), sib.get(ev)
        if not c or not mx:
            continue
        sib_says = (mx - c).total_seconds() / 86400.0 > EARLY_DAYS
        if sib_says == (cls[tick]["state"] == "EXPOSED"):
            agree += 1
        else:
            disagree += 1
    tot = agree + disagree
    if tot:
        print(f"\nCROSS-CHECK (reported, not used to classify): the "
              f"sibling-max-close rule agrees with the deadline "
              f"classification on {agree}/{tot} = {agree / tot:.1%}")


if __name__ == "__main__":
    main()
