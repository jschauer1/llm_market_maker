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

## 2. Choose where the value is

This is the judgment call that makes the session worth running. The standing
menu:

- **Settle and score** what has resolved (`score-theories`).
- **Hunt for live edge** with the active theories (`find-edge`).
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
- **Sweep every running theory at once** — when several theories have
  settled rows, put one subagent on each rather than walking them serially.
  See "Working theories in parallel" below for what to delegate and what to
  keep in code.

**Prefer work that changes a decision.** If nothing settled since yesterday,
re-scoring is busywork — go hunt. If every active theory is unproven, another
scan adds unproven suggestions while a backtest adds evidence. If the same
theory has been scanned three sessions running with nothing settled yet, the
marginal value is in a *new* theory, not a fourth scan of the old one.

State which you picked and why in one line, so the user can redirect cheaply.

A short session is fine. "Nothing settled, no theory needs backtesting, I
researched two candidates and rejected both, here's why" is a good outcome.
Do not manufacture work.

## 2a. Working theories in parallel

As the board grows past two or three theories, "how is everything doing?"
stops fitting in one session's head. Split it the way the repo is already
laid out: you hold the repo level — what each theory claims, what it has
demonstrated, which is worth acting on — and a subagent per theory holds
the depth.

**Get the numbers from code, not from a model.** `score report <id>`,
`compare-theories`, and `bucket_rates` already print exact figures.
Dispatching a subagent to read numbers a command prints is the expensive
way to get an answer that was never in doubt, and it can get them subtly
wrong. Pull the numbers yourself first; they are what tell you which
theories are even worth a deeper look.

**Delegate the part that is actually analysis.** Once a theory looks
broken or ambiguous, the `score-theories` §5 diagnosis is real work —
slice the settled rows by side, price band, days-to-close, sub-family and
`theory_version`, with honest p-values, event-clustered checks and
multiple-comparison awareness. That is one subagent per theory, run
concurrently, each given: its theory's folder, the numbers you already
pulled, and the §5 checklist. It is also the shape the repo is built for
— a theory folder is self-sufficient, so a theory-level agent needs only
that folder plus `tools/`.

**Each subagent writes its own findings to disk before reporting.** A
per-theory diagnosis goes in that theory's `NOTES.md` as a dated entry —
raw, including what it ruled out and the slices that showed nothing.
Anything that changes what the theory *claims* is distilled into
`THEORY.md`; the session log gets a pointer, not a copy.

**Where that reasoning is recorded is not a free choice.** A diagnosis
subagent is *not* in any theory's decision path, so it does **not** get a
`judgment_runs` row — provenance records what judged a bet, and filing
analysis there pollutes it and muddies the backtest tier rules. Its
reasoning belongs in `NOTES.md`. Provenance is for LLM steps inside a
theory's own procedure — a gate, an analysis stage, a final review — and
those are recorded with the model and the exact prompt file, as always.

A parallel sweep is worth it when several theories have new settled rows
or one is genuinely puzzling. With two theories on the board and nothing
newly settled, just read the numbers — the cascade exists to avoid
expense, not to generate it.


## 3. Log it

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

## 4. Report for a human

End with what the user needs: bets worth placing now, anything that changed
about a theory's standing, anything needing their judgment. Not a transcript
of tool calls.

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
- **A subagent's findings go to disk before they reach you.** Per-theory
  analysis lands in that theory's `NOTES.md`; only a subagent inside a
  theory's own decision path gets a `judgment_runs` row. Reasoning that
  exists only in a subagent's reply dies with the session that read it.
