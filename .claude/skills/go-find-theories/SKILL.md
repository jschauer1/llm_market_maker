---
name: go-find-theories
description: Go looking for theses nobody here has proposed — read the outside world and the board, check each against what is already built, specced or tried, and file what survives. Invoked by go when the find-theories lane is claimed.
---

# go-find-theories — go looking for theses

Invoked by `go` once you hold the find-theories lane. **This lane
produces tickets and registry entries, not theories.** `go-new-theory`
takes one thesis all the way to running; this one goes and finds theses
worth taking there, and it exists because the repo runs out of ideas long
before it runs out of capacity to test them.

**Find as many as you can.** This is the one lane where volume is the
point — but each one has to clear the bar in §3, because twenty
mechanism-free topics are worth less than three real hypotheses and cost
the next session a day of triage.

## 1. Know what is already here, before you look anywhere else

You cannot tell whether an idea is new until you know what exists. Load
all four:

```bash
python -m tools.cli theories list                  # built, at any status
python -m tools.cli ideas search ""                # the registry, incl. dead
python -m tools.cli tickets list --lane new-theory # already queued
python -m tools.cli tickets list --lane new-theory  # specced, unbuilt
```

**A dead idea is not a free slot.** The registry records what was tried
and why it died, and re-proposing it wastes a session that will rediscover
the same wall. But read the `revisit_angle` — a falsified idea often
leaves a live successor that nobody built, and *that* is a finding you can
file today. `calendar-arb` is the standing example: its arbitrage premise
is dead, its soft-relative-value successor is unbuilt and specified.

## 2. Where to look

**The board is a source, and the cheapest one.** You have ~100k live
markets in `get_board(conn)` (no force — that is the floor's). Group them
by series and ask what no theory covers: which recurring series have
years of base rates nobody has measured, which families have structure
(ladders, mutually-exclusive sets, date nestings) nothing scans, where
Kalshi and Polymarket list the same question.

**Then read outside.** Use web search, and search deliberately:

- **The academic literature on prediction markets and forecasting** —
  favorite-longshot bias, longshot pricing on low-probability contracts,
  calendar and deadline effects, post-news drift, market maker inventory
  effects. Much of it was measured on sports books or Intrade and has
  never been tested on Kalshi's contract set.
- **Sports betting market microstructure**, which is the best-studied
  binary-outcome market that exists, and which shares most of Kalshi's
  mechanics.
- **How specific resolution sources behave** — which agencies revise,
  which publish late, which have a scheduled release nobody trades
  against, which have a definition that diverges from the market's title.
- **What is structurally new on Kalshi** — new series, new contract
  types, rule changes. A market family that launched last month has no
  informed order flow yet.

Record the source on every idea you file. A hypothesis whose provenance
is "somebody said so" cannot be evaluated later.

## 3. The bar every idea must clear before you file it

Volume is the goal; slop is not. An idea is worth filing only when you
can write all four:

1. **A mechanism.** *Why* does this mispricing exist and persist — who is
   on the other side, and why do they keep being wrong? "Retail buys YES
   because hope is directional" is a mechanism. "Prices look off" is not.
   An idea with no mechanism is curve-fitting waiting to happen.
2. **A Kalshi population.** Which markets, concretely, and roughly how
   many. **Every bet must resolve to a Kalshi ticker**, so a thesis with
   no Kalshi contracts behind it is not actionable here however true it
   is.
3. **A test that could fail.** What measurement would kill it. If you
   cannot say what would disprove it, it is a story.
4. **Which kind it is** — mechanical (a threshold, an arithmetic
   relation, a base rate: tier A, replays over all history, scales for
   free) or interpretive (a claim about the world that no field could
   express: judgment, prompts on disk, tier B). Say which and why, since
   it decides almost everything downstream.

Fail any of the four and either sharpen it until it passes or drop it.
Dropping is fine; filing a vague one is not, because the cost lands on
somebody else.

## 4. File what survives

Both, every time:

```bash
python -m tools.cli tickets new --lane new-theory --slug <slug> \
    --title "<the thesis in one line>" --session <you> \
    --body "<mechanism; Kalshi population; what would kill it; mechanical
             or interpretive; source>"
python -m tools.cli ideas record <slug> "<title>" \
    --description "<the same, in the registry>" --source claude
```

The ticket is the work; the registry entry is the memory that
deduplicates across theories and survives the ticket being closed.

**If it is a subset of an existing theory** — the same screen and
population, re-weighted — it is a **sub-theory**, not a new one: file it
`--lane theory --theory <slug>` so it lands in that theory's own folder
where its expert will see it.

## 5. Keep going

Work the sources in §2 in order and do not stop at the first good one.
Sessions in this lane are cheap and the output compounds: every idea you
file is a session somebody else does not spend staring at a blank page.

Stop when the sources are genuinely worked, not when you have "enough" —
and say in your report which sources you covered and which you did not,
so the next session in this lane starts where you left off rather than
re-reading the same three papers.

## 6. Finish

```bash
python -m tools.cli lane release <claim id> --summary "<n ideas filed>"
```

Report: how many ideas you filed and what they are, in one line each with
their mechanism; what you rejected and why (that is as useful as what you
kept — it stops the next session re-finding it); which sources you
covered; and anything for the user's ruling. Append Did / Learned / Next
to `RESEARCH_LOG.md`.

**Name your best one and say why.** A list of fifteen with no ranking
gets triaged by whoever reads it, which is work you were better placed to
do.
