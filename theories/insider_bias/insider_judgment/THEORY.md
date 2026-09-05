# Insider Judgment

<!-- research-memory-route -->
> [Find scoped lessons and avoided mistakes](learnings/README.md). Read this specification
> for the claim/procedure relevant to your task; historical learning narratives
> are source evidence, not an accumulating current-memory summary.
<!-- /research-memory-route -->


## Hypothesis

Some Kalshi markets resolve on facts a specific, identifiable group of humans
already knows while the public does not — pre-taped reality TV, award votes
already cast, executive hires the board has already made, appointments
reporters already have sourced. When that private knowledge is real, the
public price still leaves room, and buying the favorite captures the gap.

Why it persists: the crowd cannot verify the private information, so it prices
on public uncertainty. The edge is not a smarter forecast — it is recognizing
which markets have an informed minority at all.

Ported from `kalshi_trader`, where it ran from May to July 2026 under the
name `insider_bias`. That predecessor track record was deleted at the v2
bump — see Status. Renamed `insider_bias` → `insider_judgment` on
2026-08-24 when `theories/insider_bias/` became a shared parent folder for
two sibling theories rather than this theory's own name — see next
paragraph. The old name is still the package/folder path
(`theories.insider_bias.insider_judgment`), not this theory's identity;
`theory_id='insider_judgment'` everywhere it matters (the ledger, CLI
commands, `provenance list --theory`).

