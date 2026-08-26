# <Theory name>

> Delete this quote block when you fill the template in.
>
> A theory is a folder. Beyond this file, its shape is entirely yours: Python
> scripts, prompts, notebooks, fixture data — whatever the hypothesis needs.
> There is no required function, no pipeline to conform to, no base class.
>
> `insider_bias` happens to be a filter-then-judge theory. That is one shape,
> not the shape — it needs judgment only because its thesis ("does a specific
> group already know?") cannot be written as a threshold.
>
> **A theory can be pure code, and that is often the better theory.** If you
> can find edge statistically, do that. Real examples, all decidable with no
> model in the loop:
>
> - sibling-strike monotonicity violations (">40" priced below ">50")
> - a NO-basket on a mutually exclusive event summing below its payout
> - a recurring series with years of base rates to regress against
> - a persistent Kalshi-vs-Polymarket divergence on a confirmed-matched pair
> - systematic longshot or favorite bias in a specific market family
>
> A mechanical theory records `edge_basis="model"`, leaves stage 2 empty,
> costs nothing per candidate, scales to the whole board, and backtests at
> **tier A** — so it can carry real evidence immediately instead of waiting
> out tier B's thin post-cutoff window. LLM judgment is one instrument, and
> the most expensive and least verifiable one. Reach for it when the thesis
> genuinely needs reading comprehension or context, not by default.
>
> Write whatever code the idea needs — a scraper, a regression, an order-book
> walker, a scheduler. The folder is yours.
>
> The one thing every theory must do is call `record_opportunity` with a
> tradeable Kalshi ticker and a net edge in percentage points. That single
> contract is what makes theories comparable to each other — and what lets the
> session running this repo ask "what is the best bet right now?" across all
> of them at once.

## Hypothesis

What is the thesis? What mistake is the market making, and why does it
persist rather than getting arbitraged away?

## Data sources

Which platforms and tools does this use?

## Status

`proposed` — with a journal of status changes and the reason for each.

Status is an evidence level: `proposed` (unproven, not running) → `testing`
(running, accruing evidence) → `active` (demonstrated positive net calibration
edge). A theory failing its own bar goes `under_review` and **keeps running**
while it is diagnosed; `paused` is for one blocked on a missing prerequisite,
not a failing one. `retired` is the user's call alone — record a diagnosis
with `theories propose-retirement` and let them rule.

## Version

1 — changelog of what changed at each bump. Any change to the decision
procedure bumps this, including migrating a stage-2 heuristic into stage 1.
The tiering split counts too: turning a cheap gate on or off, or changing the
question it asks, changes the decision path and bumps the version just like a
threshold change would.

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

**Every judging prompt lives in `prompts/` in this folder, and every run
records which model read it.** A prompt that exists only inside a tool call is
part of the decision procedure that nobody wrote down, and an edge produced by
a procedure nobody wrote down cannot be reproduced — which is most of what an
edge is worth. Declare `theories.set_uses_llm_judgment(conn, slug, True)` and
`record_opportunity` will refuse to write rows for a run with no provenance.
List the prompt files here, one per judging stage.

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
  model's knowledge cutoff, web search off. If stage 2 runs a cheap gate ahead
  of deep analysis, that is two models with two cutoffs — use the **later** of
  the two to decide the tier, since the earlier-cutoff model's judgment was
  still part of the decision path.
- **Tier C** — LLM judgment on pre-cutoff markets. Contaminated; indicative
  only, and excluded from credibility.

**The replay lives in this folder**, as `backtest.py` by convention — or,
if this theory shares a screen with a sibling and the replay is shared with
it, in their shared parent package rather than in either folder (see
`theories/insider_bias/replay.py`). Never in `tools/`. The
harness supplies point-in-time data (`tools/kalshi/history.py`,
`tools/snapshot.py`), run bookkeeping (`run_mode="backtest"` plus a real
`run_id`, and the `backtest_runs` table), and scoring — and nothing else.
Reconstructing *this* theory's decision at a past moment, over whatever
slice of history is actually fetchable, accepting whatever approximations
that forces, is thesis-specific work that belongs here. Two rules make the
result mean something: call the same functions the live path calls (a
backtest of a reimplemented screen is a backtest of nothing), and state the
reconstruction's known biases in this section, because a replay whose
biases are not written down produces a number nobody can caveat.

## Learnings

The **distilled** record: what this theory now knows that changes what it
claims or how it runs. Not a journal — raw working notes (dead ends, data
quirks, backtest narratives, hunches not yet worth a version bump) go in
`NOTES.md` in this folder, and graduate into this section only when they
change the theory's claims, procedure, or status. Summarize and point at
the `NOTES.md` entry; do not copy it.
