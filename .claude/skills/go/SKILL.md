---
name: go
description: Run an autonomous research session — orient on current state, choose the highest-value work, do it, log it, and report. Use when the user says "go", or asks you to work on finding edge without specifying what to do.
---

# Autonomous Research Session

You are the researcher. Nobody is going to tell you what to test.

## 1. Orient (always, and cheaply)

```bash
python -m tools.cli theories list
python -m tools.cli opportunities list --disposition endorsed
python -m tools.cli ideas revisitable
```

Read the last ~30 lines of `RESEARCH_LOG.md` for what the previous session
was doing. For each active theory, `python -m tools.cli score report <id>`.

This is mechanical and costs almost nothing. Do it before deciding anything.

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
- **Pause or retire** a theory the evidence has killed — and record why
  against its originating idea.

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

## Rules

- Never present unresearched screen output as a recommended bet.
- Never retire a theory without recording why it failed against its idea.
- Search the idea registry before proposing anything new.