**A mechanical sibling theory, `mention_family`, split off from this one on
2026-08-24 — see `theories/retired/mention_family/THEORY.md` for its
hypothesis.** It started as a v3 sub-path here (a purely mechanical, no-LLM
edge on "will X mention/say/do Y" markets, discovered as a side effect of
backtesting this theory's stage-1 screen) and moved into its own theory
folder once it was clear it tested a different claim than this one: not
"does a specific group already know," but "does this ticker family, priced
by its own measured historical rate, beat its own price." The two theories
share `theories/insider_bias/screen.py` (the mechanical filter both screen
with, living at the shared parent level) but nothing else — no `gate.py`,
no prompts, no Stage 3, no shared version number, no shared theory_id. This
theory's own v3 bump marks the point in history where that discovery
happened; its own decision procedure (Stages 1–6 below) is unchanged from
v2.

## Data sources

Kalshi only (`tools/kalshi/markets.py`). No Polymarket dependency.

## Status

`testing`, v7. The registered `strong-moderate-no` sub-theory is ready and
first-class. Candidates matching that predicate rank on the slice's current
eligible out-of-sample record; the complement ranks on its own record and
does not borrow the slice's evidence. The current sign, edge, and promotion
rung come from the CLI rather than this status prose.

The judgment claim is no longer `n=0`. Eligible tier B replays and live
settlements span the continuing version chain, and v6 now prices confidence
buckets from those measured live-plus-backtest rates. The discovery run named
in the slice's `mined_from_run_ids` remains excluded from validating the
slice; independent qualifying replays and forward settlements count in full.

The current procedure is five stages: mechanical screen, event deduplication,
deterministic gate, blind payload construction, and one deep-analysis
judgment stage. The price-aware final review used by v2-v4 was removed at v5
and is historical only. Stage 5 can use a Codex or Claude model comparable to
the Sonnet agents used in the judged benchmark. Under the user's idealized-judge assumption,
the same written procedure shares existing calibration across models; record
the actual model without requiring a compatibility experiment. Missing required
search access or a changed judging procedure remains a separate issue.

Use `python -m tools.cli score report insider_judgment`,
`python -m tools.cli slices report insider_judgment`, and `promote` for
current numbers and candidate rungs. The dated stage-1 replay, deleted v1
migration record, stage-3 interpretation history, and slice derivation remain
available through
[backtests/RESULTS.md](theories/insider_bias/insider_judgment/backtests/RESULTS.md),
the [historical notebook](theories/insider_bias/insider_judgment/notes/archive/NOTES.md),
and [scoped lessons](theories/insider_bias/insider_judgment/learnings/README.md);
they are not current status.

## Version

**7** (2026-09-05) — Measured bucket transfer now bounds the inferred
binary probability to `[0, 1]`, then derives gross and net edge from that
bounded value. The live run `insider-refresh-20260905T054912Z` exposed
strong-bucket probabilities above one near the payout ceiling. This is a
`continues` correction: the screen, prompt, classifications and population
stay the same, and historical observed returns remain evidence. Existing
v6 receipts and ledger rows retain their actual values; promotion key v5
holds impossible old claims at R4 until a new valid decision replaces them.

**6** (2026-09-01) — **the confidence buckets finally speak for
themselves.** `price()` asked `score.bucket_rates` for its defaults —
one exact `theory_version`, `run_mode='live'` — and got `{}` for this
theory's entire life, so `buckets.edge_for` fell through to `PRIORS`
every time and every judged row ever recorded carried
`edge_basis='prior'`. The measurement was there the whole time: 1,564
settled bucketed rows, `moderate` alone **565 rows over 58 settlement
days** against floors of 10 and 5.

Two independent causes, either sufficient, both fixed in
`tools/score.py`: an **exact version match** that a `continues` bump
should never have reset (the same defect class as the 2026-09-01
`state.py` incident — the sweep after it checked `compute_score` and
missed `bucket_rates` in the same file), and a **live-only default**
that contradicts the 2026-08-31 ruling that backtested evidence counts
exactly as forward-settled evidence does. `bucket_rates` is now built on
`observations()`, the same seam `compute_score` uses, and takes the same
`run_mode`/`pool` arguments; `price()` passes `("live","backtest")` and
`pool="chain"`.

Measured, the buckets are **+4.07 / +2.03 / −0.36** against priors of
+4.00 / +2.00 / 0.00. The priors were well chosen and the numbers barely
move — which is not a reason the change is cosmetic. `edge_basis` is the
field that tells a reader whether a number was measured or assumed, and
until now it said `prior` on every row while the data sat unread. Note
`weak` measures *negative* where its prior was flat zero.

`continues` — no screen, gate, prompt, bucket scale or threshold moved;
the procedure now reads a measurement it already had. Full account:
`NOTES.md` 2026-09-01.

**5** (2026-09-01) — **stage 3, the main session's price-aware final
review, is removed.** It was never part of the procedure that produced this
theory's evidence (every backtest row was generated without it) and it was
rejecting 72 of the 79 live rows the `strong-moderate-no` slice's record
entitled, each landing on R6 and so unbettable. Stage 2's bucket is now the
whole interpretation; what it is worth is decided by the candidate's
segment record through the promotion key, whose R4 gate was amended the
same day (key v3) to read the bucket rather than a disposition. Rows record
`disposition='screened'` — for this theory read that as "the bucket is the
interpretation", not "not yet assessed". Full argument, and why this is not
a return to v1's mechanical disposition, under Stage 3 below.

Bumped **`continues`**, and unusually well founded: since every backtest
row was produced by a five-stage procedure, v5 sits *closer* to the
measured evidence than v4 did. Nothing about stages 1–2, the screen, the
gate, the prompt or the buckets changed.


**4** (2026-08-29) — *Two changes, both in this version because no v4 row
had been recorded when the second landed.*

**(a) `gate.py` reads resolution rules, not only ticker prefixes.**
Measured over the whole 117,272-market board: the prefix allowlist removed
198 of 328 screened events, and **109 of the surviving 130 were still
families the thesis rejects outright** — 84% junk reaching the expensive
stage, in whole categories nobody had enumerated (39 Carbon Arc
vendor-panel events, 47 sport fixtures across a dozen leagues, 7
OpenRouter share events, 3 Metacritic events). A vendor panel says "Carbon
Arc" in its own rules whatever its ticker is called, so `RULES_NO_RULES`
matches the mechanics instead of the name and covers every such series
Kalshi adds without an edit. **Net: 130 survivors → 18**, and every one of
the 18 is an event a human reading this file would agree is at least
arguable.

Two seemingly-obvious rules were measured and **rejected** for silently
killing real candidates — a ticker-suffix sport rule that eats `KXRACE`
(Ferrari's own shipment count) and `KXXAIGAME` (xAI's own roadmap), and a
substring statistical rule where "Phili**PPI**nes" matches `PPI` and
`KXGTA**SALES**RECORD` dies on `SALES`. Both are documented in `gate.py`
with the measurement, and a test asserts those four survive. This is the
gate's own documented failure mode ("inside a matched family it drops
silently") caught before it cost anything.

**(b) A confidence bucket now contributes its own realized
EDGE, not a probability.* `tools/buckets.py` previously computed
`(bucket_win_rate − this candidate's price)`, which reads the bucket's
pooled win rate as this candidate's probability and therefore makes the
claimed edge vary 1:1 with price. That is a constant, not a calibration:
it manufactures edge on everything cheaper than the bucket rate and
negative edge on everything dearer, regardless of what the judge said.
Diagnosed on the 2026-08-28 run (a `weak` bucket graduated by one night of
gate-leaked football minted "positive edge" on 150 of 216 rows) and
confirmed unchanged on 2026-08-29 with a 4× larger sample — the rate moved
0.941 → 0.776 and the shape did not, still claiming edge on Taça de
Portugal football and app-download markets priced just under it.

Now the bucket carries `(win_rate − mean entry price of the rows that
measured it)`, i.e. how far it beat the prices it was actually bought at,
and only the fee depends on the candidate's own price. This also brings
three things that had silently disagreed into line: the prior path (always
points of edge), `score.compute_score` (which GRADES this theory on
`win_rate − price_implied_rate`), and `Edge.model_prob` (now this
candidate's price plus the bucket's edge).

A second guard lands with it: `buckets.MIN_BUCKET_DAYS = 5`. A bucket must
span five distinct settlement days before it may replace its prior,
because rows are not independent draws — the 2026-08-27 clustering study
measured this screen's own population swinging +4.26 / −7.29 / +5.40 net
across three consecutive close-days, and the `weak` bucket graduated on
17 rows that all settled on one night. `score.bucket_rates` reports
`n_days`, and a rates dict that cannot supply it fails closed to the
prior.

**Rows recorded at v3 and earlier keep v3's arithmetic and stay their own
cohort.** They travelled through the old formula; relabelling them would
be exactly the silent merge the versioning rule exists to prevent.

**No version bump — 2026-08-25 module move.** The tier A replay of the
shared stage-1 screen moved from `insider_judgment/backtest.py` to
`theories/insider_bias/replay.py`, and the `is_mention_family` ticker
classifier from `mention_family/mention_bucket.py` to
`theories/insider_bias/families.py` — both into the shared parent, beside
the `screen.py` they serve. No decision logic changed and neither theory's
version bumps: both call the same functions with the same arguments and
get the same results. The move restores the rule that a theory folder
never imports a sibling theory's folder, now enforced by
`tests/test_conventions.py::test_no_theory_imports_a_sibling_theory`.

**3** (2026-08-24) — *Marks the point where the mention-family discovery
happened; this theory's own decision procedure (Stages 1–6 below) did not
change.* Built after the 2026-08-24 tier A backtest found that
"MENTION"/"SAY"/"ACT"-suffix series are a real, distinct family (n=116,
`calibration_edge_net=+5.48pts`) that `gate.py`'s regex does not currently
name. For a few hours this lived here as a second, wholly mechanical
decision path (`mention_bucket.py`, `edge_basis='measured'`, no LLM, no
gate, no Stage 3) — **it has since moved out entirely into its own theory,
`mention_family`** (see Hypothesis, above, and Learnings below for the full
account, including a real flat-rate bug it had and fixed before the move).
This theory kept the v3 version number rather than reverting it — there is
no mechanism to un-bump a version, and doing so would be revisionist — but
`screen.py`, `gate.py`, the prompts, and Stage 3 here are byte-for-byte
what they were at v2. Read v3 as a historical marker, not a claim that this
theory's own procedure differs from v2's.

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

**Two interpretation stages, and the gate is code.** The predecessor ran a
cheap LLM gate here. This theory does not. Since v5 the analysis bucket is
the only judgment; the former price-aware final review is historical.

| Stage | Sees | Decided by | Answers |
|---|---|---|---|
| Gate | every screened event | **`gate.py` — deterministic, no model** | "Is this a market family where private foreknowledge is structurally impossible?" |
| Analysis | gate survivors only | strong model, high reasoning | The full stage-2 assessment below, ending in a confidence bucket |

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

- It only knows ticker and rules-text patterns already encoded. An
  unrecognised series falls through to `PLAUSIBLE` and reaches the expensive
  stage — the safe direction, but the expensive stage grows as Kalshi adds
  families.
- A matched family is removed before the ledger, so a false elimination has
  no settlement record. `gate_counts` and `ScreenResult.gate_removed` make the
  category visible; always report them and audit the removed population.
- It needs maintenance, and nothing reminds anyone to do it.

An LLM gate would handle novel families and read the actual rules. But its
mistakes would be 242 unreviewable judgments, where these are eight lines in a
file with tests. A bounded, visible, fixable failure mode beats an unbounded
invisible one.

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
judging. Since v5 rows remain `screened`: the bucket is the interpretation,
and the promotion key decides what its independently measured segment record
supports.

```python
from tools import buckets, ledger, score
rates = score.bucket_rates(
    conn, "insider_judgment", version,
    run_mode=("live", "backtest"), pool="chain",
)
edge, basis = buckets.edge_for(bucket, entry_price, rates, PRIORS)
opp_id, _ = ledger.record_opportunity(
    conn, ..., edge_pts_net=edge, edge_basis=basis,
    confidence=bucket, judged_blind=True,
)
# disposition stays "screened"; evaluate the recorded row with `promote`.
```

Historical v2-v4 endorsements and rejections remain intact as the control for
the removed final review. Current judged rows are all recorded as `screened`,
including weak buckets; candidates never reached are reported as a count.

## Stage 3 — removed at v5

**There is no stage 3.** From v2 to v4 this theory ended with the main
research session reading the judged batch *with prices visible* and
endorsing or declining each candidate; `disposition='endorsed'` was the
only path from a bucket to a bet. v5 removes it. A bucket from stage 2 is
the whole interpretation, and what a bucketed candidate is worth is decided
by its ranking segment's measured record through the promotion key.

### Why it went

**It was never in the procedure that earned the evidence.** All 3,759
backtest rows this theory holds — including the 314 out-of-sample rows
behind the `strong-moderate-no` slice at +3.76 net, the best-evidenced
result in this repo — were generated with no final review. So the live
path ran a six-stage procedure while every number used to justify it
described a five-stage one. That is the silent merge the versioning rules
exist to prevent, arriving through a side door: not two prompts under one
version, but two *stage counts* under one track record.

**It was rejecting the rows the evidence entitled.** Of 79 live candidates
matching the proven slice's predicate (a strong-or-moderate verdict on a NO
favorite), stage 3 endorsed 7 and rejected 72 — 91%. A rejected row is R6
CONTROL under the promotion key, so each of those was unbettable forever.
The mechanism that routes a proven sub-theory's candidates onto its own
record was working exactly as designed, and a second, unmeasured veto sat
downstream of it cancelling the result.

