# insider_bias — a theory family, not a theory

There is no theory called `insider_bias`. This folder is the **shared
parent** of two sibling theories that screen the same board:

- `insider_judgment/` — "is there a specific identifiable group who already
  knows?", decided by LLM judgment.
- `mention_family/` — "this ticker-pattern family, priced by its own
  measured historical win rate, beats its own price", decided by code.

The name is historical: `insider_bias` was one theory until 2026-08-24,
when `mention_family` split out of it and both turned out to need the same
underlying favorite screen. Each sibling's `THEORY.md` carries its own
hypothesis, status, and version; this folder carries only what they share.

## What lives here

| Module | What it is | Who uses it |
|---|---|---|
| `screen.py` | the stage-1 favorite screen (price band, spread, volume, days-to-close) | both siblings |
| `replay.py` | tier A point-in-time replay of `screen.py` over settled markets | both siblings' backtests |
| `families.py` | `is_mention_family`, the ticker-family classifier | `mention_family` to select its population, `insider_judgment` to define the complement |
| `backfill_history.py` | one-off durable-cache backfill over both populations | operator |

## The rule for adding to this folder

Something belongs here when **both siblings actually depend on it** — not
when it looks reusable. Until then it lives in the theory that needs it
(`tools/README.md`'s promotion rule, applied at family scope).

Two constraints decide where shared code goes, and they point in different
directions, so check both:

1. **A theory folder never imports a sibling theory's folder.** Shared
   ancestry comes through this package or through `tools/`. Enforced by
   `tests/test_conventions.py::test_no_theory_imports_a_sibling_theory`.
2. **A replay never goes to `tools/`.** There is no shared backtest engine
   in this repo (CLAUDE.md, "What lives in a theory, and what gets
   elevated"). `replay.py` is here rather than in `tools/` for exactly that
   reason: it is shared by a *family*, not by the platform.

So the test is: does a theory with a *different thesis* inherit this? If
yes, it may be a `tools/` candidate. If it only makes sense to theories
replaying *this* screen, it belongs here.

`families.py` is the worked example of a third constraint — history. Its
classifier once lived in `screen.py`, and the 2026-08-24 split deliberately
removed it, with
`tests/theories/test_insider_bias_screen.py::test_does_not_carry_is_mention_family`
guarding its absence. When it later became genuinely shared again, it came
back to the parent as its **own module** rather than back into the screen:
shared ancestry without undoing a decision someone made on purpose.

## What does not live here

Per-theory code, prompts, `RUNBOOK.md`, `NOTES.md`, and `THEORY.md` stay in
the sibling folders. Tests live in `tests/theories/`. Measured results live
in the database. This folder holds no `THEORY.md` of its own, and nothing
here records opportunities — only the siblings produce bets.
