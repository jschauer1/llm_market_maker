"""Mine this theory's settled rows for structure the headline hides.

CLAUDE.md: "A dead headline number is not a dead dataset -- mine it before
moving on." Cell B is 150 rows over 116 event clusters and 6 settlement
days at +0.46 net (t = +0.15); the aggregate says nothing, which is the
condition under which slicing is the job rather than a fishing trip.

**Everything here is exploratory and is labelled as such.** Nothing this
script prints is an edge. A partition that survives is a hypothesis to
register as a slice (`cli slices register`), which starts its
out-of-sample clock; a partition that fails on 150 rows is unconfirmed,
not disproven. The cut count is printed at the end so the reader can price
the multiple comparisons rather than being invited to forget them.

Usage:  python -m theories.no_side_premium.mine_cells
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from tools import db, score

THEORY = "no_side_premium"
VERSION = 1
HERE = Path(__file__).parent
RAW = HERE / "data" / "raw_markets.jsonl"

#: Families grouped by what the market actually is, not by ticker prefix.
#: Assigned from the series prefix, which is published and needs no
#: judgment -- the division-of-labour rule's top rung.
FAMILY_RULES = (
    ("crypto-ladder", ("KXBTCD", "KXETHD", "KXSOLD", "KXBTC", "KXETH",
                       "KXXRPD", "KXDOGED")),
    ("commodity-ladder", ("KXWTI", "KXBRENT", "KXGOLD", "KXSILVER",
                          "KXCOPPER", "KXNGAS", "KXDIESEL", "KXURANIUM")),
    ("retail-price", ("KXAAAGAS", "KXBKNUGGETS", "KXDDCOLDBREW",
                      "KXCHIPBURRITO", "KXTBCRUNCHWRAP", "KXEGGS",
                      "KXMILK")),
    ("index-rate", ("KXRT", "KXNASDAQ", "KXSPX", "KXDJIA", "KXVIX",
                    "KXFED", "KXCPI", "KXPAYROLLS", "KXADP", "KXGDP")),
    ("sport", ("KXWNBA", "KXFIBA", "KXHNL", "KXNBA", "KXNFL", "KXMLB",
               "KXEPL", "KXUFC", "KXTENNIS", "KXCAN", "KXNHL", "KXSOCCER")),
    ("entertainment", ("KXALBUM", "KXTOPSONG", "KXBILLBOARD", "KXPOKEMON",
                       "KXROTTEN", "KXBOX", "KXAGT", "KXEMMY", "KXOSCAR")),
    ("weather", ("KXRAIN", "KXHIGH", "KXLOW", "KXTEMP", "KXSNOW",
                 "KXHURRICANE", "KXEARTHQUAKE")),
    ("politics-policy", ("KXTRUMP", "KXGOVT", "KXSEC", "KXPRESS",
                         "KXACTBLUE", "KXSENATE", "KXHOUSE")),
    ("tech-compute", ("KXH100", "KXB200", "KXTOKENUSE", "KXAALCC",
                      "KXOPENAI", "KXGEMINI")),
)


def family(ticker: str) -> str:
    head = ticker.split("-")[0]
    for name, prefixes in FAMILY_RULES:
        for p in prefixes:
            if head.startswith(p):
                return name
    return "other"


def load_titles() -> dict:
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
        m = rec.get("market")
        if m:
            out[rec["ticker"]] = m
    return out


def agg(rows):
    if not rows:
        return None
    return score.aggregate(rows)


def day_clustered(rows):
    """Mean and SE of the per-settlement-day edge -- THEORY.md's statistic.

    The 2026-08-27 amendment established that rows are not independent
    draws here: the day-level favorite edge swung +4.26 / -7.29 / +5.40
    across three consecutive close days on this very screen. So the
    day-level mean, not the row-level one, is what a claim about this
    theory gets read on.
    """
    by_day = defaultdict(list)
    for r in rows:
        by_day[r.get("resolved_day")].append(r)
    means = []
    for day, rs in sorted(by_day.items()):
        a = score.aggregate(rs)
        if a and a.get("calibration_edge_net") is not None:
            means.append((day, a["calibration_edge_net"], a["n"]))
    if not means:
        return None
    vals = [m[1] for m in means]
    mean = statistics.fmean(vals)
    se = (statistics.stdev(vals) / math.sqrt(len(vals))
          if len(vals) > 1 else None)
    return {"days": means, "mean": mean, "se": se, "n_days": len(vals),
            "pos": sum(1 for v in vals if v > 0)}


def show(label, rows, cuts):
    a = agg(rows)
    if not a:
        print("  {:<26} (empty)".format(label))
        return
    cuts[0] += 1
    e, se = a["calibration_edge_net"], a["clustered_se"]
    t = (e / se) if se else None
    dc = day_clustered(rows)
    dstr = ""
    if dc:
        dstr = "  | day-mean {:+6.2f} over {} days ({}+)".format(
            dc["mean"], dc["n_days"], dc["pos"])
    print("  {:<26} n {:>4}  cl {:>3}  net {:+7.2f}  se {:>6}  t {:>6}{}"
          .format(label, a["n"], a["n_clusters"], e,
                  ("%.2f" % se) if se else "n/a",
                  ("%+.2f" % t) if t is not None else "n/a", dstr))


def main() -> None:
    conn = db.connect()
    markets = load_titles()
    rows = score.observations(conn, THEORY, VERSION, "live", "all")

    cellA = [r for r in rows
             if str(r.get("outcome")).lower() == "no"
             and (r.get("entry_price") or 0) >= 0.85]
    cellB = [r for r in rows
             if str(r.get("outcome")).lower() == "yes"
             and 0.80 <= (r.get("entry_price") or 0) <= 0.90]

    cuts = [0]
    print("=" * 78)
    print("CELL B  (outcome=yes, ask 0.80-0.90) -- the avoid claim, -3.9 net")
    print("=" * 78)
    show("HEADLINE", cellB, cuts)
    cuts[0] -= 1                      # the headline is not a cut

    dc = day_clustered(cellB)
    print("\n  per settlement day:")
    for day, e, n in dc["days"]:
        print("    {}  n {:>3}  net {:+7.2f}".format(day, n, e))
    print("    day-mean {:+.2f}  SE {:.2f}  ({}/{} positive)".format(
        dc["mean"], dc["se"], dc["pos"], dc["n_days"]))

    print("\n  by family (published series prefix, no judgment):")
    fams = defaultdict(list)
    for r in cellB:
        fams[family(r["kalshi_ticker"])].append(r)
    for name, rs in sorted(fams.items(), key=lambda kv: -len(kv[1])):
        show(name, rs, cuts)

    print("\n  by entry-price band inside 0.80-0.90:")
    bands = (("0.800-0.833", 0.800, 0.8334), ("0.833-0.867", 0.8334, 0.8667),
             ("0.867-0.900", 0.8667, 0.9001))
    for name, lo, hi in bands:
        show(name, [r for r in cellB
                    if lo <= (r.get("entry_price") or 0) < hi], cuts)

    print("\n  ladder vs discrete (a ladder leg is one strike of many on a")
    print("  continuous quantity; a discrete market is not):")
    ladderish = {"crypto-ladder", "commodity-ladder", "retail-price",
                 "index-rate", "weather"}
    show("ladder-leg families", [r for r in cellB
                                 if family(r["kalshi_ticker"]) in ladderish],
         cuts)
    show("discrete families", [r for r in cellB
                               if family(r["kalshi_ticker"])
                               not in ladderish], cuts)

    print("\n  by volume at call (median split):")
    vols = [r for r in cellB if r.get("extra", {}).get("volume") is not None]
    if not vols:
        vol_of = {}
        for r in cellB:
            m = markets.get(r["kalshi_ticker"]) or {}
            v = m.get("volume_fp")
            if v is not None:
                vol_of[r["kalshi_ticker"]] = float(v)
        if vol_of:
            med = statistics.median(vol_of.values())
            show("volume <= median", [r for r in cellB
                                      if vol_of.get(r["kalshi_ticker"], 0)
                                      <= med], cuts)
            show("volume >  median", [r for r in cellB
                                      if vol_of.get(r["kalshi_ticker"], 0)
                                      > med], cuts)
            print("    (median lifetime volume {:.0f})".format(med))

    print("\n" + "=" * 78)
    print("CELL A  (outcome=no, ask >= 0.85) -- the live claim, +2.0 net")
    print("=" * 78)
    show("HEADLINE", cellA, cuts)
    cuts[0] -= 1
    print("  series:", dict(Counter(r["kalshi_ticker"].split("-")[0]
                                    for r in cellA)))
    print("  event clusters: {} -- below every gate; NOT sliced, because a "
          "2-cluster\n  sample cannot support a partition."
          .format(score.aggregate(cellA)["n_clusters"]))

    print("\n" + "=" * 78)
    print("{} exploratory cuts taken on cell B. Nothing above is an edge; a"
          .format(cuts[0]))
    print("survivor is a hypothesis to register as a slice, and a failure on")
    print("150 rows is unconfirmed rather than disproven.")
    print("=" * 78)


if __name__ == "__main__":
    main()
