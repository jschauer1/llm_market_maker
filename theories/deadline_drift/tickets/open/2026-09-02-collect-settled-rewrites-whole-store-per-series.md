---
title: collect_settled rewrites the whole store per series, which is quadratic on a platform-wide walk
lane: theory
theory: deadline_drift
created: 2026-09-02
created_by: user-directed-dd3
author_lane: theory
author_context: Hit while running the DD-3 platform-wide capture on 2026-09-02.
status: open
---
WHAT IS SLOW. collect() calls _save('settled_raw.json', raw) after every series and _save('anchors.json', anchors) after every NEW MARKET. Both rewrite the entire file. That was fine for the walk it was designed for -- superset_series returns ~960 board-scoped series -- but the platform walk is 13,733, and settled_raw.json passed 5.2 MB partway through.

MEASURED 2026-09-02, mid-walk: throughput fell from 1.78 to 1.30 series/sec between the 1,200th and 2,300th series, with the store growing from ~4.9 to 5.2 MB. Projected completion moved from ~2h to ~2.5h and is still moving. The cost is O(series x store size), so it degrades exactly as the capture succeeds.

WHY IT WAS NOT FIXED IN FLIGHT. The run holds perishable data -- Kalshi archives settled markets ~60 days after close -- and it is resumable. Changing the write path underneath a live capture risks the data it is capturing, which is the one thing the data convention will not trade for speed.

THE FIX, AND THE CONSTRAINT IT MUST RESPECT. CLAUDE.md requires incremental writes so an interrupted run resumes rather than restarts; it does NOT require a full-store rewrite per unit. Options, cheapest first:

1. Batch the raw save every N series (N=25) and the anchors save per series rather than per market. Resume granularity drops from 1 series to 25 -- seconds of refetch, against hours saved. Smallest diff.
2. Append-only JSONL for settled_raw (one line per series) with a load that folds it. Resume stays exact, writes become O(1) in store size. This is the shape tools/README.md's convention actually describes.
3. Move the store to SQLite, which is where structured facts are supposed to live anyway.

Prefer 2 if anyone is touching this properly; 1 is the stopgap that needs no migration of the existing JSON.

DO NOT start this while a capture is running.
