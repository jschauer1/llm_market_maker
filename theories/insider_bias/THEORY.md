# Insider Bias

## Hypothesis

Some Kalshi markets resolve on facts a specific, identifiable group of humans
already knows while the public does not — pre-taped reality TV, award votes
already cast, executive hires the board has already made, appointments
reporters already have sourced. When that private knowledge is real, the
public price still leaves room, and buying the favorite captures the gap.

Why it persists: the crowd cannot verify the private information, so it prices
on public uncertainty. The edge is not a smarter forecast — it is recognizing
which markets have an informed minority at all.

Ported from `kalshi_trader`, where it ran from May to July 2026. That
predecessor track record was deleted at the v2 bump — see Status.

## Data sources

Kalshi only (`tools/kalshi/markets.py`). No Polymarket dependency.

## Status

`testing` — moved from `under_review` on 2026-08-24, by Claude
(`authorized_by=claude`; only `retired` requires the user), because the
specific concern that put it there has real evidence behind it now. Track
record was reset to zero at v2 (2026-08-23), by the user's decision, because
the decision procedure changed (see Version below).

**Read `testing` narrowly: it is backed by stage-1-alone evidence, not
evidence about this theory's actual claim.** The 2026-08-24 backtest below is
tier A and real, but it measures the mechanical screen in isolation — it says
nothing about whether stage 2/3 judgment (the part that actually embodies the
insider thesis) adds value, destroys it, or is irrelevant. That question is
still **n=0**. Do not read a future positive stage-1 number as evidence the
full theory works; read it as evidence the floor stage 2/3 stands on is not
broken.

The v1 history — 96 imported `kalshi_trader` opportunities, 28 settlements,
n=29 settled at `calibration_edge_net = -0.75` — was **deleted**, not
carried forward. That was the right call: those rows were produced by a
different procedure (OpenAI classify/pick, no main-model sign-off, no
recorded decider), and scoring them alongside v2 rows would merge two
different theories into one track record. A backup of the deleted rows exists
outside the repo, and `migrate_kalshi_trader.py` can regenerate them if a
v1-specific question ever needs answering.

**2026-08-24 — item 1 of the "what would settle it" list below is now done.**
A tier A backtest of the stage-1 screen alone (`theories/insider_bias/
backtest.py`, `run_id=backtest-2026-08-24-stage1-90d`) replayed `screen.py`
— unchanged since v1 — against real point-in-time candlesticks over the last
90 days: 200 real screen hits, `calibration_edge_net = +1.38pts` overall.
That answers the exact question that kept this `under_review`: the v1
diagnosis was about the screen, and the screen, alone, does not have a
negative edge. See Learnings for the full breakdown — the headline number
undersells it. This does **not** mean `active`: it tests stage 1 in
isolation, and the theory's actual claim (does stage 2/3 judgment add value
over the screen) still has **n=0** on the live side — the 44 v2 rows settle
Aug 24–Sep 5. `testing` reflects exactly that: real accruing evidence, the
central claim not yet demonstrated either way.

What's left to settle the theory as a whole, roughly in order of value:

1. ~~A tier A backtest of the stage-1 screen alone.~~ **Done 2026-08-24** —
   see above and Learnings.
2. **`interpretation_value`** once both endorsed and rejected rows have
   settled: does stage 2 add edge over its own screen, or destroy it?
3. **Fix `gate.py`'s incomplete "aggregate of many independent people"
   pattern.** The 2026-08-24 backtest found it: of 200 screen hits, 116 are
   "MENTION"/"SAY"/"ACT"-suffix series (`KXWCMENTION`, `KXTRUMPMENTION`,
   `KXFIGHTMENTION`, ...) that `gate.py`'s current regex does **not** catch
   (it only names a few specific instances like `TRUMPSAY`,
   `MAMDANIMENTION`). Unlike the family gate.py *does* catch — see next
   item — this broader mention family backtests **positive**
   (`edge_net=+5.48pts`, n=116), so the fix here is not obviously "exclude
   it"; it needs its own judgment pass to find out whether it is a genuine
   thesis case or a distinct, still-profitable phenomenon (a public figure's
   mention rate is a base-rate bet, not obviously insider knowledge). Either
   way, gate.py's classification of it is currently just wrong — it thinks
   these are `PLAUSIBLE` when many read exactly like the aggregate-of-many
   pattern it already targets.
