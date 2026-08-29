---
name: backtest-theory
description: Replay a theory against historical markets without lookahead bias, assigning a contamination tier. Use when a theory needs evidence, or the user asks how a strategy would have performed.
---

# Backtest a Theory

## 1. Determine the tier — derived, never self-reported

Three facts decide it:

1. Does the theory's decision path invoke LLM judgment? Check
   `theory.uses_llm_judgment` — a `ClassVar`, drift-checked against the DB
   by `registry.check_drift`, so it cannot silently disagree with the
   registry row. `THEORY.md` explains *why*; the class is the fact.
2. If it does, is **every** judging stage a *structural gate* — a stage
   whose answer cannot be influenced by the outcome? Test it against
   CLAUDE.md's four conditions ("Structural gates keep tier A"), not
   against the prompt's self-description. The decisive one is the
   contamination probe: given only what the prompt shows, can the model
   state the outcome? If it can, the stage is outcome judgment.
3. Did the markets resolve before or after the judging model's knowledge
   cutoff?

| Tier | Condition | Trust |
|---|---|---|
| **A** | No LLM, **or** every model stage is a structural gate | Full evidence, all history |
| **B** | Outcome judgment, markets resolved *after* the cutoff, web search off | Valid, small sample |
| **C** | Outcome judgment, markets resolved *before* the cutoff | Contaminated — indicative only |

**Structural is a finding, not a claim.** "Derived, never self-reported"
binds hardest here, because it is now the one label a theory could award
itself. Run the probe, record its result in the `judgment_runs` row's
`notes`, and treat an unrun probe as outcome judgment. A stage that
assigns any bucket, side, or probability is outcome judgment whatever its
prompt is titled — buckets come only from a deep stage.

A tier A backtest of a judgment theory's *screen alone* is often the best
available evidence: uncontaminated, and it measures whether the filter selects
markets that beat their price.

**Only outcome stages contribute a cutoff.** A structural gate cannot
leak the future, so it does not drag a cascade's cutoff earlier — a theory
whose gate is structural and whose deep stage judges outcomes takes the
deep stage's cutoff alone. A theory with *no* outcome stage has no cutoff
to honour at all, which is what tier A means.

**A cascade with two outcome stages has two cutoffs, not one.** If the theory runs a cheap gate ahead
of deep analysis, those are two different models with two different knowledge
cutoffs. Tier B validity requires the markets to resolve after the **later**
of the two — a cheap gate with an earlier cutoff still contaminates the run
even when the deep model's cutoff is clean, because the gate's judgment was
also part of the decision path. Record the later of the two cutoffs as
`model_cutoff` and derive the tier from that single, later date.

## 2. Enforce the rules

- **The replay code lives with the theory**, as `backtest.py` in its
  folder by convention — `theories/insider_bias/mention_family/backtest.py`
  is the worked example. When sibling theories replay the *same* screen,
  the shared half moves up to their shared parent, never to `tools/`:
  `theories/insider_bias/replay.py` is that case. The harness gives you
  point-in-time data, run identity, tiers and scoring; reconstructing a
  theory's decision at a past moment is thesis-specific and stays on the
  theory side. **Never write or extend a shared replay engine**
  (`tools/backtest.py`), and never add a `backtest()` method to the
  `Theory` contract. A backtest is a driver script that builds a
  backtest-mode context and calls the same `screen()` and `price()` the
  live path calls — replaying a reimplementation of the screen is a
  backtest of nothing.
- **`TheoryContext(run_mode="backtest")` is what a replay keys on.** Build
  the context with `run_mode="backtest"` and a real `run_id` (not `"live"`)
  — `TheoryContext.build(..., run_mode="backtest", run_id=...)` — and it
  propagates everywhere that matters: `finish()` stamps every row it writes
  with `ctx.run_mode` and `ctx.run_id` automatically, so replayed rows stay
  separable from live ones with no per-candidate bookkeeping.
- **`ctx.now` must be the day being replayed, not the day you are running
  on** — so a walk over sixty days builds a context per replayed day (or
  rebuilds one with a new `now`), never one context for the whole walk.
  `ctx.now` is the harness's as-of time and it is what dates the attempt:
  `OpportunityRecord.from_scored` passes `decision_date=ctx.now.date()`,
  and an attempt is keyed `(opportunity_id, decision_date, run_id)`. One
  context for the whole walk stamps all sixty decisions with today's date
  under one `run_id`, the key collapses them, and **fifty-nine attempts are
  overwritten in silence** — the position ends up looking like a single
  proposal at whichever price was written last. Nothing catches this:
  `record_opportunity` refuses a backtest with a *missing* `decision_date`,
  and cannot know a present one is wrong. Setting `ctx.now` correctly also
  keeps `point_in_time` and the attempt agreeing on which moment is being
  replayed, which is what makes a per-day price series reconstructable
  afterwards.
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

The same rule governs **judgment stages, because usage can cut out at
any moment**: write every batch's input payload to disk before any model
runs, have each judgment subagent write its verdicts to a file itself,
and ingest + record each batch before dispatching the next — never hold
verdicts only in conversation context. However far the run got must be
scoreable by a future session that never saw this one.
`theories/insider_bias/insider_judgment/backtest_judged.py` is the
worked example.

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
