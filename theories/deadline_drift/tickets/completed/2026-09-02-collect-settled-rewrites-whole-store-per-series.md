---
title: collect_settled rewrites the whole store per series, which is quadratic on a platform-wide walk
lane: theory
theory: deadline_drift
created: 2026-09-02
created_by: user-directed-dd3
author_lane: theory
author_context: Hit while running the DD-3 platform-wide capture on 2026-09-02.
status: done
closed: 2026-09-03
resolution: FIXED with option 1 (the stopgap), and the fix is now MEASURED rather than assumed. FLUSH_EVERY=25 was already in the file; the 2026-09-03 platform sweep is the first run to complete under it and it held: 13,772 series walked in 1,933s with the store at 8.3MB (settled_raw) + 7.9MB (candles), and throughput did NOT degrade as the store grew -- windowed rate ran 1.9/s early (heavy candle fetching) and 3.5/s late, i.e. dominated by network, not by write volume. The quadratic term the ticket measured (1.78 -> 1.30 -> 0.84 series/sec) is gone. The resume also re-walked 7,100 already-done positions in 11 seconds, which is the 25-series granularity costing nothing in practice.

Options 2 (append-only JSONL) and 3 (SQLite) are NOT done and are no longer urgent for speed. They remain the right shape for a different reason -- whole-file rewrites produce ~16MB of fresh git blobs per walk -- and that argument is carried forward in the new maintenance ticket 'perishable-capture-dirs-vs-the-10mb-gitignore-rule', which has to settle whether this directory is gitignored at all before anyone picks a storage format. Closing here rather than leaving it open on speed grounds it no longer has.

TWO THINGS FOUND WHILE FINISHING THE WALK, both fixed in collect_settled.py. (1) THE COLLECTOR REPORTED NOTHING. The 2026-09-02 walk had been dead for three hours at 56% and the only way to find out was to stat the store's mtime -- the second stalled collection in this repo noticed by accident. collect() now takes a `progress` callback and prints one line per flush (position, store sizes, elapsed, rate), emitted on a flush that has already happened so it cannot claim progress the store does not hold. Pinned by test_collect_reports_progress_so_a_stall_is_visible. (2) A TRANSIENT FETCH FAILURE WAS STORED AS AN ANSWER. collect() wrote {'__error__': ...} on exception and the resume test was `s not in raw`, so one HTTP error permanently recorded 'nothing here' and no later run looked again. On data Kalshi ages out at ~60 days that is unrecoverable -- and the nine series it hit were not a random nine: KXCOMEYDISMISS, KXELECTUKRAINE, KXCRUDEEXPORTBAN, KXCONGRESSPAYINCREASE, KXDCEILEND, KXFTA and friends are exactly the one-off newsy by-deadline questions DD-2 says carry the effect. A biased loss. `_is_retryable` now re-walks a stored failure while keeping the deliberate page-cap skip permanent; a retry pass recovered all nine and the store now holds zero error entries beyond the 74 intended combinatorial-shard skips. Pinned by test_a_transient_series_failure_is_retried_but_a_page_cap_skip_is_not.
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