4. **A slice breakdown** by bucket, market family, days-to-close, and price
   band. If one family carries whatever edge exists, this is a narrower
   theory than it claims — a version bump and a real finding. The 2026-08-24
   backtest already did a first pass of this for stage 1 alone (see
   Learnings); item 2 needs the equivalent for judged bets once they settle.
5. **Gross vs net.** If `calibration_edge` is positive while the net figure is
   not, the thesis is sound and the entry threshold is wrong. Already
   answered for stage 1 alone (both are positive); still open for stage 2/3.

## Version

**2** (2026-08-23) — *Final recommendation must come from the main research
model.* Stage 2 previously ended at the subagent verdict, and a candidate was
endorsed mechanically whenever its bucket implied a positive edge. It no
longer is: subagent output is now an **initial recommendation**, and no
candidate may be suggested as a bet unless the main research session — the
model actually running the repo — reviews it and recommends it itself. The
model that made that final call is recorded on every opportunity. See
*Stage 3* below. Track record reset to zero at this bump; v1 rows deleted.

**Not a version bump (2026-08-23):** THEORY.md previously described the gate
as a cheap LLM stage while `gate.py` — deterministic code — is what actually
ran for v2. Rewriting the description to match the code corrects a document
that misdescribed the procedure; it does not change the procedure, so v2's
in-flight rows keep their meaning. Narrowing the gate's patterns to fix the
two known misclassifications *would* change the decision path and is held for
v3, so the 44 rows settling Aug 24–Sep 5 stay one comparable cohort.

1 — initial port. Stage 1 is ported from the original deterministic filter,
with two deliberate changes: it bands the favorite-price filter on the
**ask** rather than the **mid** (an edge measured against the mid is an edge
against a price nobody will fill), and it drops a market outright when the
book is one-sided instead of the original's fallback to `last_price` (a
stale trade print is not a price you can act on either). Both are
improvements, not incidental drift. Stage 2 replaces the OpenAI classify/pick
calls with Claude/subagent judgment.

## Stage 1 — mechanical screen

`python -c "from theories.insider_bias import screen"` — or call
`screen.screen(markets)` directly on the session board from
`tools.board.get_board(conn)` — never `markets.list_open()` directly, so one
session makes one pull shared by every theory.

Filters, all overridable per run:

- Excluded ticker prefixes: sports, esports, multi-variate parlays. The
  thesis cannot apply where nobody can know the outcome in advance.
- Favorite price in [0.65, 0.97] at the **ask**. Below the band there is no
  favorite worth calling informed; above it there is no room left after fees.
- Spread ≤ 0.07 and volume ≥ 500. An edge inside the spread is not an edge.
- Closes within 14 days and has not already closed.

The screen deliberately produces **no probability estimate**. Nothing is
recorded to the ledger at this stage.

## Stage 2 — what needs judgment

The screen finds tradeable favorites. It cannot tell you whether anyone
actually knows the answer. That is the whole thesis, and it is judgment.

**Three stages, and the gate is code.** The predecessor ran a cheap LLM gate
here. This theory does not, and that is a deliberate design decision rather
than a shortcut — see below. The final review was added at v2 and is not
optional.

| Stage | Sees | Decided by | Answers |
|---|---|---|---|
| Gate | every screened event | **`gate.py` — deterministic, no model** | "Is this a market family where private foreknowledge is structurally impossible?" |
| Analysis | gate survivors only | strong model, high reasoning | The full stage-2 assessment below, ending in a confidence bucket |
| **Final review** | **every analysed candidate, together** | **the main research session** | **"Do I recommend this bet?" — see Stage 3. Nothing reaches the user without it.** |

**Deduplicate by `event_ticker` before gating.** Sibling strikes on one event
— different contestants in one show, different dates for one announcement —
share a gate verdict and a thesis judgment, so paying for each separately is
waste. On 2026-08-23 this cut 765 candidates to 274 events.

### Why the gate is code and not a model

The gating question reads like judgment, but on this board it mostly is not.
This theory's own NO list is largely a list of **market families** — "any
future price", "weather", "live sports", "scheduled economic indicators",
"random draws". Whether a series is a Bitcoin strike ladder or a Chicago
temperature market is a ticker fact, not a judgment. Measured on 2026-08-23,
242 of 274 candidate events fell in such families. Asking a model 242 times
whether anyone can know tomorrow's weather is paying for an answer a pattern
already has.

