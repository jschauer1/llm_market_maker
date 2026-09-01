---
title: tools/http.py retries a 429 four times and gives up; long collectors need backoff-and-resume
lane: maintenance
created: 2026-09-01
created_by: llm-market-identifier-d8
author_lane: theory
author_focus: calibration_harvest
author_context: Hit while sizing the Sports population for calibration_harvest; the probe died on a 429 after 21 series and lost nothing only because it checkpoints per series.
status: open
---
WHAT HAPPENED. `collect size --categories Sports` (one `list_settled` per series, single-threaded) raised `HttpError: GET .../markets failed with status 429 after 4 attempts` after 21 of 3,274 series. The run died. It lost no data only because that probe checkpoints per series -- a collector that batched its writes would have lost the lot.

WHY THIS IS NEW INFORMATION. calibration_harvest's 2026-08-29 profiling established two things about Kalshi's limiter: requests serialize at ~4-5/s per client, and concurrency buys nothing (4 and 8 workers were no faster than 1; 12 started erroring). Both are in that theory's NOTES. What was NOT known is that a **long single-threaded walk still trips a 429** -- i.e. the limiter is not only a rate ceiling but has a sustained-volume component, and staying under the instantaneous rate is not sufficient. That matters for every collector this repo will ever write.

THE DEFECT. `tools/http.py` treats 429 like any other retryable status: 4 attempts, then raise. For a 429 specifically that is wrong twice over --
  - four quick retries against a limiter that wants you to *stop* can extend the penalty rather than clear it;
  - the correct response to 429 is exponential backoff honouring `Retry-After` if present, and for a multi-hour walk it is backoff-then-continue, not abort.

WHAT TO DO.
  1. Special-case 429 in `get_json`: honour `Retry-After`, else exponential backoff with jitter, with a materially larger attempt budget than the generic path.
  2. Give callers a way to say 'this is a long walk, sleep and continue rather than raising' -- collectors want that, an interactive quote lookup does not.
  3. Pin it with a test that a 429 with `Retry-After` is waited out rather than hammered.

CROSS-CUTTING, WHICH IS WHY THIS IS MAINTENANCE AND NOT A THEORY TICKET. Every tier-A replay in this repo is a long single-threaded walk over thousands of series: insider_bias/replay.py, the calibration_harvest collector, and anything the series-bias work grows into. They all inherit this. CLAUDE.md's collection convention ('record while you collect... an interrupted run resumes; it never restarts from zero') is currently carried entirely by each collector's own checkpointing, with the HTTP layer beneath it configured to give up.

CONTEXT ON URGENCY: calibration_harvest is retired as of 2026-09-01 so nothing is blocked on this today. File-worthy anyway because it is a silent tax on the next long walk somebody runs, and the failure mode is 'the run died three hours in' rather than an error anyone sees coming.