**The machinery it predates now exists.** Stage 3 was added at v2 for a
real reason: at v1 the disposition was mechanical — `endorsed` whenever the
*bucket's own claimed edge* was positive — and the first live run turned 25
`moderate` verdicts into suggested bets with nothing between a subagent and
the user. **v5 is not a return to v1**, and the difference is the whole
argument. v1 deferred to a claimed number from a bucket with no settled
history; v5 defers to a *segment's measured record* — evidence gates, an
out-of-sample split, `mined_from_run_ids`, the complement as control. None
of that existed at v2. The batch-level defects stage 3 was built to catch
now show up where they should: as a segment whose measured
`calibration_edge_net` goes negative, which suppresses its own candidates at
R5 without anyone reading them.

### What decides a bet now

Judgment classifies; measurement quantifies. Stage 2 assigns a bucket blind
to price, `buckets.edge_for` turns it into points from that bucket's own
realized history, and `promote` classifies the row on its segment:

- a ready `strong-moderate-no` match routes on the slice's own eligible
  out-of-sample record;
- the complement routes on its own record and cannot borrow the slice's edge;
- a bucket whose claimed edge is not positive at today's ask is suppressed.

The exact edge, sample, and rung are live facts: read them with `slices
report`, `score report`, and `promote` rather than copying a dated snapshot
into this procedure.

