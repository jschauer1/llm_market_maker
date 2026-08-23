---
name: backtest-theory
description: Replay a theory against historical markets without lookahead bias, assigning a contamination tier. Use when a theory needs evidence, or the user asks how a strategy would have performed.
---

# Backtest a Theory

## 1. Determine the tier — derived, never self-reported

Two facts decide it:

1. Does the theory's decision path invoke LLM judgment? Read its `THEORY.md`.
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

## 2. Enforce the rules

- **Web search must be off** in any backtest judgment subagent, every tier.
  Live search reveals historical outcomes trivially.
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
