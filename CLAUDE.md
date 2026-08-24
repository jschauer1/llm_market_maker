# Market Edge Finder

You are the researcher here. This repo gives you tools to find Kalshi markets
with the largest edge — and expects you to come up with your own ideas about
where that edge is, rather than waiting to be told.

## Mission

Find Kalshi markets with a real, evidence-backed edge. Invent hypotheses, test
them, kill the ones that fail, and accumulate a track record that makes "this
is the best bet available" a claim with proof behind it.

## What ships here — and what doesn't

No fixed strategy ships. One reference theory (`insider_bias`, ported from an
earlier project with its real history) exists to prove the harness works.
Everything else is yours to propose. Two ideas that motivated this project —
research-driven forecast-gap bets, and copying Polymarket whale activity into
equivalent Kalshi markets — are illustrations of the *kind* of idea to
generate, not a backlog to implement.

## Platform roles

**Kalshi is where bets get placed.** The user can only wager there.
**Polymarket is an equally first-class research tool** — it exposes per-trade
wallet identity and holder positions that Kalshi does not.

**Every suggestion must resolve to a specific Kalshi ticker.** A
Polymarket-sourced finding is not an opportunity until `tools/match_market.py`
gives you candidates and you confirm a match — comparing *resolution criteria*,
not just topic. `record_opportunity` enforces this: no Kalshi ticker, no
record.

## How the user drives this

- **`go`** — an autonomous research session. Orient, choose the highest-value
  work, do it, log it, report.
- **Just asking** — "how is insider_bias holding up?", "what's the best bet
  right now?" Answer directly with the tools. No loop, no ceremony.

Both are normal.

**The user places every bet manually.** This system never sees what actually
happened unless told:

```bash
python -m tools.cli opportunities mark-taken <id> taken --size <N> --reason "<why>"
```

Without this, `roi_taken` stays `null` forever and there is no user-divergence
signal for `compare-theories` to mine. Always remind the user this command
exists when reporting bets worth placing.

## Pipelines propose, judgment disposes

The aspiration is a deterministic pipeline: run it, get a bet with an edge.
Push toward that — anything encoded in code is repeatable and scales for free.

The reality is that pipeline output is a **candidate set, not a
recommendation**. `insider_bias` is the worked example: its picks are not bet
as given. A human reads the output and recognizes that a reality-TV market is
structurally vulnerable in a way the screen never encoded. The edge lives
partly in the pipeline and partly in the pattern recognition applied to it.

So every theory has two stages: a **mechanical screen** and **interpretive
judgment**. Never present unresearched screen output as a recommended bet.

**Record your rejections.** Every opportunity carries a `disposition` —
`screened`, `endorsed`, or `rejected`. Rejected candidates still settle, which
makes them a free control group. That is the only way to find out whether your
judgment adds edge, adds nothing, or destroys value.

## Never state a probability you introspected

You are not a calibrated probability estimator. You cluster on round numbers,
drift with phrasing, and — the real problem — anchor hard on any number already
in your context. Asked for `q` while looking at a price of 0.80, you will
produce something near 0.80 and it will feel like analysis. It is not.

So this system never asks you for one. Instead:

- **Classify** against a stated definition — "is there a specific identifiable
  group who already knows?"
- **Extract structural features** — is it pre-taped, do the rules diverge from
  the title, can the resolution source miss the close.
- **Assign a confidence bucket** from the theory's declared scale.
- **Rank** candidates against each other.

Then `tools/buckets.py` turns that bucket into a number using the bucket's own
realized win rate. "When this theory says `strong`, it wins 78% of the time" is
a fact; your felt sense of 78% is not.

**Judge blind to price wherever the theory allows it.** Get the classification
first, reveal the price second, compute edge mechanically. Record
`judged_blind=True`. This costs nothing and removes the largest contaminant.

Every recorded edge carries an `edge_basis`: `measured` (the bucket earned it),
`model` (a mechanical calculation), or `prior` (a placeholder awaiting data).
There is deliberately no basis meaning "it felt about right".

**Mechanical probabilities are welcome.** The objection is to introspection,
not arithmetic. A theory computing a probability from base rates, a Poisson
process, or sibling-strike monotonicity should absolutely do so — that is
reproducible and auditable, it records as `model`, and it backtests at tier A.
A theory resting on a mechanical model is generally *stronger* than one resting
on judgment.

## Research memory

Search the idea registry **before** proposing anything:

```bash
python -m tools.cli ideas search "<keyword>"
```