No model is in that path. The key-v3 amendment that made it possible is in
`docs/promotion-key.md`: the R4 gate now asks whether a *bucket* was
recorded rather than whether a second model endorsed, which is what the
rung's own rationale always said it was asking.

### What this does not claim

**It does not claim stage 3 was measured and found harmful.** Its endorsed
cohort settled 6/6 at +14.81 net against −8.06 for its rejections — which
points the *other* way. But n=6 over 2 event clusters clears no gate in this
repo; the endorsed cohort could not reach even R3's three-day floor. By this
project's own standard that is unconfirmed, not evidence. The argument for
removal is structural, not empirical: the stage was outside the measured
procedure and was vetoing the measured result.

The 456 interpreted live rows (9 endorsed, 447 rejected) stay exactly as
recorded at v2–v4 and remain a readable control for whether stage 3 added
value. The question is open and a ticket carries it; if the cohort ever
reaches a size that can answer it, the answer is worth having.


## Prompts and provenance

**`RUNBOOK.md` in this folder is the end-to-end procedure** — every
stage, which artifact decides it, the model and prompt for each
judging stage, and the provenance commands to run before any
opportunity is written. Stages 1-4 are executable via
`pipeline.run_mechanical_stages(board)`; stage 5 is the only judgment
stage (stage 6 was removed at v5).

