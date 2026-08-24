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
from tools import db, snapshot
from tools.kalshi import markets

board = markets.list_open()          # complete board, ~95k markets, ~1 min
conn = db.connect(); db.init_db(conn)
snapshot.save_kalshi(conn, board)
```

Every number the rest of this session produces — which markets are open,
what they cost, what a screen returns — is only as current as this fetch.
Reasoning over yesterday's board without noticing is exactly the failure
mode this step exists to prevent. `market_snapshots` is also the first-party
price history this project accrues over time; skip this and a day of history
is gone permanently, not deferred. `list_open` always pages to exhaustion —
there is no partial-fetch option — so budget the minute it takes rather than
assuming it's free.

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

**Prefer work that changes a decision.** If nothing settled since yesterday,
re-scoring is busywork — go hunt. If every active theory is unproven, another
scan adds unproven suggestions while a backtest adds evidence. If the same
theory has been scanned three sessions running with nothing settled yet, the
marginal value is in a *new* theory, not a fourth scan of the old one.

State which you picked and why in one line, so the user can redirect cheaply.

A short session is fine. "Nothing settled, no theory needs backtesting, I
researched two candidates and rejected both, here's why" is a good outcome.
Do not manufacture work.

## 3. Log it

Append to `RESEARCH_LOG.md`:

```markdown
## YYYY-MM-DD — <one-line summary>

**Did:** what you actually did.
**Learned:** what you now know that you didn't.
**Next:** what is worth picking up next session.
```

Theory-specific findings also go in that theory's `THEORY.md` Learnings.
This log is what makes a year of sessions accumulate instead of repeat.

## 4. Report for a human

End with what the user needs: bets worth placing now, anything that changed
about a theory's standing, anything needing their judgment. Not a transcript
of tool calls.

**Any theory awaiting a retirement ruling goes here explicitly** — the
rationale, the numbers behind it, and what you ruled out. That is a decision
only they can make, and it does not get made if you leave it in the database.

Tell them they can record what they actually bet with
`python -m tools.cli opportunities mark-taken <id> taken --size <N> --reason
"<why>"` (or `skipped` with a reason). This is not optional bookkeeping: until
a bet is marked `taken`, `roi_taken` stays `null` forever, and divergences
between what was endorsed and what was actually bet — the raw material
`compare-theories` mines for new theory candidates — are invisible.

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
