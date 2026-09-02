"""DD-3 — replay the pre-registered cell on data the population choice never saw.

Pre-registration: `THEORY.md`, "DD-3, a replication on contemporaneous data
the population choice never saw", committed at af0e569 *before* the capture
that produces this data had finished. Read it before reading any number
printed here.

**What makes this out-of-sample.** `collect_settled`'s walk took its series
list from the live board, so it reached a series only while that series
still had something trading. The 2026-09-01 population choice was made on
exactly the 1,908 markets that walk had found. `data/preplatform_seen.json`
freezes that ticker set; anything absent from it comes from a series the
choice never saw, and is therefore a genuine test set — contemporaneous
rather than forward, so it controls for **selection** and for nothing about
**regime**.

**Not a reimplementation.** Every number here comes from `hazard.estimate`
with `side="bid", entry="first"`, the same call `hazard.main` labels "THE
PRE-REGISTERED CELL". This module only chooses which tickers go in.

**One pre-specified choice, fixed before any output was seen** (and
committed with the file, so the ordering is checkable): `partition_families`
is derived from **seen data only**. It is a function of settled *outcomes*,
so recomputing it over the test set would let test outcomes define the test
population — mild leakage, but leakage. The full-store variant is printed
underneath as a sensitivity, never as the headline.

Run: python -m theories.deadline_drift.backtest
"""
from __future__ import annotations

import json
from pathlib import Path

from theories.deadline_drift import hazard

DATA = Path(__file__).resolve().parent / "data"

#: DD-3's bar, from THEORY.md. Confirmation needs BOTH; below the cluster
#: floor the run settles nothing in either direction.
NET_BAR = 2.0
CLUSTER_FLOOR = 80


def seen_tickers() -> set[str]:
    d = json.loads((DATA / "preplatform_seen.json").read_text())
    return set(d["tickers"])


def arms(anchors, candles, rules, events):
    """(seen, unseen, part) for the pre-registered population.

    The stratum is built exactly as `hazard.main` builds it: over `candles`
    keys, classifying `rules[ticker]`. Iterating `anchors` instead would
    silently admit markets with no candle series, which `estimate` then
    drops -- same answer, but the printed population size would be a
    number this theory never screens on.
    """
    seen = seen_tickers()
    vol = hazard.market_volume()
    liquid_haz = [tk for tk in candles
                  if hazard.stratum(rules.get(tk, "")) == "hazard"
                  and vol.get(tk, 0.0) >= 100.0]
    # Pre-specified: exclusions derived from SEEN data only.
    seen_anchors = {tk: a for tk, a in anchors.items() if tk in seen}
    part = hazard.partition_families(seen_anchors, events)
    clean = [tk for tk in liquid_haz
             if (anchors.get(tk) or {}).get("series") not in part]
    return ([tk for tk in clean if tk in seen],
            [tk for tk in clean if tk not in seen], part)


def main() -> None:
    anchors, candles, rules = hazard.load()
    events = hazard.event_map()
    seen = seen_tickers()
    print(f"store: {len(anchors)} markets;  frozen seen set: {len(seen)};  "
          f"new since freeze: {len(set(anchors) - seen)}")

    seen_arm, unseen_arm, part = arms(anchors, candles, rules, events)
    print(f"pre-registered population -> seen {len(seen_arm)}, "
          f"unseen {len(unseen_arm)}  (partition families from seen: {len(part)})")

    print("\n" + hazard.HDR)
    print("-" * len(hazard.HDR))
    kw = dict(events=events, side="bid", entry="first", weight="event")
    r_unseen = hazard.estimate(anchors, candles, tickers=unseen_arm, **kw)
    r_seen = hazard.estimate(anchors, candles, tickers=seen_arm, **kw)
    hazard._row("DD-3 UNSEEN (the test)", r_unseen)
    hazard._row("seen (control, descriptive)", r_seen)

    print("\n=== DD-3 VERDICT (bar fixed in THEORY.md before any of this ran) ===")
    if not r_unseen or r_unseen.get("markets", 0) == 0:
        print("NO DATA — the unseen arm is empty.")
        return
    net = r_unseen["net_pts"]
    ncl = r_unseen["n_clusters"]
    lo = net - 1.96 * r_unseen["se_cl_pts"]
    hi = net + 1.96 * r_unseen["se_cl_pts"]
    print(f"net {net:+.2f} pts, 95% CI [{lo:+.2f}, {hi:+.2f}], "
          f"{ncl} event clusters")
    if ncl < CLUSTER_FLOOR:
        print(f"UNDERPOWERED — {ncl} clusters is below the pre-registered "
              f"floor of {CLUSTER_FLOOR}. Settles nothing in either direction.")
    elif net >= NET_BAR and lo > 0:
        print(f"CONFIRMED — net >= +{NET_BAR} and the 95% CI excludes zero.")
    else:
        print(f"FAILED — needs net >= +{NET_BAR} with a CI excluding zero.")


if __name__ == "__main__":
    main()
