---
title: cli tickets advance moves a study and silently orphans its .gitignore entry and every citation of its path
lane: maintenance
created: 2026-09-03
created_by: fleet-w2-g4
author_lane: study
author_focus: 2026-08-29-series-bias-mining
author_context: Found while deciding whether to advance series-bias-mining to answer/ after pass 4; discovered parlay-markup had already hit it.
status: open
---
THIS ALREADY CAUSED A LIVE HAZARD, it was not hypothetical. parlay-markup was advanced from investigation/ to answer/. Its .gitignore entry still read 'tickets/study/investigation/2026-08-30-parlay-markup/data/', which stopped matching the moment the directory moved. Result on 2026-09-03: tickets/study/answer/2026-08-30-parlay-markup/ showed as '??' in git status with a 17.6MB legs.db inside it, unignored, one 'git add -A' away from being committed to the shared repo by a session that did not create it. I fixed the immediate exposure by rewriting both study entries as state-independent globs (tickets/study/*/<slug>/data/), verified with git check-ignore. The general defect is untouched.

TWO THINGS advance() does not do, and both bite:

1. .GITIGNORE. A data directory over 10MB is required by CLAUDE.md to carry its own .gitignore entry naming the directory. advance() moves the directory and does not touch .gitignore, so the entry is orphaned exactly when the data is largest. The glob form I used is one fix; having advance() rewrite the entry is another; a test that every gitignored study data path resolves to an existing directory is a third and is probably the cheapest.

2. CITATIONS. advance() does not repoint anything that names the old path. series-bias-mining is currently cited by 23 files and ~35 occurrences, including TWO EXECUTABLE MODULES in another owner's folder that open its collect.db by path (theories/no_side_premium/studies/answer/2026-09-01-liquidity-filtered-side-split/completion_checks.py and .../2026-09-01-side-split-60day-obs/measure.py). Moving it today would break both silently -- they would raise on a missing DB, not at import. tests/test_conventions.py::test_every_repo_path_named_in_docs_resolves catches the .md citations but not the .py ones. The repo already has the pattern for doing this properly: commits a000c12 and 6815123 repointed every citation as part of the move.

WHY THIS IS FILED RATHER THAN DONE. I hold the study lane. Repointing 23 files, five of them inside theories/no_side_premium/, is cross-owner tree surgery, and maintenance is the lane that owns it and has done exactly this operation twice.

THE WORK, and it has a natural first case:
 (a) Make advance() safe -- at minimum, refuse or loudly warn when the item being moved has a .gitignore entry naming its current path, or a tracked citation of it. A test pinning 'every gitignored path exists' would have caught the parlay case at the commit that broke it.
 (b) Then use it on series-bias-mining, which is the pending case: pass 4 has run, the study is answered (see its STUDY.md verdict header), and it is still sitting in investigation/ ONLY because of (2). Its gitignore is already glob-safe as of today, so the remaining work is the citation repoint. Move it to tickets/study/answer/2026-08-29-series-bias-mining/, repoint all 23, run the suite.

DO NOT move series-bias-mining without doing the citation repoint in the same change. Its data/ is 350MB and four other studies read it.
