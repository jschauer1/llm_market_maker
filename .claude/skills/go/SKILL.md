---
name: go
description: Run an autonomous research session — orient on current state, choose the highest-value work, do it, log it, and report. Use when the user says "go", or asks you to work on finding edge without specifying what to do.
---

# Autonomous Research Session

You are the researcher. Nobody is going to tell you what to test.

## 1. Orient (always)

**First, pull a fresh Kalshi board.** This is not optional, and it comes
before every local-state query below:

```python
from tools import board as board_tool, db

conn = db.connect(); db.init_db(conn)
board = board_tool.get_board(conn, force=True)   # ~100k markets, ~13s
```

`force=True` here and **nowhere else**: this is the session's one deliberate
refresh. Every number the rest of the session produces — which markets are
open, what they cost, what a screen returns — is only as current as this
fetch, and reasoning over yesterday's board without noticing is the failure
this step prevents. The pull is snapshotted automatically, so it also feeds
the first-party price history the project accrues.

**Every later call in the session — and every theory — uses
`board_tool.get_board(conn)` with no `force`**, which reuses this pull
instead of re-walking the feed. One session, one board. Two sessions on
2026-08-24 each pulled ~100k markets 19 hours apart because that reuse was
prose rather than a function; it is a function now.

Then read local state:

```bash
python -m tools.cli theories list
python -m tools.cli theories list --running   # testing + active + under_review
python -m tools.cli theories pending-retirement
python -m tools.cli opportunities list --disposition endorsed
python -m tools.cli ideas revisitable
```

Read the last ~30 lines of `RESEARCH_LOG.md` for what the previous session
was doing. For each theory that runs, `python -m tools.cli score report <id>`.

Anything `pending-retirement` returns is a decision **waiting on the user**,
and it stays waiting until they rule. Carry it into your report every session
— a standing proposal nobody mentions is not a suggestion to anyone.

**Then work the queue.** Endorsed positions that are still open and still
`user_action='untouched'` are bets this system recommended and nobody has
resolved — the user may have placed them, skipped them, or never seen them.
The listing above is the raw material; derive the queue from it:

```python
import json, subprocess
rows = json.loads(subprocess.run(
    ["python", "-m", "tools.cli", "opportunities", "list",
     "--disposition", "endorsed"], capture_output=True, text=True).stdout)
queued = [r for r in rows
          if not r.get("settled_at")
          and (r.get("user_action") or "untouched") == "untouched"]
```

A queued bet **decays**, which is why this belongs in Orient and not in the
report. Three things to check on each, cheapest first:

1. **Age and close time.** A recommendation carries the price it was made
   at. One made three sessions ago against a market closing tomorrow is not
   a live suggestion, and repeating it as though it were is how a stale ask
   becomes a bad bet.
2. **Re-quote before re-recommending.** `markets.quotes([tickers])` gives
   the current ask for a handful of tickers without touching the board. If
   the edge is gone at today's price, say so and stop carrying it.
3. **Chase the disposition.** Ask the user to `mark-taken … taken` or
   `… skipped` on anything they have already acted on. Until they do,
   `roi_taken` stays `null` forever and the endorsed-vs-actually-bet
   divergence — the raw material `compare-theories` mines — never
   accumulates. A queue that only grows is a queue nobody is learning from.

Never silently re-endorse a queued bet to pad a report. Either it still
clears its bar at today's ask, in which case say it is the *same* position
still standing, or it does not, in which case it is closed out.

The local-state queries are mechanical and cost almost nothing; the board
fetch above is the expensive part of this step, and still required. Do all
of it before deciding anything.

## 2. Update the theories (always)

**This is the part of `go` that is not a choice.** The user must be able to
say `go`, walk away, and come back knowing every running theory saw today's
board. A session that skipped straight to something more interesting and
left the theories un-run has failed at its one standing obligation, however
good the thing it did instead was.

Two halves, in order:

1. **See how they are doing.** Settle what resolved and recompute scores
   (`score-theories`). This is what turns yesterday's recommendations into
   evidence, and it is what tells you whether anything's standing changed.
2. **Re-run each of them against today's data.** Every theory whose status
   is `testing`, `active`, or `under_review` gets run — `under_review`
   included, because pulling a theory you suspect is broken is how you
   guarantee you never find out whether it was broken or merely unlucky.
   Record what each produces, including rejections.

Both halves are on the *whole running set*, not on whichever theory is
currently interesting.

**Skip it only when it is already done today.** The check is per theory,
not per session:

