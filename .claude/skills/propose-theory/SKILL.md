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

Explicitly decide what is mechanical and what needs judgment. Push as much as
possible into stage 1 — code is repeatable and free to run at scale. Be
concrete about stage 2: "check whether the resolution source publishes on a
schedule that can miss the close" is useful; "use good judgment" is not.

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

## 6. Stay at `proposed`

A new theory does not become `active` until a tier A or B backtest shows
positive *net* calibration edge (`calibration_edge_net` — gross
`calibration_edge` is not the promotion bar), or the user explicitly
overrides. Say what evidence you would need to promote it.

## If you drop the idea instead

```bash
python -m tools.cli ideas status <slug> dead \
    --what-was-tried "<what you actually did>" \
    --outcome "<why it does not work>" \
    --revisit-angle "<what a different approach would look like, or omit>"
```

Omit `--revisit-angle` only if the idea is genuinely exhausted.
