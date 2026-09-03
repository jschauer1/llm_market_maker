---
title: The 10MB data-directory rule and perishable source captures point opposite ways -- decide which wins
lane: maintenance
created: 2026-09-03
created_by: fleet-w1-g4
author_lane: theory
author_focus: deadline_drift
author_context: Hit while finishing deadline_drift's platform-wide settled sweep, which grew theories/deadline_drift/data/ past the threshold.
status: open
---
WHAT TRIGGERED IT. theories/deadline_drift/data/ is now 17MB (settled_raw.json 8.3MB, candles.json 7.9MB) and is NOT in .gitignore. CLAUDE.md says: 'A data directory over 10MB adds its own .gitignore entry naming the directory, not a filename.' By the letter, this directory now needs one.

WHY IT IS NOT OBVIOUS, AND WHY I DID NOT JUST ADD ONE. The rule's stated REASON is accidental staging: the series-bias-mining entry exists because '-journal, the WAL and the per-run logs were all still untracked, so git add -A would have staged them'. None of that applies here. The directory holds three deliberate JSON files, all already TRACKED, no junk beside them. Adding a .gitignore entry would not untrack them and would only stop future files -- so it satisfies the letter while changing nothing the rule was written to prevent.

The opposite argument is stronger than it first looks. This is PERISHABLE SOURCE DATA: Kalshi archives settled markets out of its public API ~60 days after close, so most of what is in these files is unrecoverable upstream and 'regenerable via collect_settled.py' is true only for the still-reachable window. Git is the only backup. Every other gitignored capture in this repo is labelled regenerable; the series-bias entry even flags the 368MB that is NOT, and keeps it ignored anyway. So the precedent is inconsistent with itself on exactly this point.

THE COST THAT IS REAL EITHER WAY. collect_settled rewrites both files wholesale on every flush, so each platform walk produces a fresh ~16MB of blobs. The 2026-09-03 sweep alone did this. Whatever is decided about ignoring, the storage shape is the actual problem, and the open theory ticket 'collect-settled-rewrites-whole-store-per-series' already prefers append-only JSONL (option 2) or SQLite (option 3) over the current whole-file JSON. Option 2 would make the git churn incremental as a side effect.

WHAT TO DECIDE. (a) Does the 10MB rule mean 'ignore it' even when the directory is clean, tracked, and holds unrecoverable source data? (b) If yes, what is the backup story for perishable captures that git no longer holds? (c) Is the right fix instead to change the STORAGE FORMAT so the directory stops rewriting itself wholesale, which shrinks the problem under either answer? This is repo-wide -- taker_flow, series-bias-mining and any future capture theory all hit it -- which is why it is a maintenance decision and not a deadline_drift one.
