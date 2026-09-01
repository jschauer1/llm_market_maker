# user_reports — what the floor tells you, one directory per day

```
user_reports/
  README.md              <- this file (tracked)
  2026-09-01/
    README.md            <- the day's floor report; this is the thing to read
    <attachments>        <- optional, and only when the report cites them
  2026-09-02/
    README.md
```

**One directory per day, named `YYYY-MM-DD`.** The floor writes it, links
it when it closes its claim (`floor complete --report <path>`), and
summarizes it in the terminal. Nothing else writes here.

Days are directories rather than single files so a report can carry
what it cites — a funnel table too wide for prose, a judged payload, a
subagent's raw output — without either bloating the report or leaving the
number unverifiable. Most days there will be nothing but `README.md`, and
that is the expected case.

## What the day's README contains, in this order

The order is what you act on first, not what happened first.

1. **Bets** — every candidate that cleared the promotion key (R1
   RECOMMENDED, R2 RISKLESS, R3 PROVISIONAL), with ticker, side, today's
   ask, claimed and ranked edge, the segment that earned it, the n and
   settlement days behind it, edge basis, and suggested size. R3 is
   labelled with exactly what it is missing. R2 baskets itemize every leg
   with its own ask and the verify-every-leg warning.

   **An empty table is a valid table** and most days it will be empty.
   A day with no bet is not a day with no information — section 2 is
   where the information is.

2. **Theories** — one short block per running theory: what it did today
   and why nothing came of it. Found nothing / found candidates not yet
   evidenced / measured against / blocked at a stage. Sub-theories get
   their own line on the same terms, because a sub-theory's evidence is
   its own and can be strong while its parent is flat.

3. **For your ruling** — everything escalated instead of asked: pending
   retirements with their diagnosis, orphaned evidence, gaps in the
   promotion key, permission-blocked actions. Carried every day until you
   rule on it.

4. **Queue** — endorsed positions still open and untouched, re-quoted at
   today's ask: which still stand, which were closed as stale. Then the
   asks, **by id**, so you can answer one line:

   ```bash
   python -m tools.cli opportunities mark-taken <id> taken \
       --theory <slug> --size <N> --reason "<why>"
   ```

   Until a bet is marked, `roi_taken` stays `null` and the divergence
   signal never accumulates.

5. **Floor record** — the receipt, last because it is the least
   actionable: which theories ran through which stages, what the gates
   removed by category, what settled, and how the scores moved.

## What this folder is not

**Not the audit trail.** The record lives in the database, each theory's
`NOTES.md`, and `RESEARCH_LOG.md`. These are written for you to read, and
they are regenerable from the ledger — if a report and the database
disagree, the database is right.

**Sessions may read past reports; they may never cite one as evidence.**
Reading yesterday's report to see what was already said is useful and
allowed. But a report is a *rendering* of the ledger at a moment, so any
number a session acts on comes from `score report`, `slices report` or
`promote` — never from a report file. Citing a report as evidence would
let a stale figure launder itself into a new decision, and the whole
point of computing rungs mechanically is that nothing gets to do that.

The day directories are git-ignored; this README is not, so the shape
survives a fresh clone.
