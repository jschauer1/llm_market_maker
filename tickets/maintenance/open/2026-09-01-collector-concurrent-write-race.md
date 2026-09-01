---
title: Two concurrent collectors silently lose each other's data, and TaskStop does not stop one
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-9e
author_lane: theory
author_focus: deadline_drift
author_context: Hit while running deadline_drift's settled capture: a collector I had stopped was still alive and silently un-writing the new one's rows.
status: open
---
MEASURED, TODAY, IN THIS REPO. deadline_drift's settled capture was running; anchors.json went 332 -> 294 markets while the walk was still adding. Markets cannot un-settle. Cause: TWO collect_settled processes were live at once.

TWO SEPARATE DEFECTS, both general.

1. TaskStop stops the SHELL, not the detached child. I stopped background task b07k64uvi and the harness reported success; `Get-CimInstance Win32_Process` showed its python.exe (PID 28132) still running 9 minutes later, still fetching, still writing. `ps -ef` in Git Bash here shows only the interpreter path, NOT the arguments, so `ps -ef | grep collect_settled` returns ZERO while the process is running -- the obvious check silently says 'nothing running'. Get-CimInstance Win32_Process with CommandLine is the check that works. Worth putting that one-liner somewhere a session will find it.

2. The standard collector write pattern is load-modify-save over a whole JSON file, and it has no lock. Every collector in this repo built to the 'record while you collect' convention does this: _load() the whole dict at start, mutate, _save() the whole file after each item. Two processes each hold a snapshot from their own start time, so whichever saves last erases everything the other added since. It is a lost-update race with no error, no warning, and no trace in the file afterwards -- the data is simply not there, and the only way I noticed was watching a monotonically-increasing count go down.

WHY THIS IS WORTH A SESSION. This repo runs several sessions at once (four were live when this happened) and CLAUDE.md tells every one of them to top up captures whose marker is stale. Two sessions obeying that instruction on the same theory is not an unlucky coincidence, it is the documented procedure. And the loss is silent AND partially unrecoverable: Kalshi archives settled markets ~60 days after close, so a market dropped from the file by a race and not re-walked before it ages out is gone upstream permanently. That is the exact failure the incremental-write convention exists to prevent, defeated by the convention's own implementation.

WHAT TO DO. A lock beside the data file is enough -- O_EXCL create with the pid, refuse to start if held and unstale, remove on exit. tools/ is the right home since every theory needs it: something like tools/filelock.py, then have each collector take it. Cheap. Alternatively make the collectors append-only (JSONL per record) so concurrent writers interleave instead of overwriting, which also removes the O(n^2) whole-file rewrite; bigger change, better end state.

NOTE FOR WHOEVER TAKES THIS: deadline_drift's own data is not at risk from this incident. Its collector is resumable and skips what is on disk, so a re-run refills anything the race dropped, and I am re-running it. The ticket is about the pattern, not that file.

## Addendum, same session: the same write pattern also fails on OneDrive, and that half is now fixed locally

Two more failures of `_load()/mutate/_save(whole file)`, both hit for real
while the ticket was open.

**OneDrive interference.** This repo lives under `OneDrive\Documents`, and
the sync client intermittently holds a handle on a file being rewritten.
The wide walk died at **874 of 960 series** with
`OSError: [Errno 22] Invalid argument` on open-for-write. It cost nothing
only because the open failed *before* truncating and the collector is
resumable — a failure a moment later would have left a truncated file
where 1,859 markets of capture used to be, and ~60 days of that is
unrecoverable upstream.

**Truncation windows for readers.** `Path.write_text` opens mode `"w"`,
so any reader — a peer session, or an analysis script in the same session
— can catch the file empty or half-written. I hit this too: a `json.load`
mid-walk raised `JSONDecodeError: Expecting value: line 1 column 1`.

**Fixed in `theories/deadline_drift/collect_settled.py::_save`**: write to
`<name>.tmp`, then `os.replace` (atomic on Windows within a volume), with
six retries on `OSError` and a backoff. A reader now always sees either
the old file or the new one, and a transient sync lock costs a retry
instead of a run.

**That is one collector.** Every other collector built to the
record-while-you-collect convention still uses the plain whole-file
rewrite and is exposed to both failure modes. This is a stronger argument
for promoting the write helper to `tools/` than the original race was:
the atomic-replace part is ~10 lines, needs no lock protocol, is
obviously correct, and fixes a failure that is already happening. The
lock for concurrent writers is the harder half and can follow.