Four things follow, and together they outweigh what an LLM gate offers:

- **Determinism.** The same board yields the same survivors, every time. This
  theory's central problem is a tiny sample; removing a variance source from
  the decision path is worth more here than almost anywhere else.
- **Auditability.** Eight patterns anyone can read and challenge, against 242
  opaque yes/nos nobody can review after the fact.
- **One less model in the decision path.** Tier B's cutoff rule takes the
  *later* of the judging models' cutoffs. With no gate model, the analysis
  model alone sets it.
- **Cost.** Free and instant, over the stage with the most volume.

### The rule for what may be blocked

**A family may be blocked only when the exclusion follows from the market's
resolution mechanics — how it resolves makes private foreknowledge impossible
— never from what the ticker name suggests the market is about.**

This rule exists because breaking it is the one failure this gate has actually
produced. The 2026-08-23 audit found two events blocked on name-shape rather
than mechanics: `KXMAMDANIMENTION` (what a mayor will say at a scheduled
announcement — his speechwriters are exactly the named informed group this
thesis hunts) and `KXEOWEEK` (executive orders, which this theory's own gating
rules list as a **yes**). Both read like counts, so both were filed as
aggregates. Neither should have been blocked.

Seven of the eight categories are genuine families and are safe. The
`aggregate of many independent people` category is the one doing semantic work
a ticker prefix cannot support, and both misses came from it.

### Where this is weaker than an LLM gate, and why it is still the trade

- It only knows families it has already seen. An unrecognised series falls
  through to `PLAUSIBLE` and reaches the expensive stage — the safe direction,
  but the expensive stage grows as Kalshi adds families.
- Inside a matched family it drops silently, and **a false elimination is
  invisible**: nothing downstream reports what the gate removed. Always report
  `gate_counts` when reporting a run.
- It needs maintenance, and nothing reminds anyone to do it.

An LLM gate would handle novel families and read the actual rules. But its
mistakes would be 242 unreviewable judgments, where these are eight lines in a
file with tests. A bounded, visible, fixable failure mode beats an unbounded
invisible one — particularly for a theory that has to earn trust from n=0.

**A gate "no" is a count, not a `rejected` opportunity.** The gate cannot
produce a bucket, so it cannot produce the edge `record_opportunity` requires,
and `disposition='rejected'` is reserved for a deep-stage verdict — that is
the control group `score.interpretation_value` measures stage-2 judgment
against. Report gate rejections as a count, the same treatment candidates
never reached at all get. If you want them in the ledger for bookkeeping,
record them and leave `disposition` at its default `'screened'`.

**If the screen is ever fixed so its output is thesis-aligned**, the volume
argument weakens and a cheap LLM gate reading actual resolution rules becomes
the better instrument again. That switch is a version bump.

**The gating question.** Is there a specific, identifiable group of humans who
probably already know the outcome, while the public does not? Not "could
someone guess well" — *does a production crew, a board, a voting body, or a
reporter's source already know*.

Say yes for: pre-taped competition TV (finales, reunions, eliminations),
award winners after a small voting body has voted, product launches and
release dates known to supply chain and press, executive hires and firings,
M&A closings awaiting only a date, cabinet and judicial appointments,
pardons and executive orders with circulated drafts, coaching hires, and
anything resolving on a discretionary decision a small group has already made
but not announced.

Say no for: live sports and fights, any future price (stocks, crypto, FX,
commodities), weather, scheduled economic indicators computed later from data
not yet collected, live election-day outcomes, random draws, and anything
resolving on the aggregate behavior of many independent people.

**Reality TV is the strongest sub-case, and the screen cannot see it.** The
original classifier listed pre-taped competition TV as one item among twelve
equally-weighted YES examples. In practice it is not one among twelve — a
pre-taped show has a *known taping date*, a *large crew*, and an *active leak
community*, which is a far more concrete informed group than "reporters may
have sources." When a candidate is a pre-taped competition show, weight it
well above the flat prompt's treatment. This heuristic came from the user's
own trading, not from the pipeline. **If it keeps proving out in the endorsed
vs. rejected split, encode it in stage 1 as a ticker-family boost and bump the
version.**

**Do not estimate a probability.** Never answer "I think this is about 85%".
That number would be an anchor on the price you just read, not a belief.
Instead assign a **confidence bucket** from the scale below, and let
`tools/buckets.py` convert it using what that bucket has actually been worth.

