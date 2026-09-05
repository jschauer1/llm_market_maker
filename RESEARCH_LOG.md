# Research changes that affect the next session

For reusable findings, [choose a question in the knowledge map](knowledge/README.md).
For open work and current status, use owner tickets and the CLI.

An entry earns space when it changes another session's decision: explain the
change, its implication, and link the canonical source in at most 80 words.
Routine completion stays in the task record. Keep at most eight entries and
800 words; rotate older complete entries through [the archive map](knowledge/archive/README.md).
The [memory policy](docs/agents/research-memory.md) defines the full contract.

## 2026-09-04 — Read through decisions and scoped lessons

Research context now starts with question summaries and individual lesson
cards. Agents retrieve relevant evidence instead of reading complete
notebooks. Save a lesson only when it changes a future action or avoids
expensive repetition; consolidate existing cards and omit low-value recaps.
Initial migration is deliberately selective, capped at sixteen cards.
[Writing and retrieval rules](docs/agents/research-memory.md).

## 2026-09-04 — Share calibration across comparable judges

The user adopts an idealized judge: models following the same written procedure
share calibration even when actual classifications differ. Aim for comparable
intelligence and retain exact provenance. A provider/model switch alone needs
no experiment, version bump, or evidence reset. Historical replays still verify
their own cutoff and contamination eligibility.
[Judge policy](docs/RESEARCH_GUIDE.md#record-what-judged-and-what-you-asked-it).

<!-- research-memory-archive: knowledge/archive/research-log-through-2026-09-04.md -->

## 2026-09-05 — Reusing a cache does not broaden its evidence

News Drift's first replay exposed a reusable data limitation: the shared daily
cache inherits the insider collector's category, final-volume and close-window
filters. Its 204 replayed positions stay experimental, with no production
calibration. New theories should inspect the collector before interpreting
cached rows as a complete population. [Selection lesson](knowledge/lessons/history-cache-inherits-collector-population.md).

## 2026-09-05 — Check historical settlement rules before collecting a long replay

WG-1 found the same station tickers changed from NWS to The Weather Company
on August 14. A six-month inventory therefore contained only 18 comparable
history dates per city, leaving the new weather model unconfirmed. Future
forecast research should census settlement-source regimes before buying or
collecting long histories. [Scoped lesson](theories/weather_model_gap/learnings/source-change-resets-calibration.md).

## 2026-09-05 — Public inputs still need a useful forecast

TRG-1 reconstructed four known TSA days and forecast the remaining three, but
its frozen 44-position holdout lost 8.07 net points. Both sides were negative;
source revisions additionally limit the reconstruction. The implemented theory
is under review. Do not repeat this exposed holdout as fresh confirmation or
assume that adding public data creates an edge. [Failure and revisit condition](theories/tsa_remainder_gap/learnings/unconditional-remainder-failed.md).

## 2026-09-05 — Price, edge and judgment must belong to one decision

A live refresh exposed mixed-attempt arithmetic: a latest estimate paired with
an original entry could invent several points of edge. Promotion now reads a
coherent latest attempt, and historical scoring selects a coherent earlier
one. Impossible old binary claims require a new bounded decision; original
receipts remain intact. [Selection rule and regression evidence](knowledge/lessons/keep-estimates-on-one-attempt.md).
