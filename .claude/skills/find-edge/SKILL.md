---
name: find-edge
description: Scan the running theories for live opportunities, research the top candidates, and report a credibility-ranked list of the best bets. Use when the user asks what to bet, where the edge is, or what looks mispriced right now.
---

# Find Edge

Pipeline output is a **candidate set, not a recommendation**. Your job is to
narrow mechanically, then research, then rank honestly.

## 1. Select theories

Run every theory that runs — `active`, `testing`, and `under_review`
(`theories.SCANNABLE_STATUSES`). Skip `proposed`, `paused`, and `retired`.

```bash
python -m tools.cli theories list --running
python -m tools.cli score report <theory_id> --pool chain
```

`--pool chain` pools evidence across any proven carry-chain (spec 2.5) —
without it a theory that carried its track record through a no-op version
bump reports only its current version's rows; the response's
`chain_versions` key shows what pooled, and is absent when nothing did.

Ordering by credibility is right; excluding the unproven is not. Ranking
already shrinks an unproven claim to a quarter of its face value and a
measured-worthless one to zero, so a weak theory cannot crowd out a strong
one — and a theory that never runs never earns the evidence that would
settle it. `under_review` in particular means "failing and being diagnosed,"
not "benched": taking it off the board is how you guarantee you never learn
whether it was broken or just unlucky.

Show each theory's status and standing alongside its picks, so a `testing`
theory's candidates are never read as a demonstrated edge.

Honor a user scope override ("just insider_judgment", "all theories").

## 2. Run every theory through the contract

No `THEORY.md` reading is needed to run stage 1. The parent session pulls
the board once, then runs mechanical theories inline and dispatches one
subagent per judgment theory:

```python
from datetime import datetime, timezone

from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect(); db.init_db(conn)
board = board_tool.get_board(conn)          # cached if fresh; go's Orient
                                            # makes the one force=True pull
ctx = TheoryContext.build(conn=conn, board=board,
                          now=datetime.now(timezone.utc), run_id="live")

results = []
for theory in registry.running(conn):
    if theory.uses_llm_judgment:
        dispatch(theory.id)                 # subagent; see the model below
    else:
        results.append(theory.start(ctx).finish())   # inline, no model
```

**Do not pass `force=True`** to `get_board` and do not call
`markets.list_open()` directly. One session makes one pull, shared by every
theory; `get_board` is what makes that true rather than aspirational. If you
need current prices for a handful of tickers right before recommending a
bet, re-quote just those with `markets.quotes(tickers)` — far cheaper than
any board pull.

The underlying walk takes no cap and always pages to exhaustion. Kalshi's
`/events` feed is not sorted by close time, so anything less than the
complete board is a biased slice that can silently exclude almost every
near-term market. A full walk is ~100k markets in about 13 seconds, and
`get_board` snapshots it automatically — you never need to call
`snapshot.save_kalshi` yourself.

**Dispatch model.** The unit dispatched is a theory id, not a payload. The
subagent instructions MUST state: the board is already pulled — call
`get_board(conn)` **without** `force`; open your own `db.connect()`; build
your context with `TheoryContext.build(..., judge_model="<the exact model
you are>")`, because `finish()` stamps provenance with the judging model,
not the parent's. Inside the subagent:

```python
from datetime import datetime, timezone

from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect()
ctx = TheoryContext.build(conn=conn, board=board_tool.get_board(conn),
                          now=datetime.now(timezone.utc), run_id="live",
                          judge_model="<the exact model you are>")
theory = registry.discover()["<id>"]
run = theory.start(ctx)                # cache hit: no second board pull
# Judge run.payload against theory.prompts, then build
# {Candidate.key: Verdict(bucket=..., rationale=...)} — a bucket from the
# theory's declared scale plus a rationale. Never a probability; a Verdict
# has no numeric field to put one in.
result = run.apply(verdicts).finish()  # price + provenance + ledger
```

The subagent's durable output is the ledger rows; its final message is a
compact summary of the ScanResult. Read the rows back with
`ledger.list_opportunities(run_id=...)` rather than trusting the prose.
Final cross-theory selection stays with the parent — credibility ranking
compares theories against each other, which no single-theory agent can do.