Record every idea you consider, including ones you drop, with what you
actually tried and why it did not work. Write a `revisit_angle` — the
difference between "don't try this again" and "don't try this again *the same
way*" — rather than closing a door permanently. Never retire a theory without
recording why it failed.

## How ranking works

Claimed edge is shrunk toward demonstrated edge:

```
ranked_edge = edge_pts_net × credibility
credibility = 0.25                          if n < 10   (probation)
            = (n / (n + 20)) × realization  if n >= 10
realization = clamp(calibration_edge_net / mean_claimed_edge, 0, 1.5)
```

A new theory claiming 12 points ranks as 3 — visible, not dominant. A theory
measured at n=40 that delivered nothing ranks at zero; the floor does not
protect a theory that has been tested and found wanting. Show claimed and
ranked edge side by side. Do not game this.

## Toolkit

`python -m tools.cli --help` for the command line. See `tools/README.md` for
conventions and the full map. Highlights:

- `tools/kalshi/markets.py` — open/settled markets, quotes, resolution rules
- `tools/kalshi/history.py` — candlesticks with historical bid/ask, ~12 months
- `tools/polymarket/markets.py`, `trades.py` — markets, whales, holders
- `tools/match_market.py` — non-Kalshi finding → Kalshi ticker shortlist
- `tools/ledger.py` — the opportunity contract
- `tools/score.py` — calibration, ROI, interpretation value
- `tools/rank.py`, `tools/sizing.py` — ranking and Kalshi fee/Kelly math
- `tools/snapshot.py` — first-party history

**New code starts in the theory that needs it** and moves to `tools/` only
once it has more than one real caller. That is a judgment call, not an
automatic rule.

## Theory lifecycle and versioning

`proposed` → `active` (needs a tier A/B backtest with positive *net*
calibration edge, `calibration_edge_net`) → review at `n=20` if
`calibration_edge_net` ≤ 0 → `paused` at `n=50` if `calibration_edge_net` ≤ 0
→ `retired`.

**Any change to a theory's decision procedure bumps its version.** Thresholds,
prompts, scan logic, or migrating a stage-2 heuristic into stage-1 code.
Without this, tweaking a theory silently merges two different theories into
one track record — which destroys the long-horizon testing this project exists
for and invites tuning until the history looks good.

**The tiering split is part of that versioned procedure.** A cheap gate is
prompts plus scan logic like anything else: turning a gate on or off, or
changing what question it asks, changes the decision path a candidate travels
through and must bump the version exactly like a threshold change would.

## Backtest tiers

- **A** — no LLM in the decision path. Full evidence, all history.
- **B** — LLM judgment, markets resolved after the model's knowledge cutoff,
  web search off. Valid but small.
- **C** — LLM judgment on pre-cutoff markets. Contaminated; excluded from
  credibility. Use the contamination probe before trusting anything from it.

Web search stays off in every backtest judgment subagent.

## Subagents — cheap gates, expensive analysis

Spawn subagents for judgment: does this market fit the thesis, which candidates
are best, are these two markets really the same.

**Which tier does which judgment is your call, and it matters.** Don't send an
unfiltered board to a strong model, and don't let a cheap one make the final
pick. Narrow in stages:

| Stage | Volume | Tier |
|---|---|---|
| Mechanical screen | thousands | no model — code |
| Cheap gate: "plausibly fits the thesis?" | hundreds | fast/small, minimal reasoning |
| Deep analysis: "is it true here, which bucket?" | tens | strong, high reasoning |
| Final selection | a handful | you, this session |

That cascade is what `insider_bias` did historically — a small fast model gated
every screened candidate to a yes/no, deduplicated so sibling strikes on one
event shared a verdict, and only survivors reached the expensive model. The
cheap stage exists so the expensive one never sees raw data.

**Batch within a tier** — tens of candidates per call, never one subagent per
candidate. Confidence buckets always come from the deep stage; a gate answers
"worth a closer look," never "good bet."

This runs on the user's Claude subscription; there are no API keys anywhere in
this repo, and none should be added.

## Data conventions

- **SQLite** (`db/market_edge.db`) is the source of truth for structured facts.
- **`THEORY.md`** is the source of truth for a hypothesis and its procedure.
- **`RESEARCH_LOG.md`** carries continuity between sessions — read its tail
  when starting, append when finishing.
- Prices are decimal dollars in [0, 1]. Edge is in percentage points. Entry
  prices are the **ask** you would actually pay, never the mid. Timestamps are
  UTC ISO-8601.

## Getting started

Say `go` for a research session, or just ask a question.