```python
from tools import db
conn = db.connect()
for r in conn.execute(
    "SELECT theory_id, MAX(DATE(last_seen_at)) AS last_day "
    "FROM opportunities WHERE run_mode = 'live' GROUP BY theory_id"
):
    print(dict(r))
```

Compare that against `theories list --running`: a running theory missing
from the result, or carrying an older date, has not been updated today. If
every running theory is current, say so in one line and go straight to §3 —
re-running a theory twice against the same board produces nothing but
duplicate rows and wasted time.

**One caveat that check cannot cover: a scan that legitimately found
nothing writes no rows, so it is indistinguishable from a scan that never
happened.** Until that is fixed, close the gap in prose — when a theory
runs and produces no candidates, say so explicitly in the session log
("`mention_family`: ran, 0 candidates"). A future session reading only the
ledger cannot tell the difference, and will either redo your work or
wrongly assume it was done.

**Then stop.** Updating the theories is the floor, not the session. Once
they are current, the rest of the time is yours.

## 3. Then work the value list — item by item

The theories are current; this is where the session earns more than its
floor. **This step is a loop, not a single pick**: choose the top item,
do it, report it (§5), then come back to this menu and choose the next.
The standing menu, roughly highest-leverage first:

- **Research a queued or freshly-screened candidate** into a real
  recommendation (`find-edge`) — §2 ran the theories; this is the deeper
  pass on what they surfaced.
- **Build a queued theory.** Twenty-two researched, implementable specs sit
  in
  [docs/superpowers/specs/theories/](../../../docs/superpowers/specs/theories/)
  — start at the backlog index — and far more are specced than built
  (`theories list` against that folder tells you the current gap). Every
  instrument added widens the board the "what is the best bet right now?"
  question can be asked about, and a mechanical one carries evidence
  immediately (tier A, `edge_basis='model'`, no judgment to wait on). Check
  `ideas search "<slug>"` first in case the idea has since been killed or
  parked, and the build tracker in
  [docs/superpowers/plans/theories/](../../../docs/superpowers/plans/theories/)
  in case someone is already on it, then `propose-theory`.
- **Backtest** a theory running on claims rather than evidence
  (`backtest-theory`).
- **Propose a new theory** (`propose-theory`) — from a market pattern you
  noticed, a gap in what current theories cover, or a recurring `user_reason`
  divergence.
- **Revisit a parked or dead idea** whose `revisit_after` condition may now be
  met, or that carries a `revisit_angle` worth trying differently.
- **Tighten a theory** — migrate a stage-2 heuristic that keeps proving itself
  into stage 1 code (bump the version), or promote a theory-local tool that
  now has multiple callers.
- **Diagnose an `under_review` theory** — often the highest-value work on the
  board. Its numbers are bad and nobody knows why yet; the checklist in
  `score-theories` §5 turns that into an answer. The outcome is usually a
  narrower version, not a burial.

**Prefer work that changes a decision.** §2 already ran the theories, so a
second scan of the same board is not an option — the question is what the
board cannot tell you yet. If every active theory is unproven, another
scan adds unproven suggestions while a backtest adds evidence. If the same
theory has been scanned three sessions running with nothing settled yet, the
marginal value is in a *new* theory, not a fourth scan of the old one.

State which you picked and why in one line, so the user can redirect
cheaply — then, when the item is done and reported, **pick up the next
one**. The user's standing preference (2026-08-27) is explicit: do a
high-value thing, write the report, then start another high-value thing
without waiting to be asked. One item is a busy day's floor, not the
target.

The loop has exactly two exits:

- **Nothing left that changes a decision.** Every remaining menu item
  would be busywork — a re-scan of a board already scanned, a backtest
  nobody would act on. Say so and end; an empty menu honestly reported
  beats a padded one. Do not manufacture work.
- **Blocked on input only the user can give** — a retirement ruling, a
  scope call, an ambiguous redirect. Name exactly what you need, then
  end.

Ending for any other reason — "one thing is done", "the report is
written", "the session feels long" — is the failure mode this loop
exists to prevent: a report is a checkpoint, never a finish line.

## 3a. How much to delegate

**Your call, every time.** Reading the numbers and doing the work yourself
is a perfectly good session. Subagents are available when the work is
genuinely wide — several theories to diagnose at once, a batch of
candidates to judge — and they are not a target to hit.

Two things are worth knowing whichever way you go:

**Numbers come from code, not from a model.** `score report <id>`,
`compare-theories` and `bucket_rates` print exact figures. Asking a model
to read numbers a command already prints is the expensive way to get an
answer that was never in doubt, and it can get them subtly wrong.