This theory declares `uses_llm_judgment`, so `record_opportunity` refuses any
row for a run whose model and prompt were not recorded first.

| stage | prompt file | model used 2026-08-23 |
|---|---|---|
| gate | `gate.py` (deterministic — no model) | none |
| analysis | `prompts/analysis.md` | `opus` — an Agent-tool **alias**, web search on, effort not set |
| ~~final_review~~ | `prompts/final_review.md` — **retired at v5**, kept on disk only because eleven `judgment_runs` rows name it | `claude-opus-5[1m]` (main session), v2–v4 |

That table describes historical live settings. The judged benchmark used
`claude-sonnet-5` subagents, as recorded in
[the benchmark protocol](backtests/RESULTS.md#what-was-run) and the s200,
s200b, and s57 analysis provenance. Sonnet is the capability reference for
cross-runtime model selection; historical model identities remain unchanged.

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
python -m tools.cli provenance list --theory insider_judgment
```

**The gate is code by design, not by substitution** — see Stage 2 for the
reasoning. It has no prompt, so its `judgment_runs` row records
`model='none (deterministic)'` with `gate.py` itself as the artifact whose
sha is pinned. Editing `gate.py` therefore shows up as prompt drift in
provenance exactly as editing a prompt file would, which is the behaviour we
want.

## Confidence buckets

Priors are deliberately conservative and apply only until a bucket has at
least 10 settled results across at least 5 settlement days. Eligible live and
tier A/B backtest rows pool over the continuing version chain; after both
floors are met, the bucket's measured edge replaces its prior.

| bucket | meaning | prior edge (pts) |
|---|---|---|
| `strong` | A specific named group already knows — pre-taped show with a known taping date, a board that has voted, a signed deal awaiting announcement | 4.0 |
| `moderate` | A plausible informed group exists but is less specific — "reporters likely have sources" | 2.0 |
| `weak` | The thesis is a stretch; no concrete group identified | 0.0 |

**These priors are placeholders.** The current chain has enough eligible
evidence to measure the declared buckets; a future bucket below either floor
would still fall back to its prior.

## How to backtest

**Tier B or C** — the decision path uses LLM judgment, so it is contaminated
on any market that resolved before the judging model's knowledge cutoff.

**The gate contributes no contamination**, because it is deterministic code
with no model in it. Since v5, only the analysis stage judges; its cutoff
sets the tier. That is one of the reasons the gate is code — see Stage 2.

Prefer tier B: restrict replay to markets resolving after the cutoff, with
web search disabled. For tier C runs, use the contamination probe first — ask
a subagent the outcome with only the market question and no price data; if it
knows, discard that market.

The stage-1 screen alone is tier A and can be backtested over full history
using `tools/kalshi/history.py`. That measures whether the *filter* selects
markets that beat their price — useful on its own, and uncontaminated.

**Built 2026-08-24** (as `insider_judgment/backtest.py`; moved to the
shared parent as `theories/insider_bias/replay.py` on 2026-08-25)**.** The candle→market
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

[Choose an actionable lesson](learnings/README.md). The cards preserve only
scoped conclusions that change a later decision or avoid expensive repetition.
The original [learning narrative](notes/archive/THEORY-learnings.md) remains
available for a specific evidence question; it is not current startup context.

<!-- research-memory-archive: notes/archive/THEORY-learnings.md -->