## 3. Filter for executability

Executability is no longer a judgment call: `tools/promotion.py` applies
the promotion key's stated thresholds (spread must be smaller than the
claimed net edge at today's ask; an ask must exist — see
`docs/promotion-key.md`, "Preconditions") and demotes what fails to R4 with
`not_takeable` in its reasons. **Report how many were demoted** so
nothing disappears silently.

## 4. Collapse duplicates across theories

If several theories surface the same ticker and side, that is **one bet with
corroboration**, not three bets. Merge them and note the agreement — it is a
genuine positive signal. Also flag when top candidates cluster on correlated
markets; a portfolio of correlated bets is not diversified.

## 5. Research the top candidates (stage 2)

**First check whether this theory has a stage 2 at all.** The discriminator
is `theory.uses_llm_judgment` — a `ClassVar`, drift-checked against the DB
by `registry.check_drift` rather than self-reported. A mechanical theory
(`uses_llm_judgment = False`) already ran inline in step 2 —
`theory.start(ctx).finish()` — so its candidates arrive **scored and
already recorded**. `edge_basis` is `model` for a pure calculation (e.g.
arbitrage) or `measured` when it mechanically applies a backtested bucket
rate (`mention_family`); either way it was never a judge's call. There is
nothing to research: skip straight to ranking (§6). That is not a
degenerate case, it is the preferred one — such theories are cheaper,
reproducible, and backtest at tier A.

The rest of this section applies only to a theory with `uses_llm_judgment =
True`, dispatched per §2's model.

Within your scan budget, research the highest-ranked candidates by following
the theory's **Stage 2** section.

