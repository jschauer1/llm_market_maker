"""deadline-drift audit round 5.

Rounds 1-4 refined a pure rules-text regex and plateaued near 15%
misclassification (40 -> 20 -> 12 -> 16), above the spec's 10% kill bar.
The residue was multi-destination "which branch" markets, which are
semantic: "X's next team is Y", "the next club that X joins is Y", "is
the first country to launch", "before any other head coach", "a coalition
that includes SPD". They share a meaning, not a string, so no extension
of the pattern set reaches them.

Round 5 stops reading the wording for that question and reads STRUCTURE
instead, via two signals the regex never had:

1. Kalshi's own event-level ``mutually_exclusive`` flag. This is ground
   truth for "does this condition on which branch?", published by the
   venue rather than inferred from prose. It became available on the
   board in 09a66f7 -- before that, list_open fetched it on every pull
   and discarded it.
2. A price-partition test, for events where the flag is absent or wrong
   (Kalshi calls "Where will Ronaldo go next?" False). >= 3 siblings that
   share ONE deadline and whose prices sum <= 1.05 are pricing a
   partition of one outcome. The shared-deadline condition is load
   bearing: without it the rule kills date ladders (KXALITOOUT-26JUL01 /
   26SEP01 / 27JAN01, the same question at four deadlines, nested rather
   than exclusive), which cost 88 false positives when first measured.

The regex families from round 4 are kept unchanged -- thresholds and
scheduled certainties are genuinely syntactic and the patterns work.

This file is FROZEN before the sample is drawn. The point of round 5 is
an out-of-sample measurement: the two structural rules were designed
against round 4's misses, so re-tuning them against round 5 would
reproduce exactly the in-sample flattery the round is meant to detect.
"""
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"c:\Users\jbs00\OneDrive\Documents\Current_Work\LLM_market_identifier")

from tools import board as board_tool, db   # noqa: E402

# --- round-4 regexes, unchanged -------------------------------------
_r4 = open("studies/2026-08-29-deadline-drift-classifier-audit/classifier.py",
           encoding="utf-8").read()
_ns: dict = {}
exec(_r4.split("conn = db.connect()")[0], _ns)
BY_DEADLINE = _ns["BY_DEADLINE"]
THRESHOLD = _ns["THRESHOLD"]
SCHEDULED = _ns["SCHEDULED"]
MULTI_DESTINATION = _ns["MULTI_DESTINATION"]

PARTITION_SUM_MAX = 1.05
PARTITION_MIN_LEGS = 3


def _price(m):
    for v in (m.mid, m.yes_ask, m.last_price):
        if v is not None:
            return float(v)
    return None


def _deadline(m):
    hit = BY_DEADLINE.search(m.rules_primary or "")
    return hit.group(0).lower() if hit else None


def partition_events(board) -> set[str]:
    """Events pricing a partition of one outcome: >= 3 siblings sharing a
    single deadline whose prices sum to about a dollar. Siblings at
    DIFFERENT deadlines are a date ladder, not a partition, and are
    exempt."""
    by_event = defaultdict(list)
    for m in board:
        by_event[m.event_ticker].append(m)
    out = set()
    for ev, ms in by_event.items():
        if len(ms) < PARTITION_MIN_LEGS:
            continue
        deadlines = {_deadline(m) for m in ms}
        if len(deadlines) != 1 or None in deadlines:
            continue
        prices = [p for p in (_price(m) for m in ms) if p is not None]
        if prices and sum(prices) <= PARTITION_SUM_MAX:
            out.add(ev)
    return out


def classify(board):
    """-> (kept, excluded_counter). `kept` is the candidate population."""
    partitions = partition_events(board)
    kept, excl = [], Counter()
    for m in board:
        rules = m.rules_primary or ""
        if not BY_DEADLINE.search(rules):
            continue
        if THRESHOLD.search(rules):
            excl["continuous or count threshold"] += 1
        elif SCHEDULED.search(rules):
            excl["scheduled certainty"] += 1
        elif MULTI_DESTINATION.search(rules):
            excl["multi-destination (rules text)"] += 1
        elif m.event.get("mutually_exclusive") is True:
            excl["multi-destination (Kalshi flag)"] += 1
        elif m.event_ticker in partitions:
            excl["multi-destination (price partition)"] += 1
        else:
            kept.append(m)
    return kept, excl


if __name__ == "__main__":
    board = board_tool.get_board(db.connect(), max_age_minutes=600)
    kept, excl = classify(board)
    total = len(kept) + sum(excl.values())
    print(f"by-deadline phrasing : {total:,}")
    for k, v in excl.most_common():
        print(f"  excluded {v:6,}  {k}")
    print(f"candidate population : {len(kept):,} markets in "
          f"{len({m.series_ticker for m in kept}):,} series")
    band = [m for m in kept
            if m.yes_ask is not None and 0.05 <= m.yes_ask <= 0.60]
    print(f"in the 0.05-0.60 band: {len(band):,}")
