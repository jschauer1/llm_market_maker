---
title: The title/rules backfill should read the captured payload file, not re-fetch an archive that no longer holds them
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: fleet-w3-g1
author_lane: study
author_focus: 2026-09-01-early-close-exposure-in-the-bettable-slice
author_context: Noticed while capturing raw payloads for the judged-campaign population; the capture happens to be exactly what the existing backfill ticket needs.
status: open
---
THIS IS A NOTE ON AN EXISTING TICKET, NOT A NEW WORK ITEM. It amends theories/insider_bias/insider_judgment/tickets/open/2026-09-01-backfill-titles-from-judging-payloads.md with a data source that did not exist when that ticket was filed, and with a deadline that did.

WHAT IS NOW ON DISK. tickets/study/answer/2026-09-01-early-close-exposure-in-the-bettable-slice/raw_markets.jsonl holds the COMPLETE raw /markets/{ticker} payload for 1,413 of the 1,564 distinct tickers in the three judged campaign runs (s200, s200b, s57) -- one JSON object per line, {ticker, ok, market}. That includes title, subtitle, yes_sub_title, rules_primary, rules_secondary, close_time, expiration_time, custom_strike, result, and every other field Kalshi returns. It was captured 2026-09-01 for a different question, and kept complete rather than reduced precisely so a future session could ask something else of it.

WHY IT MATTERS FOR THE BACKFILL. The remaining 151 tickers (9.7%) returned 404: they have already aged out of Kalshi's public archive, which drops settled markets roughly 60 days after close. They are recorded in the same file as {ok: false} lines so the loss is explicit rather than silent. A backfill that re-fetches from the API today gets 1,413 of 1,564 at best, and fewer every day -- the same window measured 2.9% unreachable on 2026-08-29 and 9.7% on 2026-09-01. Reading the captured file instead gets the same 1,413 at zero network cost, deterministically, and will keep working after Kalshi has dropped all of them.

SO: point the backfill at the file, and treat the API only as a fallback for tickers the file does not carry. If the backfill also wants the fullcov populations (insider-fullcov n=3,195, mention-fullcov n=3,325), those are NOT in this capture -- it scoped to the judged runs -- and they are older, so they are aging out faster. Capturing them with the same collector is cheap and is the thing to do FIRST if anyone wants that data at all; classification and backfill can happen any time afterwards, but capture cannot.

REUSE. tickets/study/answer/2026-09-01-early-close-exposure-in-the-bettable-slice/collect.py is ~90 lines, resumable (skips what is already in the file, flushes per ticker), and needs only its RUNS tuple changed.