**Cascade — don't spend deep reasoning on an unfiltered set.** If the screen
left you more candidates than you can afford to research properly, insert a
cheap gate first: a fast/small subagent answering one binary question ("does
this plausibly fit the thesis?"), batched tens per call, deduplicated by event
where sibling strikes share a verdict. Then send only the survivors to a strong
subagent with high reasoning effort for the real analysis. If the theory's
`THEORY.md` names its own tiering, follow that instead.

**Provenance is automatic through the contract.** `theory.prompts` maps each
judging stage to a prompt file in the theory's `prompts/` folder; `run.apply
(verdicts).finish()` records the model and prompt for every stage in that map
before any row lands — the `# price + provenance + ledger` comment in §2 is
literal. That is why the dispatched subagent must build its context with
`judge_model="<the exact model you are>"`: `finish()` stamps provenance with
`ctx.judge_model`, and for a theory that declares `uses_llm_judgment` it
raises rather than write a row if that is unset. There is no separate manual
`provenance record` call on this path — it is what makes an edge this scan
finds reproducible rather than anecdotal, without you having to remember it.

<!-- rule: batch-and-dedupe (moved from CLAUDE.md § Subagents — cheap gates, expensive analysis, 2026-08-29) -->
**Batch within a tier** — tens of candidates per call, never one subagent per
candidate. Deduplicate before gating — sibling strikes on one event almost
always share a verdict.
<!-- /rule -->
<!-- rule: buckets-from-deep-stage (moved from CLAUDE.md § Subagents — cheap gates, expensive analysis, 2026-08-29) -->
Confidence buckets always come from the deep stage; a gate answers "worth a
closer look," never "good bet."
<!-- /rule -->

**Never ask a subagent for a probability.** Ask for a classification, the
structural features the theory cares about, and a confidence bucket from the
theory's declared scale. A number an LLM introspects is mostly an anchor on
whatever price was in its context — see the theory's stage 2 section and spec
section 7.

<!-- rule: judge-blind (moved from CLAUDE.md § Never state a probability you introspected, 2026-08-29) -->
**Judge blind to price wherever the theory allows it.** Get the classification
first, reveal the price second, compute edge mechanically. Record
`judged_blind=True`. This costs nothing and removes the largest contaminant.
<!-- /rule -->

Build a `Verdict` per candidate — a bucket from the theory's declared scale
plus a rationale, never a number — and record through the contract:

```python
from tools import ledger
from tools.domain import Verdict

verdicts = {c.key: Verdict(bucket="strong", rationale="...") for c in ...}
result = run.apply(verdicts).finish()   # theory.price() converts bucket ->
                                         # Edge via the bucket's measured
                                         # rate, then writes every row
for opp_id in result.opportunity_ids:
    ledger.interpret(conn, opp_id, "endorsed", "<your reasoning>")
```

`theory.price()` attaches the `Edge` (mechanically, from the bucket's
measured win rate — never from the judge) and `finish()` writes every scored
candidate to the ledger. Disposition stays at the default `'screened'`
unless `price()` set it, so — exactly as before the contract — the
endorse/reject call is still yours to make afterward, now against
`result.opportunity_ids` instead of a hand-captured `opp_id`.

**Record rejections too.** They are the control group that measures whether
your judgment is worth anything — and they are what teaches the lower buckets
their rates. Without them, neither the endorsed-vs-rejected comparison nor the
bucket calibration ever becomes possible.

**A cheap-gate "no" is not a `rejected` disposition.** The gate cannot assign
a confidence bucket, so it cannot produce the edge `record_opportunity`
requires, and `score.interpretation_value`'s `rejected` group is reserved for
deep-stage verdicts — its docstring calls `rejected` the control group for
*stage-2 interpretation* specifically. A candidate the gate screens out is
either reported as a count, the same treatment unreached candidates already
get, or — if you do want it in the ledger — recorded and left at its default
`disposition='screened'` (never call `ledger.interpret(..., "rejected", ...)`
on it). Only a verdict from the deep analysis stage should ever move a row to
`rejected`.

## 6. Rank

**The evaluator does this whole section for you — prefer it.** One call
per run classifies every recorded candidate onto a promotion-key rung
with the correct segment, un-mixed rank inputs, today's ask, and the
ranked edge already computed:

```bash
python -m tools.cli promote --run <run_id>     # re-quotes; add --no-quote offline
python -m tools.cli promote <opportunity_id>
```

Its rung decides §7's report placement (R1/R2/R3 recommended; R4/R5/R6
not), exactly as in `go` — one promotion path however the question
arrives. The rest of this section explains what the evaluator computes,
for diagnosis and for the rare candidate not yet in the ledger.

Never sort on raw claimed edge. Use credibility shrinkage:

```bash
python -m tools.cli rank --edge <edge_pts_net> --n <settled_n> \
    --calibration-edge-net <cal_net> --mean-claimed-edge <claimed>
```

`--calibration-edge-net` takes the theory's *net* calibration edge (the
`calibration_edge_net` key from `score report`) — gross `calibration_edge` is
also in that report and useful for diagnosis, but only the net figure is
comparable to a claim, which is net of fees by definition.

**`--n`, `--calibration-edge-net`, and `--mean-claimed-edge` must all come
from the same `score report` row.** Never mix `n` from one row (e.g. `all`)
with realization figures from another (e.g. `endorsed`). Mixing rows is how
a `n=29` sample from `all` ends up shrinking an edge whose realization was
measured on a completely different, unrelated sample.

**Which row is the matching one depends on whether the theory endorses at
all.** Where it does, match the disposition: ranking an endorsed
opportunity means all three come from the *endorsed* row. Where it does not
— a mechanical theory, or a judgment theory with no endorsement stage, as
`insider_judgment` has been since v5 — there is no endorsed row and there
never will be one; the row that matches is the one covering the rows the
theory actually writes. Do not read an empty or stale `endorsed` row as
"this theory has no evidence".

