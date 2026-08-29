"""deadline-drift audit round 3.

Round 2 (fresh disjoint sample of 50) still missed 10 (20%), in three
families the round-2 patterns did not cover:

  count thresholds phrased as prose -- "the number of X ... is at least 5",
    "if above 1 federal judges are confirmed", "... is exactly 1"
  role-succession "which person" markets -- "is the FIRST PERSON confirmed
    as Commissioner", "is the first such subject to do so", "becomes Prime
    Minister ... following the next election". Same multi-destination
    objection as "next team is Y": hazard times a conditional multinomial.
  scheduled competition outcomes -- "wins a tennis major before Dec 31":
    the tournaments happen on schedule, so the question is the outcome,
    not the occurrence.

Round 3 extends the patterns and re-audits on a third disjoint sample.
"""
import re
import sys
from collections import Counter

sys.path.insert(0, r"c:\Users\jbs00\OneDrive\Documents\Current_Work\LLM_market_identifier")

from tools import board as board_tool, db   # noqa: E402

BY_DEADLINE = re.compile(
    r"\b(?:before|by|on or before|no later than)\s+"
    r"(?:\w+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2})",
    re.IGNORECASE)

THRESHOLD = re.compile(
    r"\bis (?:above|below|at or above|at or below|between)\b"
    r"|\bcloses? (?:above|below)\b|\bhigher than\b|\blower than\b"
    r"|\brise[s]? (?:more|less) than\b|\bprice .{0,40}\b(?:above|below)\b"
    # count thresholds, prose forms
    r"|\bthe number of\b"
    r"|\b(?:has|have|is|are)\s+(?:above|below|at least|at most|exactly)\s+\d"
    r"|\bif above \d"
    r"|\bachieves? an? (?:accuracy|score)\b"
    r"|\bscores? at least\b",
    re.IGNORECASE)

SCHEDULED = re.compile(
    r"originally scheduled for"
    r"|\bprofessional .{0,60}(?:soccer|basketball|football|cricket|hockey"
    r"|tennis|baseball) (?:game|match)\b|\bearnings call\b"
    r"|Consumer Price Index|Producer Price Index"
    r"|Carbon Arc|OpenRouter|\bMetascore\b"
    # scheduled competition outcomes: the event happens on the calendar,
    # the market is about who wins it
    r"|\bwins? (?:a|the) (?:tennis major|major|grand slam|championship"
    r"|tournament)\b"
    r"|\bwins? the .{0,40}(?:Open|Championship|Cup|Series)\b",
    re.IGNORECASE)

MULTI_DESTINATION = re.compile(
    r"\bnext (?:team|club|franchise) is\b"
    r"|\bnext (?:team|club) is the\b"
    r"|\bis the first\b.{0,80}\bto (?:announce|sell|declare|reach|leave|do so)\b"
    r"|\bis the first (?:person|such subject)\b"
    r"|\bis appointed, elected, named, designated\b"
    r"|\bis,? or is announced to be in the future,? the first\b"
    r"|\band is the first such subject\b"
    r"|\bbecomes .{0,50}\bas a result of government formation\b"
    r"|\bthe 51st state is\b"
    r"|\bbacks a challenger to\b",
    re.IGNORECASE)

conn = db.connect()
board = board_tool.get_board(conn)

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
        excl["multi-destination branch"] += 1
    else:
        kept.append(m)

total = len(kept) + sum(excl.values())
print(f"by-deadline phrasing : {total:,}")
for k, v in excl.most_common():
    print(f"  excluded {v:6,}  {k}")
print(f"candidate population : {len(kept):,} markets in "
      f"{len({m.series_ticker for m in kept}):,} series")
band = [m for m in kept
        if m.yes_ask is not None and 0.05 <= m.yes_ask <= 0.60]
print(f"in the 0.05-0.60 band: {len(band):,}")

kept.sort(key=lambda m: m.ticker)
k = len(kept) / 50.0
sample = [kept[min(len(kept) - 1, int((i + 0.25) * k))] for i in range(50)]
print(f"\nround-3 sample: {len(sample)} markets, "
      f"{len({m.series_ticker for m in sample})} distinct series\n")
for i, m in enumerate(sample, 1):
    t = (m.title or "").encode("ascii", "replace").decode()
    r = (m.rules_primary or "").encode("ascii", "replace").decode()
    print(f"[{i}] {m.ticker}  yes_ask={m.yes_ask}")
    print(f"    R: {r[:230]}")
