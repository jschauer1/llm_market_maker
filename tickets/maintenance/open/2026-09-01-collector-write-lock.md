---
title: Collectors still need a lock: atomic writes fixed truncation, not the lost-update race
lane: maintenance
created: 2026-09-01
created_by: fleet-w2-g1
author_lane: maintenance
author_context: Split off from collector-concurrent-write-race after its atomic-write half shipped as tools/atomic_write.py.
status: open
---
WHAT IS ALREADY DONE. tools/atomic_write.py (shipped 2026-09-01, tests/test_atomic_write.py) fixes the two SINGLE-writer failures: a sync client holding a handle mid-rewrite, and a reader catching a truncated file. Every collector now writes .tmp then os.replace. tools/README.md documents it.

WHAT IS NOT DONE, AND WHY ATOMICITY DOES NOT FIX IT. Two processes doing load-mutate-save each hold a snapshot from their own start time. Whichever replaces last still erases everything the other added -- and now it does so ATOMICALLY, which means the file is always well-formed and the loss is even harder to spot. The measured incident stands: anchors.json went 332 -> 294 markets while the walk was still adding, noticed only because a monotonically-increasing count went down.

WHY IT IS WORTH A SESSION. This is the documented procedure colliding with itself, not bad luck: several sessions run at once (four were live when it happened, three on 2026-09-01 evening) and CLAUDE.md tells every one of them to top up a capture whose marker is stale. The loss is silent AND partially unrecoverable -- Kalshi archives settled markets ~60 days after close, so a market dropped by a race and not re-walked before it ages out is gone upstream permanently.

WHAT TO DO. The ticket that spawned this recommended a lock beside the data file: O_EXCL create carrying the pid, refuse to start if held and unstale, remove on exit. tools/filelock.py, then each collector takes it. Note the staleness half is the fiddly part -- a session that dies leaves a lock behind, and a lock nobody can clear is worse than the race. Consider recording a heartbeat timestamp in the lock file and treating it as stale after N minutes.

ALTERNATIVE, BIGGER, BETTER END STATE. Make the collectors append-only (JSONL per record) so concurrent writers interleave instead of overwriting. That removes the race by construction rather than by protocol, and also removes the O(n^2) whole-file rewrite that makes a long walk quadratically slower. atomic_write stays useful for checkpoints and small state files either way.

OPERATIONAL NOTE, ALREADY DOCUMENTED IN tools/README.md: the obvious pre-flight check lies. Git Bash 'ps -ef' shows only the interpreter path, not the arguments, so 'ps -ef | grep collect_settled' returns ZERO while the collector runs. Use Get-CimInstance Win32_Process with CommandLine. And stopping a background harness task stops the SHELL, not the detached child -- a stopped task's python.exe was still fetching nine minutes later.
