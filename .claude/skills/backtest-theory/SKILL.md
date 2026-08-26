---
name: backtest-theory
description: Replay a theory against historical markets without lookahead bias, assigning a contamination tier. Use when a theory needs evidence, or the user asks how a strategy would have performed.
---

# Backtest a Theory

## 1. Determine the tier — derived, never self-reported

Two facts decide it:

1. Does the theory's decision path invoke LLM judgment? Check
   `theory.uses_llm_judgment` — a `ClassVar`, drift-checked against the DB
   by `registry.check_drift`, so it cannot silently disagree with the
   registry row. `THEORY.md` explains *why*; the class is the fact.
2. Did the markets resolve before or after the judging model's knowledge
   cutoff?

| Tier | Condition | Trust |
|---|---|---|
| **A** | No LLM in the decision path | Full evidence, all history |
| **B** | LLM judgment, markets resolved *after* the cutoff, web search off | Valid, small sample |
| **C** | LLM judgment, markets resolved *before* the cutoff | Contaminated — indicative only |

A tier A backtest of a judgment theory's *screen alone* is often the best
available evidence: uncontaminated, and it measures whether the filter selects
markets that beat their price.

**A cascade has two cutoffs, not one.** If the theory runs a cheap gate ahead
of deep analysis, those are two different models with two different knowledge
cutoffs. Tier B validity requires the markets to resolve after the **later**
of the two — a cheap gate with an earlier cutoff still contaminates the run
even when the deep model's cutoff is clean, because the gate's judgment was
also part of the decision path. Record the later of the two cutoffs as
`model_cutoff` and derive the tier from that single, later date.

## 2. Enforce the rules

- **The replay code lives in the theory's folder**, as `backtest.py` by
  convention — `theories/insider_bias/insider_judgment/backtest.py` is the
  worked example. The harness gives you point-in-time data, run identity,
  tiers and scoring; reconstructing *this* theory's decision at a past
  moment is thesis-specific and stays local. **Never write or extend a
  shared replay engine** (`tools/backtest.py`), and never add a
  `backtest()` method to the `Theory` contract. A backtest is a driver
  script that builds a backtest-mode context and calls the same `screen()`
  and `price()` the live path calls — replaying a reimplementation of the
  screen is a backtest of nothing.
- **`TheoryContext(run_mode="backtest")` is what a replay keys on.** Build
  the context once with `run_mode="backtest"` and a real `run_id` (not
  `"live"`) — `TheoryContext.build(..., run_mode="backtest", run_id=...)` —
  and it propagates everywhere that matters: `finish()` stamps every row it
  writes with `ctx.run_mode` and `ctx.run_id` automatically, so replayed
  rows stay separable from live ones with no per-candidate bookkeeping.
- **Web search must be off** in any backtest judgment subagent, every tier.
  Live search reveals historical outcomes trivially. This is no longer only
  a discipline: `run_mode="backtest"` makes `finish()` record
  `web_search=False` for every judging stage by construction — a live run
  records `None` (unknown) instead, because only a live run could honestly
  have used it.
- Use `tools/kalshi/history.py` `point_in_time` for market state. It never
  returns a candle after your `as_of_ts` — that property is the basis of a
  lookahead-free replay.
- Price entries at the **historical ask** (`yes_ask_close`), not the mid.

## 3. Contamination probe (tier C only)

Before trusting any tier C result, per market: ask a subagent to state the
outcome given only the market question, with no price data. If it knows,
discard that market. This turns an unfalsifiable worry into a measurement and
can rescue genuinely obscure markets.

## 4. Run it

Record every replayed decision with `run_mode="backtest"` and a real `run_id`
(a uuid, not `"live"`), so dedup is per-run and results stay separable from
live. Record rejections as well as endorsements.

**Record while you collect — never batch an entire walk into one write at
the end.** A replay that fetches for more than a minute writes each finished
unit (a series, a page, a batch of markets) to the ledger or a resumable
checkpoint file before starting the next, and on restart skips what is
already recorded. An interruption then costs seconds, not the run — and
with Kalshi archiving settled markets out of its public API ~60 days after
close, rows lost to a crash may not exist upstream anymore when you re-run.
See the convention in `tools/README.md`; `theories/insider_bias/
mention_family/backtest.py` is the worked example (per-series recording
plus a `--checkpoint` file).

**Backtests are the highest-volume judgment in this system** — a replay can
span hundreds of historical markets, far more than a single live scan. Use the
same cascade the theory uses live (cheap gate, then deep analysis on
survivors), batched tens per call, and apply the theory's own tiering if its
`THEORY.md` names one. Replaying a year of markets through a strong model
one-at-a-time is the most expensive possible way to get this number. Using a
cheap tier at the gate stage is assumed to cost little in fidelity, but that
is an assumption, not a measurement, in a system whose whole thesis is that
such claims get measured — gate/deep agreement is itself checkable (run both
on an overlapping sample and compare verdicts), so do that before leaning on
the assumption for a result that matters.

Record a `backtest_runs` row with the tier, `uses_llm_judgment`, and the
`model_cutoff` you used:

```bash
python -m tools.cli backtest record <run_id> <theory_id> <theory_version> \
    --tier A --model-cutoff <date> [--uses-llm-judgment] --notes "<notes>"
```

## 5. Score and caveat

```bash
python -m tools.cli score report <theory_id> --run-mode backtest --run-id <run_id>
```

**Always pass `--run-id`.** Without it, re-running the same backtest over the
same markets pools into every prior run of this theory version and multiplies
`n` without adding a single real bet — and `n` feeds credibility directly.

Report the tier alongside every number. Tier C results are **excluded from
credibility** — never present them as evidence of edge, only as a sanity check
on the screening stage.

Backtest **results** live in the database: rows tagged
`run_mode="backtest"` plus the `backtest_runs` row. Backtest **narrative**
— what you tried, what broke, why the window is the window, which
approximations the reconstruction accepts and in which direction they bias
— goes in that theory's `NOTES.md`, and reaches `THEORY.md` only if the
result changes what the theory claims. The biases belong in `THEORY.md`'s
"How to backtest" section too, since they are part of the procedure.