**Judge blind to price.** Run the judgment on the market question and its
resolution rules *without* the price, mid, or spread in context. Reveal the
price afterwards and compute edge mechanically. Record `judged_blind=True`
when you do. The screen has already guaranteed the price is in a sane band,
so the judgment step does not need it.

**Warning signs that lower the bucket:** a vague insider story ("someone
probably knows"), resolution rules that differ from what the title implies, a
resolution source that may not publish before close, and — when you do look at
price data — momentum moving *away* from the favorite, which is informed flow
leaving.

**Recording.** Because edge depends on the bucket's measured rate, record after
judging — but **the disposition is not set here**. Stage 2 produces a bucket
and an initial recommendation; Stage 3 decides whether it becomes a bet.

```python
from tools import buckets, ledger, score
rates = score.bucket_rates(conn, "insider_bias", version)
edge, basis = buckets.edge_for(bucket, entry_price, rates, PRIORS)
opp_id, _ = ledger.record_opportunity(
    conn, ..., edge_pts_net=edge, edge_basis=basis,
    confidence=bucket, judged_blind=True,
)
# Disposition comes from Stage 3, after the main research model reviews it:
#   ledger.interpret(conn, opp_id, "endorsed"|"rejected", notes)
# "endorsed" means the main model recommends the bet, NOT that edge > 0.
```

**Record the rejections too** — they are the control group that measures
whether this judgment is worth anything, and they are also what teaches the
`weak` bucket its rate. Candidates never reached within the scan budget are
reported as a count, not recorded.

## Stage 3 — the main research model makes the final call

**A subagent verdict is an initial recommendation, never a bet.** No candidate
from this theory may be put in front of the user as a suggested bet unless the
**main research session** — the model actually running this repo — has reviewed
it and recommends it in its own right. Added at v2.

Why this exists: at v1 the disposition was mechanical (`endorsed` whenever the
bucket implied positive edge), so a `moderate` verdict became a suggested bet
with nothing standing between the subagent and the user. The first live run
showed why that fails. Deep analysis returned 25 mechanically-endorsable
markets; reading them together, most carried a resolution-rules divergence
that cut *against* the very side the screen had selected — a defect visible
only when comparing candidates side by side, which is precisely what a
per-candidate subagent cannot do. The batch view is the main model's job.

**What the final review must do**, per candidate reaching it:

- Re-read the subagent's `rules_note`. Ask which *side* a divergence favours,
  not merely that one exists. A rule broader than its title makes YES easier,
  which damages a NO favourite — and this screen picks NO most of the time.
- Check whether the "informed group" actually knows something **the public does
  not**. A group that knows a fact already carried by the mainstream press
  supplies no asymmetry, and the thesis is asymmetry, not expertise.
- Check the candidate against its siblings. On a strike ladder, confirm the
  recommended legs are jointly coherent and identify which survive *every*
  live reading of the rules.
- Verify any post-cutoff factual claim a subagent made before relying on it.
- **Verify the resolution *mechanism* itself, not just the facts fed into
  it.** A subagent can correctly report that an informed group knows X and
  still miss that the market resolves on a step *after* X that is genuinely
  live — see Learnings, 2026-08-24 (`KXBIGBROTHERELIMINATION`). Read how the
  outcome is actually produced before accepting "no rules divergence" as
  "already decided."
- Confirm the resolution source can publish before close.

The final review may **lower** a bucket (the warning-sign rules above apply to
it exactly as they do to the subagent) and may decline to recommend a
candidate whose bucket implies positive edge. It should not raise a bucket:
the subagent judged blind to price and the main session has not.

**Recording — required.** Every opportunity carries, in `extra_json`:

```json
"final_recommendation": {
  "decided_by": "<model id of the main research session>",
  "subagent_model": "<model id that produced the initial verdict>",
  "subagent_bucket": "strong|moderate|weak",
  "final_bucket": "strong|moderate|weak",
  "action": "recommended|declined|override_down",
  "note": "why the main model reached a different conclusion, if it did"
}
```

`disposition='endorsed'` now means **the main research model recommends this
bet**, not merely that arithmetic produced a positive number. Anything it
declines is `rejected` with the reason, which keeps the control group that
`score.interpretation_value` measures meaningful.

**Name the deciding model when reporting to the user.** A recommendation is
not complete without saying which model made the final call — the user is
entitled to know whose judgment they are being asked to act on, and a later
session comparing track records needs it to tell whether a change in results
came from a change in procedure or a change in model.

## Prompts and provenance

**`RUNBOOK.md` in this folder is the end-to-end procedure** — every
stage, which artifact decides it, the model and prompt for each
judging stage, and the provenance commands to run before any
opportunity is written. Stages 1-4 are executable via
`pipeline.run_mechanical_stages(board)`; stages 5-6 are judgment.

This theory declares `uses_llm_judgment`, so `record_opportunity` refuses any
row for a run whose model and prompt were not recorded first.

| stage | prompt file | model used 2026-08-23 |
|---|---|---|
| gate | `gate.py` (deterministic — no model) | none |
| analysis | `prompts/analysis.md` | `opus` — an Agent-tool **alias**, web search on, effort not set |
| final_review | `prompts/final_review.md` | `claude-opus-5[1m]` (main session) |

**Subagent model ids are aliases, not pins.** The Agent tool takes `opus` /
`sonnet` / `haiku` / `fable` and resolves them harness-side without reporting
back what it picked. So a subagent stage can record *what was asked for*, never
*what ran*. Recording the alias is still the reproducible fact — a future
session passing `opus` gets whatever the alias maps to then, and that drift is
exactly what this record should expose rather than hide behind a pinned id
nobody verified. The main session's model is known precisely; subagent stages
are not.

Editing any of those files changes what this theory decides and **bumps the
version**, exactly like moving a threshold.

```bash
python -m tools.cli provenance list --theory insider_bias
```

**The gate is code by design, not by substitution** — see Stage 2 for the
reasoning. It has no prompt, so its `judgment_runs` row records
`model='none (deterministic)'` with `gate.py` itself as the artifact whose
sha is pinned. Editing `gate.py` therefore shows up as prompt drift in
provenance exactly as editing a prompt file would, which is the behaviour we
want.

## Confidence buckets

Priors are deliberately conservative and apply only until a bucket has 10+
settled results. After that the bucket's own realized win rate replaces them.

| bucket | meaning | prior edge (pts) |
|---|---|---|
| `strong` | A specific named group already knows — pre-taped show with a known taping date, a board that has voted, a signed deal awaiting announcement | 4.0 |
| `moderate` | A plausible informed group exists but is less specific — "reporters likely have sources" | 2.0 |
| `weak` | The thesis is a stretch; no concrete group identified | 0.0 |

**These priors are guesses and should be treated as placeholders.** The whole
point of the bucket mechanism is that they get replaced by measurement. If
`strong` turns out to be worth 9 points, the data will say so; if it turns out
to be worth nothing, the data will say that too — which is the outcome this
design most needs to be able to detect.

## How to backtest

**Tier B or C** — the decision path uses LLM judgment, so it is contaminated
on any market that resolved before the judging model's knowledge cutoff.

**The gate contributes no contamination**, because it is deterministic code
with no model in it. Only the analysis and final-review stages judge, so the
tier is set by their cutoffs alone rather than by the later of three. That is
one of the reasons the gate is code — see Stage 2.

Prefer tier B: restrict replay to markets resolving after the cutoff, with
web search disabled. For tier C runs, use the contamination probe first — ask
a subagent the outcome with only the market question and no price data; if it
knows, discard that market.

The stage-1 screen alone is tier A and can be backtested over full history
using `tools/kalshi/history.py`. That measures whether the *filter* selects
markets that beat their price — useful on its own, and uncontaminated.

**Built 2026-08-24: `theories/insider_bias/backtest.py`.** The candle→market
adapter this section used to ask for now exists (`replay_market`, reusing the
real, unmodified `screen.screen()` against reconstructed daily candles —
`no_ask ≈ 1 - yes_bid_close`, exactly as this section originally specified).

**The harder problem turned out to be fetch volume, not adaptation.** An
unscoped `list_settled(min_close_ts=..., max_close_ts=...)` walk is not
usable for this: one series, `KXMVECROSSCATEGORY`, alone settles 400,000+
markets per day, so even a 30-day window is tens of millions of rows before
any filtering. `candidate_series()` sidesteps it by querying Kalshi's
`/series` listing (one call, ~13k rows) and pre-filtering by category and
ticker prefix *before* ever touching `/markets`, then `iter_settled_survivors`
scopes each settled-market walk to one series via the (undocumented but
working) `series_ticker` param. This cut a run that hadn't finished after 47
minutes down to ~9 minutes for a 90-day window. See `backtest.py`'s module
docstring for the full account, and `tools/kalshi/markets.py`'s
`list_settled` docstring for the reusable fix (`series_ticker` and
`raw_filter` params, plus checkpointing guidance for any future caller facing
the same wall).

First run: `run_id=backtest-2026-08-24-stage1-90d`, 90-day window, 18,430
candidates survived the cheap pre-filter, systematic sample of 600 replayed
against real point-in-time candles, 200 actually cleared the screen. Results
and full breakdown in Learnings below.

## Learnings

- 2026-08-23 — Ported from `kalshi_trader`. The reality-TV weighting is
  recorded here as a stage-2 heuristic rather than encoded, because it has not
  yet been measured against the endorsed/rejected split. Migrate it into
  stage 1 only once there is evidence.
- 2026-08-23 — The imported history's `edge_basis='prior'` rows are not "it
  felt about right" placeholders — every field on this repo's convention
  says a missing basis means that, but these rows are the exception. They
  are LLM-introspected `q` values from `kalshi_trader`'s OpenAI gpt-5 **pick
  stage** (not the classifier/gate, which was gpt-5-mini and never produced a
  `q` at all), kept because they are the only dataset that can answer whether
  introspected probabilities realize their claimed edge. See each row's
  `extra_json.model_prob_source` for the exact provenance.
- 2026-08-23 — **First live run.** Complete board (96,084 markets) → 765
  candidates / 274 events. Classified against this theory's own gate rules,
  **242 of 274 events (88%) are categories the gate is written to reject** —
  crypto/commodity/compute strike ladders, weather, live sport that leaked
  past `EXCLUDED_PREFIXES`, scheduled indicators, and aggregates of many
  independent people. Stage 1 has no thesis term in it; it selects tradeable
  favorites, not markets an insider could know. Strong candidate explanation
  for the flat imported record.
- 2026-08-23 — **19 of 32 judged events (59%) had resolution rules that
  diverge from the title.** This section already lists that as a warning
  sign; at 59% it is the modal property of the candidate class, not an
  occasional trap. Reading rules may be a larger share of the available edge
  than identifying informed groups.
- 2026-08-23 — **The pre-taped-TV heuristic above is wrong as written.**
  Applied to `KXAGTELIMINATION`, deep analysis correctly refused it: AGT's
  live quarterfinals are not pre-taped and elimination is decided by public
  vote — the aggregate-of-many-people case the thesis excludes. The
  heuristic needs the qualifier *pre-taped **and** taping already completed*;
  on a live-vote show it inverts. `KXBIGBROTHERELIMINATION` is the version
  that does work: 24/7 live feeds give a concrete group the nominations,
  veto result and vote plan days before broadcast.
- 2026-08-23 — **Most rules divergences cut against the side the screen
  picks.** 543 of 765 candidates are NO-side favourites, and a rule broader
  than its title makes YES *easier* — so the divergence damages exactly the
  leg the screen selected. Seen live on `KXCLAUDE-NXTMYTH` (an unexcluded
  Mythos 5 already satisfies it), `KXNEWDEAL` (Trump already posted "we have
  a DEAL"), `KXTRYFIRECOOK` (removal already attempted in 2025), and the
  rolling-BLA markets (arguably already submitted). This is mechanically
  checkable and is the strongest stage-1 candidate for v3.
- 2026-08-23 — **v2 recorded**: 44 opportunities, 3 endorsed / 41 rejected,
  all `judged_blind=True`, all `edge_basis='prior'`, all carrying
  `final_recommendation.decided_by`. The gap between what the mechanical rule
  would have endorsed (25) and what the main model recommends (3) is the
  entire reason Stage 3 exists. They settle Aug 24–Sep 5, which makes
  `interpretation_value` computable for the first time.
- 2026-08-24 — **First tier A backtest: the stage-1 screen alone is
  net-positive, but the number is a mix of two very different signals.**
  90-day window, `run_id=backtest-2026-08-24-stage1-90d`, n=200 real screen
  hits (see "How to backtest" for the fetch methodology). Overall:
  `win_rate=85.0%`, `price_implied_rate=82.7%`, `calibration_edge_net=
  +1.38pts`. That headline number undersells what's actually there — three
  slices tell three different stories:
  - **n=47, series `gate.py` already classifies as "aggregate of many
    independent people"** (Rotten Tomatoes scores, Netflix rankings, album
    equivalent sales, YouTube view counts, shipping-lane traffic counts,
    press-briefing/launch counts): `calibration_edge_net = -11.12pts`. This
    is **direct mechanical confirmation that gate.py's existing exclusion of
    this family is correct** — buying these "favorites" loses money against
    their own price, not just against the thesis. Previously this was a
    design argument from first principles; now it is measured, tier A, n=47.
  - **n=116, series with a "MENTION"/"SAY"/"ACT" suffix that `gate.py`'s
    current regex does NOT catch** (`KXWCMENTION`, `KXTRUMPMENTION`,
    `KXFIGHTMENTION`, `KXLATENIGHTMENTION`, `KXHEARINGMENTION`,
    `KXFEDMENTION`, `KXFOXNEWSMENTION`, ...): `calibration_edge_net =
    +5.48pts`. Structurally this reads like the same aggregate-of-many
    pattern (a mention is decided by whether a public figure happens to say
    something, not by a small informed group), but it backtests
    **positive**, unlike the family above. Two live possibilities, not yet
    distinguished: either this is a base-rate-calibration edge unrelated to
    the insider thesis (still worth a mechanical rule, but a different
    theory), or "will X mention Y" markets really do have an informed
    minority (a press office, a campaign, a network that knows what's
    scheduled to air) the way `KXBIGBROTHERELIMINATION`'s live-feed viewers
    do. `gate.py`'s classification of this whole family as `PLAUSIBLE` is
    presently just an accident of which specific series got named in its
    regex, not a decision — see Status item 3.
  - **n=37, everything else (not mention-family, not gate-rejected)** — the
    slice that most resembles what actually reaches judgment in the live
    pipeline: `calibration_edge_net = +4.40pts`. Named series in this slice
    include `KXBIGBROTHERELIMINATION` (the same series as a live v2
    endorsed opportunity), `KXGABBARDOUT`, `KXEPSTEIN`, `KXFDAAPPROVE`,
    `KXTRUMPMEET`, `KXSTARMERCABLEAVE`, `KXLIUKELIMINATION`/
    `KXLOVEISLANDUSARANK` (reality-TV elimination, the theory's own
    strongest sub-case), `KXSUMMERHOUSECAST`, `KXESPYS`,
    `KXTAYLORSWIFTWEDDINGATTEND`. This is the cleanest tier A evidence yet
    that the screen, restricted to genuinely thesis-eligible families, beats
    its own price.

  Methodology note: this backtest used a **category-narrowed slice of
  settled markets** (Kalshi series `category` not in `backtest.py`'s
  `NO_CATEGORIES`, recency ≤ 60 days), not literally every settled market —
  see `backtest.py`'s module docstring point 2. That scoping choice is why
  n=200 is a *sample* of 18,430 raw survivors, not the full count, and
  should be named alongside this result, not left implicit.
- 2026-08-24 — **Stage 3 endorsed `KXBIGBROTHERELIMINATION-26AUG27-DRE`
  without verifying the resolution mechanism, and the user caught it, not the
  process.** The recorded rationale said "no rules divergence... resolution
  lands before close" and treated the outcome as effectively already known
  via 24/7 live feeds. That is half right: nominations and the veto result
  really were known days in advance. What it missed is that this season
  resolves eviction through "BB Block Buster" — the three nominees compete
  in a genuinely live, live-that-day competition, the winner is safe, and
  only *then* does the house vote out one of the other two. The competition
  itself is live sport, exactly the category this theory's own gate says no
  to; a subagent correctly reporting the pre-known facts (nominees, veto)
  does not mean the *thing the market actually resolves on* is one of them.
  On checking (web search, since this was live research on an open
  opportunity, not a backtest — see Backtest tiers on why that distinction
  matters), the NO bet still holds up, but for a narrower and more specific
  reason than originally recorded: the house's stated plan (Gold Derby, Big
  Brother Network, live-feed coverage, Aug 22-23) covers every branch of the
  live competition — Drew is protected whether Mallory, Taylor, or Drew
  himself wins it. That is house consensus robust across a live event, not
  an outcome already decided before the event. Corrected the opportunity's
  recorded interpretation (id 192) rather than leave the overstated version
  standing. The general lesson, folded into Stage 3's checklist above:
  verifying the facts a subagent reports is not the same as verifying that
  those facts are what the market actually resolves on.