**If the theory has registered slices, one score row is the wrong unit —
rank per segment.** Check with `python -m tools.cli slices list --theory
<id>`; when any slice exists, run each recorded candidate through
`python -m tools.cli slices match <opportunity_id>` and feed its
`rank_inputs` (already cluster-counted `n`, net calibration, mean claimed)
into `rank` instead of the whole-theory row. A candidate matching a
*ready* slice ranks on that slice's out-of-sample record; the rest of the
theory ranks on the **complement**, so the remainder cannot borrow the
slice's demonstrated edge — nor be punished for it. A candidate matching
a slice still below its evidence gates ranks unchanged but gets the
annotation `slices match` returns. Slice evidence is per theory version:
if the current version's segments are empty because a version bump
*adopted* the slice's rule, pass `--pool chain` to `slices match` and
`slices report` first — under a **proven carry**, pooling the prior
version's evidence in is mechanical, and the response's `chain_versions`
key confirms what pooled. Only when `chain_versions` does not appear
(a **breaking** bump never pools) fall back to the manual citation: cite
the prior version's segment via `slices report <id> --version <n>` and
say so explicitly in the report — switch to the current version's own
segment as soon as it is ready.

**If credibility computes to 0** — realization is 0.0 even though `n` clears
the probation floor — do not present a table of zeroed-out ranked edges. That
reads as "no edge exists" when the truth is "this theory hasn't demonstrated
the edge it claims yet." Report the claimed edge with the shrinkage reason
stated plainly instead, the same way you would never hide the shrinkage on
any other row.

## 7. Report recommendations, then the remainder

**Recommended bets** — one ranked table across all theories, citing the
promotion-key version, with a **rung** column (only R1 RECOMMENDED, R2
RISKLESS, and R3 PROVISIONAL belong in it; an R5 MEASURED-AGAINST or R4
ACCRUING candidate is reported in the remainder, by rung, never as a
bet): rung, ticker, side, entry price, confidence bucket (blank for
mechanical theories), claimed edge, **edge basis**, ranked edge, `n`,
realization, theory, **segment** (the slice, complement, or aggregate
row that ranked it — blank only for a theory with no registered
slices), suggested size, and your interpretation (blank for mechanical
theories). Disagree with a rung by reporting the dissent as a proposed
key amendment — never by moving the candidate.

Two kinds of candidate belong in this table, and `edge_basis` is what tells
them apart:

- **Researched picks** — a judgment theory's candidates that you endorsed at
  stage 2 (`disposition='endorsed'`, `edge_basis` `measured` or `prior`).
  **A judgment theory need not have an endorsement stage at all.** Where it
  does not, its judged rows stay `screened` carrying a confidence bucket,
  and the bucket is the interpretation — read them like mechanical picks
  below, and let `promote` rank them. `insider_judgment` is that case since
  v5. Never run `ledger.interpret` on such a theory's rows to make them
  look endorsed: since key v3 the R4 gate reads the bucket, so it buys no
  different bet, and it fabricates a control group that measures nothing.
- **Mechanical picks** — a code-only theory's candidates
  (`uses_llm_judgment = False`). `edge_basis` is `model` for a pure
  calculation (e.g. arbitrage) or `measured` when the theory mechanically
  applies a backtested bucket rate (`mention_family`) — never a judge's
  call either way. These stay at `disposition='screened'` because nothing
  interpreted them, which here means *needed no interpretation*, not *not
  yet assessed*. They are recommendable as-is. Do **not** run
  `ledger.interpret(..., "endorsed", ...)` on them just to make them look
  endorsed — that would pollute the endorsed-vs-rejected control group
  `score.interpretation_value` uses to measure stage-2 judgment.

**Unassessed remainder** — candidates from a judgment theory that you did not
reach within the scan budget. A count, plus the top few ordered by whatever
the theory's stage 1 provides (a screen edge, if it computes one). Some
theories — `insider_judgment` deliberately among them — produce no screen
edge at all; when a theory provides no ordering, fall back to an unordered
list rather than implying a ranking that does not exist. A mechanical
theory never has an unassessed remainder.

Always show claimed edge next to ranked edge, and always show the edge basis.
`prior` means the number is a placeholder nobody has measured yet; `measured`
means the bucket has earned it. If a theory has no track record, say so
plainly — a 12-point claim from a theory with `n=0` ranks as 3 points for a
reason, and the user should see why.

Rejected candidates and reasons are available on request.
