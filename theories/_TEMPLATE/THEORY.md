# <Theory name>

> Delete this quote block when you fill the template in.
>
> A theory is a folder. Beyond this file, its shape is entirely yours: Python
> scripts, prompts, notebooks, fixture data — whatever the hypothesis needs.
> There is no required function, no pipeline to conform to, no base class.
>
> `insider_bias` happens to be a filter-then-judge theory. That is one shape,
> not the shape. A structural arbitrage theory might be pure deterministic
> math with an empty stage 2. A whale-following theory might be almost
> entirely judgment across two platforms. Build what the idea needs.
>
> The one thing every theory must do is call `record_opportunity` with a
> tradeable Kalshi ticker and a net edge in percentage points. That single
> contract is what makes theories comparable to each other.

## Hypothesis

What is the thesis? What mistake is the market making, and why does it
persist rather than getting arbitraged away?

## Data sources

Which platforms and tools does this use?

## Status

`proposed` — with a journal of status changes and the reason for each.

## Version

1 — changelog of what changed at each bump. Any change to the decision
procedure bumps this, including migrating a stage-2 heuristic into stage 1.

## Stage 1 — mechanical screen

What can be encoded deterministically: which tools to call, what filters and
thresholds, how candidates are produced. Push as much here as possible —
anything in code is repeatable, testable, and free to run over thousands of
markets.

If the signal originates outside Kalshi, this must include the
`tools/match_market.py` step that resolves it to a Kalshi ticker.
`record_opportunity` has no Kalshi-less path.

## Stage 2 — what needs judgment

What cannot be encoded, and what Claude should look for when reading this
theory's output. Market types that are structurally soft or dangerous,
resolution-language traps, context worth researching before endorsing.

Be concrete. "Use good judgment" helps nobody; "check whether the resolution
source publishes on a schedule that can miss the close" is a real instruction.

**Say which model tier does what.** If stage 1 leaves more candidates than deep
reasoning can afford, split stage 2 into a cheap gate and a deep analysis, and
write down the split — how many candidates each tier sees, and the single
question the gate answers. A gate decides "worth a closer look"; only the deep
stage assigns a confidence bucket. A theory that needs no gate should say so;
one whose decision path is fully deterministic can leave this section empty and
is stronger for it (it backtests at tier A).

**Ask for classifications and a confidence bucket, never a probability.** An
LLM-introspected number is mostly an anchor on whatever price was in context.
State here whether judgment runs blind to price — it should, wherever the
theory allows.

Anything here that keeps proving itself should eventually migrate into
stage 1 as code.

## Confidence buckets

The ordinal scale this theory's judgment step uses, with a conservative prior
edge in points for each. Priors apply only until a bucket has 10+ settled
results; after that its own realized win rate replaces them. Treat the priors
as placeholders — the point of the mechanism is that measurement overrides
them, including measuring that a bucket is worth nothing.

| bucket | meaning | prior edge (pts) |
|---|---|---|
| `strong` | | |
| `moderate` | | |
| `weak` | | 0.0 |

A theory whose edge comes from a mechanical model rather than judgment can
skip this section — record `edge_basis="model"` instead.

## How to backtest

A procedure using the point-in-time tools. State plainly whether the decision
path uses LLM judgment, because that determines the tier:

- **Tier A** — no LLM in the decision path. Backtest over all history.
- **Tier B** — LLM judgment, restricted to markets that resolved after the
  model's knowledge cutoff, web search off.
- **Tier C** — LLM judgment on pre-cutoff markets. Contaminated; indicative
  only, and excluded from credibility.

## Learnings

Running journal — what worked, what did not, what surprised you.
