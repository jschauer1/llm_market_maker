---
name: propose-theory
description: Formalize a new trading hypothesis into a theory folder, after checking it has not already been tried. Use when you have an idea worth testing, or the user asks for a new strategy.
---

# Propose a Theory

## 1. Check the research memory FIRST

Before any other work:

```bash
python -m tools.cli ideas search "<keyword>"
python -m tools.cli ideas search "<another keyword>"
```

Search several phrasings — the same idea wears different words.

- **Matches a `dead` idea?** Read its `outcome` and `revisit_angle`. Without a
  genuinely different angle, stop and tell the user it was tried and why it
  failed. Repeating a known dead end is the failure this registry exists to
  prevent.
- **Matches a `parked` idea?** Check `revisit_after`. If the condition is now
  met, this is high-value work — proceed and say why it is newly viable.
- **Matches a `promoted` idea?** The theory already exists. Improve it instead.

## 2. Record the idea

```bash
python -m tools.cli ideas record <slug> "<title>" \
    --description "<the hypothesis in a sentence or two>" \
    --source claude
```

Record it even if you end up dropping it — an idea investigated and abandoned
is exactly what a future session needs to know about.

## 3. Interrogate the hypothesis

- What mistake is the market making, and **why does it persist** rather than
  being arbitraged away? A thesis with no answer here is usually wrong.
- **What would falsify it?** Not what would confirm it. If you cannot state a
  result that would kill this theory, it is not testable.
- Which data sources? Does anything exist to support it?
- If the signal is not from Kalshi, how does it reach a Kalshi ticker?

## 4. Split stage 1 from stage 2

**Ask first whether this theory needs a stage 2 at all.** If the thesis can be
decided by code — a monotonicity violation, a NO-basket summing below its
payout, a base-rate regression, a cross-platform divergence on a matched pair,
a measurable structural bias in a market family — then write the script,
record `edge_basis="model"`, leave stage 2 empty, and stop. That theory is
cheaper, reproducible, scales to the whole board, and backtests at tier A, so
it can carry real evidence immediately rather than waiting out tier B's thin
post-cutoff window. Prefer it whenever the thesis allows.

Reach for LLM judgment when the thesis genuinely needs reading comprehension or
context that no threshold captures — as `insider_bias` does, since "would a
specific group already know this?" is not a number.

If you do need stage 2: push as much as possible into stage 1 — code is
repeatable and free to run at scale. Be concrete about what's left: "check
whether the resolution source publishes on a schedule that can miss the close"
is useful; "use good judgment" is not.

If stage 1 is likely to leave more candidates than deep reasoning can afford,
decide the **tiering split** now, as part of designing the theory: does stage
2 need a cheap gate ahead of deep analysis, how many candidates does each
tier see, and what single question does the gate answer? Write the split down
in `THEORY.md` — `_TEMPLATE/THEORY.md`'s stage 2 section says what to state.
A theory whose decision path is fully deterministic can skip this and say so.

## 5. Scaffold

```bash
mkdir -p theories/<slug>
cp theories/_TEMPLATE/THEORY.md theories/<slug>/THEORY.md
python -m tools.cli theories register <slug> "<Name>" theories/<slug>
python -m tools.cli ideas status <idea-slug> promoted --theory-id <slug>
```

Fill in `THEORY.md` completely. Write any stage-1 code in the theory folder,
with tests. Theory-local code stays local until it earns promotion — see
`tools/README.md`.

## 6. Start at `proposed`, move to `testing` when it runs

A theory is `proposed` while its procedure is still being written. Once the
screen actually runs end to end and starts recording opportunities, move it
to `testing`:

```bash
python -m tools.cli theories status <slug> testing
```

`testing` means the theory is on the board and accruing evidence, while its
claimed edge is not yet demonstrated. It does not become `active` until a
tier A or B backtest shows positive *net* calibration edge
(`calibration_edge_net` — gross `calibration_edge` is not the promotion bar),
or the user explicitly overrides.

Say what evidence you would need to promote it — and what result would send
it to `under_review`. A theory whose falsifying result you cannot name is not
testable.

## If you drop the idea instead

```bash
python -m tools.cli ideas status <slug> dead \
    --what-was-tried "<what you actually did>" \
    --outcome "<why it does not work>" \
    --revisit-angle "<what a different approach would look like, or omit>"
```

Omit `--revisit-angle` only if the idea is genuinely exhausted.
