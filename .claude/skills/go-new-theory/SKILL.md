---
name: go-new-theory
description: Take a new hypothesis from idea to a running theory — check it has not been tried, formalize it, build it, and get it recording. Invoked by go when the new-theory lane is claimed.
---

# go-new-theory — get a new thesis running

Invoked by `go` once you hold the new-theory lane. **One thesis, this
whole session.** The goal is a theory that *runs* and records, not a
design document: a specced idea nobody built is worth nothing, and this
repo has more of those than it has theories.

## 1. Check it has not been tried

```bash
python -m tools.cli ideas search "<keyword>"
python -m tools.cli ideas revisitable
python -m tools.cli tickets list --lane new-theory
```

**Search before proposing, every time.** The registry exists to
deduplicate across theories, and a dead idea's `revisit_angle` is often a
better brief than a fresh idea — `calendar-arb`'s hard-arbitrage premise
was falsified outright, and its revisit angle is a fully specified
successor nobody has built.

Also check `docs/superpowers/specs/theories/`: far more theses are
specced than built, and a spec with a ticket against it is the strongest
signal in this lane.

## 2. Decide what kind of thesis it is

This decides almost everything downstream, so decide it explicitly.

**Mechanical** — the thesis is a threshold, an arithmetic relation, a
base rate, a structural fact. No model anywhere in the decision path.
Records `edge_basis='model'`, backtests at tier A over all reachable
history, costs nothing per candidate, scales to the whole board.
**Prefer this whenever the question can be settled by statistics.**

**Interpretive** — the thesis is a claim about the world that no
published field could express: somebody already knows, an outcome is
decided before it is official, a resolution source behaves in a way only
reading the situation reveals. Needs judgment, records provenance, has
prompts on disk, backtests at tier B.

Both are first-class. What is never acceptable is spending judgment on a
*structural* question — how many winners a market pays, whether strikes
are mutually exclusive, which family a ticker is in. Those are data, then
code, then a structural gate, then outcome judgment, in that order.

## 3. Formalize, then build

Invoke `propose-theory` — it carries the registry discipline and the
folder contract. What must exist before the theory is real:

- `THEORY.md` — the claim, the procedure, the status, the pre-registered
  bar it must clear and what would kill it
- `RUNBOOK.md` — Stages / Run / Record / **Sub-theories** / Report / Skip
  (conventions-tested; the Sub-theories section says "none registered"
  when there are none, which is a checked fact rather than an omission)
- `NOTES.md` — dated from the first session
- the code: `screen()` and `price()` at minimum, plus whatever else the
  thesis needs. Nothing imports a sibling theory's folder; shared
  ancestry goes through a shared parent module or `tools/`.
- `prompts/` on disk, if anything judges

**Write down the kill criterion before you have results.** A theory
without a pre-registered bar cannot fail, which means it cannot be
trusted when it passes.

## 4. Get it recording, and get it evidence

A theory that has never run is `proposed`; one that runs is `testing`.
Run it against the session's board (`get_board(conn)` — no force, that is
the floor's) and record what it produces, including rejections.

Then **back it up with evidence in the same session if you can**. A
mechanical theory replays over all reachable history and re-runs for
free; that is the difference between a theory that is bettable this week
and one that spends two months accruing settlement days. `backtest-theory`
has the tiers and the traps.

## 5. Stay in the lane

**Do not pivot.** A second thesis that occurs to you is a *ticket*:

```bash
python -m tools.cli tickets new --lane new-theory --slug <slug> \
    --title "<one line>" --body "<the thesis and why it might work>" \
    --session <you>
```

Record the idea in the registry too (`ideas record`) — the ticket is the
work, the registry entry is the memory that stops someone re-proposing it
in three weeks.

Same single exception as every focused lane: a maintenance problem that
makes progress *truly impossible*. Ticket it, say so, fix it.

## 6. Finish

```bash
python -m tools.cli lane release <claim id> --summary "<what you built>"
```

Report what the thesis is, what kind it is and why, what exists now,
whether it ran, and what evidence it has. Append Did / Learned / Next to
`RESEARCH_LOG.md`.

**An unfinished theory needs a ticket saying exactly where it stands** —
half a theory nobody can find is worse than none, because the next
session will start over.