**If you do delegate, the findings go to disk before they reach you.** A
per-theory diagnosis belongs in that theory's `NOTES.md` as a dated entry,
including what it ruled out and the slices that showed nothing; anything
that changes what the theory *claims* is distilled into `THEORY.md`, and
the session log gets a pointer rather than a copy. Reasoning that exists
only in a subagent's reply dies with the session that read it.

**Where that reasoning is recorded is not a free choice.** A subagent
diagnosing performance is *not* in any theory's decision path, so it does
**not** get a `judgment_runs` row — provenance records what judged a bet,
and filing analysis there pollutes it and muddies the backtest tier rules.
Provenance is for LLM steps inside a theory's own procedure — a gate, an
analysis stage, a final review — recorded with the model and the exact
prompt file, as always.

## 4. Log it

Append to `RESEARCH_LOG.md`:

```markdown
## YYYY-MM-DD — <one-line summary>

**Did:** what you actually did.
**Learned:** what you now know that you didn't.
**Next:** what is worth picking up next session.
```

Keep this log cross-cutting. Theory-specific findings go in that theory's
`NOTES.md` — dated, raw, append-only — and the log entry points at them
rather than repeating them; `THEORY.md` changes only when the claim, the
procedure, or the status changes. This log is what makes a year of sessions
accumulate instead of repeat.

## 5. Report for a human

**A report lands after every §3 item, not once at the end.** Write it as
visible text the moment the item is done, then head back to the §3 menu
— the report is the checkpoint where the user can redirect; the work
continuing is the default, not something they must request. The first
report of the session opens with the standing obligation below; later
ones need only what their item found. The session's last report carries
the cumulative queue picture and the mark-taken asks.

**Open with the standing obligation:** which theories were updated today,
what each produced (including "ran, nothing"), and anything that settled.
One or two lines. The user's baseline expectation from `go` is that this
happened, so it is the first thing they should be able to confirm — not
something they have to go and check.

Then what they need: bets worth placing now, anything that changed about a
theory's standing, anything needing their judgment. Not a transcript of
tool calls.

**Any theory awaiting a retirement ruling goes here explicitly** — the
rationale, the numbers behind it, and what you ruled out. That is a decision
only they can make, and it does not get made if you leave it in the database.

**Report the queue, not just today's finds.** Every endorsed position still
open and still `untouched` is a bet the user may not know is outstanding.
Say how many there are, which still clear their bar at today's ask, and
which you closed out as stale — a queue nobody reads is a list of bets
quietly expiring.

Tell them they can record what they actually bet with
`python -m tools.cli opportunities mark-taken <id> taken --size <N> --reason
"<why>"` (or `skipped` with a reason). This is not optional bookkeeping: until
a bet is marked `taken`, `roi_taken` stays `null` forever, and divergences
between what was endorsed and what was actually bet — the raw material
`compare-theories` mines for new theory candidates — are invisible. Name the
specific ids you want resolved rather than repeating the command generically;
a request to mark "whatever you did" gets acted on far less often than
"did you take 9204?".

## Rules

- Never present unresearched screen output as a recommended bet — *unless* the
  theory computed the edge mechanically (`edge_basis='model'`), in which case
  there was nothing to research and it is recommendable as-is.
- **Never write off an underperforming theory.** Diagnose it — `score-theories`
  §5. The salvageable cases (fees ate a real edge, judgment inverted over a
  sound screen, one slice profitable, sample too small to mean anything) all
  look identical to death from outside.
- **Retiring is the user's decision, not yours.** Diagnose, then
  `theories propose-retirement <id> --rationale "..."`, then raise it in your
  report. The tooling refuses to let you retire a theory yourself.
- Never retire a theory without recording why it failed against its idea.
- Search the idea registry before proposing anything new.
- **Updating the running theories is not optional and not a menu item.** If
  something blocks it — an API down, a theory erroring — say so plainly in
  the report rather than quietly doing other work instead. A session that
  did something clever while the theories went another day without seeing
  the board has traded the user's standing expectation for its own
  preference.
- **A theory that ran and found nothing must say so in the log.** The
  ledger records candidates, not scans, so "no rows" and "never ran" look
  identical to the next session.
- **A report is a checkpoint, never a finish line.** After reporting an
  item, return to the §3 menu and take the next one; the only two ways
  a session ends are the §3 exits (nothing decision-changing left, or
  blocked on the user).
- **A subagent's findings go to disk before they reach you.** Per-theory
  analysis lands in that theory's `NOTES.md`; only a subagent inside a
  theory's own decision path gets a `judgment_runs` row. Reasoning that
  exists only in a subagent's reply dies with the session that read it.
