# insider_judgment — runbook

How to run this theory end to end, and what to record so the result is
reproducible. `THEORY.md` says *what* the theory believes; this says *how a
run happens*. Anything here that is code is authoritative — where prose and
`pipeline.py` disagree, the code is right and the prose is a bug.

`theory_id='insider_judgment'` (renamed from `insider_bias` 2026-08-24 —
see `THEORY.md` Hypothesis section for why). The package path is
`theories.insider_bias.insider_judgment`; `theories/insider_bias/` is now a
shared parent folder, not this theory's own name.

Current version: **7** (2026-09-05) — measured bucket probabilities are bounded
to `[0, 1]`, with gross/net edge derived consistently. Screen and judging
stages are unchanged; the continuing evidence chain remains applicable.
Original receipts retain their version. Promotion key v5 holds impossible
legacy claims for a new bounded decision.

Previous version: **6** (2026-09-01 — **the confidence buckets now supply their own measured edge.** `price()` was asking `score.bucket_rates` for one exact version and `run_mode='live'`, which returned `{}` for this theory's whole life, so every judged row claimed a `PRIORS` placeholder while 1,564 settled bucketed rows sat unread at v3/backtest. `bucket_rates` is rebuilt on `observations()` and now takes `run_mode`/`pool` like `compute_score`; the theory passes `("live","backtest")` and `pool="chain"`. Measured buckets: strong +4.07, moderate +2.03, weak −0.36, against priors of +4.00/+2.00/0.00. Bumped `continues` — nothing in the decision path moved except that it now reads a measurement it already had. **Nothing in the run procedure below changes.** See THEORY.md Version 6.)

Previous version: **5** (2026-09-01 — **stage 6, the main session's price-aware final review, is removed.** A bucket from stage 5 is now the whole interpretation, and what it is worth is decided by the candidate's segment record through the promotion key (key v3). Bumped `continues`: every backtest row this theory holds was generated without stage 6, so v5 is closer to the measured procedure than v4 was. See THEORY.md Version 5.)

Previous version: 4 (2026-08-29 — `gate.py` now reads resolution rules
as well as ticker prefixes, cutting survivors 130 -> 18 on a full board;
and a confidence bucket now supplies its own realized edge rather than a
probability, and must span `buckets.MIN_BUCKET_DAYS` settlement days
before it may replace its prior. See THEORY.md Version). Carried forward from the
`insider_bias` rename, not reset. Changing any prompt file, `gate.py`, `screen.py`, or the stage
sequence below is a decision-procedure change and **bumps the version**.
v3 (2026-08-24) marks the point where the mention-family discovery
happened; it briefly lived here as a mechanical sub-path before moving into
its own theory the same day. That theory was retired (user, 2026-08-27)
and migrated on 2026-09-02: its record is now
`theories/retired/mention_family/`, and its `RUNBOOK.md` was deleted with the rest of its
code — retrieve it with `git show 450db428ec0e7542852fae6484ab8370aaeddfad:theories/insider_bias/
mention_family/RUNBOOK.md`. It did not change the then-current stages 1–6, which
is why the 44 v2 live rows stay their own comparable cohort rather than
needing a re-run, and why the version number stayed at 3 rather than
reverting.

**Historical correction:** v3 has substantial backtest and live rows in the
ledger. They were produced under v3 and stay labelled v3; do not relabel them
to the current version. Because the registry records v1 through v6 as one
`continues` chain, eligible rows pool when scoring and measuring bucket
rates. A version label records the procedure that produced a row, while the
chain declares whether its evidence applies now.

## Stages

Five stages since v5. Exactly one of them uses a model:

| # | stage | who decides | artifact | recorded as |
|---|---|---|---|---|
| 1 | mechanical screen | code | `screen.py` | — |
| 2 | event dedup | code | `pipeline.dedupe_by_event` | — |
| 3 | **gate** | code (no model) | `gate.py` | `stage='gate'` |
| 4 | blind payload build | code | `pipeline.build_blind_payload` | — |
| 5 | **deep analysis** | subagents | `prompts/analysis.md` | `stage='analysis'` |

Stages 1–4 are one call. Stage 5 is judgment and cannot be scripted.

**There is no stage 6 any more, and nothing replaces it.** Until v5 the main
session read the judged batch *with prices visible* and endorsed or rejected
each candidate, and `disposition='endorsed'` was the only route to a bet.
That stage is gone. Rows now record `disposition='screened'` — read it as
"the bucket is the interpretation", exactly as `edge_basis='model'` theories
already do, not as "not yet assessed".

**What decides a bet instead:** the promotion key. A bucketed row falls
through key v3's R4 gate to its ranking segment, and the segment's own
measured record classifies it — R1 where the record is past its evidence
gates and positive, R5 where it is past them and negative, R6 where today's
claimed edge is not positive. For this theory,
`strong-moderate-no` matches route to the slice and all other candidates
route to the complement; each uses its current eligible score. Judgment
classifies; measurement quantifies. Read exact rungs with `promote`.
**Do not re-introduce a session-level veto** — that
is the stage that was removed, and reinstating it by hand is a
decision-procedure change that needs a version bump and a reason.

## Run

"Run the theory" means all five stages, in order — a session that runs the
screen and skips the judgment stages has not run the theory; if a stage is
blocked (no judge budget, API down), the floor report names the stage and
why.

### 1–4. Mechanical (reproducible by execution)

```python
from tools import board as board_tool, db
from theories.insider_bias.insider_judgment import pipeline

conn = db.connect(); db.init_db(conn)
board = board_tool.get_board(conn)        # session's shared pull; snapshots itself

out = pipeline.run_mechanical_stages(board)
# out: board_markets, screened_markets, events, gate_counts, gated_out,
#      survivors, survivor_markets, payload
```

`out["payload"]` is the **only** thing that may reach a judging subagent. It
is built by whitelist and re-checked by `assert_blind`, which raises if any
price field survives. Do not hand-assemble a payload — the `judged_blind=True`
on every opportunity is only true because this function guarantees it.

Report `gate_counts` when reporting a run. A gate that drops candidates
without saying what it dropped lets a scan claim coverage it never had.

### 5. Deep analysis — subagents

- **Prompt:** `prompts/analysis.md` (substitute `{input_path}`, `{n_events}`,
  `{n_markets}`, `{today}`, `{output_path}`)
- **Outcome model:** the judged benchmark used `claude-sonnet-5` agents; see
  [the benchmark protocol](backtests/RESULTS.md#what-was-run). Choose a model in
  the active runtime with comparable Sonnet-class intelligence and appropriate
  reasoning effort. Under the user's idealized-judge assumption, a Codex or Claude
  model following this same procedure uses the existing production bucket and
  slice calibration. Model choice alone needs no experiment or version bump.
  Record the actual model and effort; capability matching is approximate.
- **Batching:** ~16 events per subagent. Batch within the tier; never one
  subagent per candidate.
- **Web search:** on for the established procedure. Use the search tool the
  active runtime actually exposes. If none is available, report this stage as
  blocked; do not dispatch without search or record search as enabled.
- **Blind to price:** yes, guaranteed by stage 4.

Write `out["payload"]` to a file and pass the path — do not paste the payload
into the prompt. Pasting it changes both the intended dispatch procedure and
the exact rendered prompt that provenance must record.

Each batch has a different rendered prompt because its paths and counts differ.
Record every batch before ingesting that batch's verdicts. Record the requested
model id when the runtime exposes it; otherwise record an honestly labelled
alias. Record effort only when it was specified or exposed, record the actual
web-search setting, and pass the exact substituted prompt through
`rendered_prompt`. The template path remains `prompts/analysis.md`, while each
stored hash identifies the rendered text one judge actually received.

The established Claude procedure requested the `opus` alias. When that runtime
does not expose the resolved id, its honest historical identity is
`opus (Agent tool alias)`. A Codex dispatch records its actual requested model
id and reasoning effort. Never copy one parent model or effort value across
separately dispatched work.

For new live or experimental runs, use
`docs/agents/judgment-batches.md`: prepare one `analysis` receipt per batch,
materialize its bare blind payload at the prompt's `{input_path}`, and save the
original operator run state before dispatch. Complete each returned receipt
with its actual execution metadata and parsed `Verdict` values. Keep the raw
verdict output alongside it for recovery. The historical `backtest_judged.py`
manifest/ingest procedure stays the owner of existing replay artifacts.

On restart, `judgments.load_run_state` restores the original screen and decision
time. Recover a pending receipt's original executed output before spending
tokens again. If a live batch had not executed when its session ended, follow
the timing rule in `docs/agents/judgment-batches.md`: start a fresh live run,
retaining the old pending artifacts for audit. Later web-informed judgments
must not become decisions recorded at the old timestamp and prices.
When all required batches are complete, attach them to that restored run with
`run.attach_completed_batches(receipts).finish()`. Each batch becomes its own
`JudgmentExecution`; provenance is written before opportunities. The batch
receipts and operator run-state file never go to a judging subagent.

### 6. — removed at v5

There is no stage 6. Once stage 5's verdicts are applied, `finish()` writes
the rows and the run is done; `python -m tools.cli promote --run "<run-id>"`
then says what each row is worth. `prompts/final_review.md` is retired history
kept on disk for the `judgment_runs` rows that name it — do not run it.

## Record — before any opportunity is written

`insider_judgment` declares `uses_llm_judgment`, so `record_opportunity`
refuses rows for a run with no provenance.

```text
python -m tools.cli provenance record --theory insider_judgment --version 7 --run "<run-id>" --stage gate --model "none (deterministic)" --prompt-path theories/insider_bias/insider_judgment/gate.py --web-search 0

python -m tools.cli provenance record --theory insider_judgment --version 7 --run "<run-id>" --stage analysis --model "<actual-requested-model-or-honest-alias>" --prompt-path theories/insider_bias/insider_judgment/prompts/analysis.md --rendered-prompt-file "<rendered-batch-prompt-path>" --web-search "<0-or-1>" --n-items "<batch-size>"
```

The host adapter supplies the run id and rendered-prompt path for each batch.
It also supplies the actual model and search setting; add `--effort
"<actual-effort>"` only when the runtime specified or exposed one. Repeat the
analysis command for every batch before reading its verdict file. This manual
CLI path remains useful for crash safety; passing the same complete execution
tuple to `TheoryContext` makes the later `finish()` writes idempotent.

Two stages record, not three: `gate` and `analysis`. Then record
opportunities with `edge_pts_net` from `buckets.edge_for` and
`judged_blind=True`. There is no `extra_json.final_recommendation` any more
and no `disposition` to set — rows stay `screened`, which for this theory
now means *the bucket is the interpretation*. Report what each row is worth
with `promote`, never by re-judging the batch yourself.

## Sub-theories

A **sub-theory** is a theory run over a *subset* of this theory's data:
same rows, narrower population, its own evidence. It accrues, clears its
gates and is scored separately, and it can be strong while this theory is
flat.

| slug | claim |
|---|---|
| `strong-moderate-no` | a strong-or-moderate insider verdict on a NO-side favorite is where the screen's population-level breakeven hides a real edge |

**This theory's sub-theory is ready and has its own evidence.** It ranks on
eligible out-of-sample rows pooled over the continuing version chain;
reporting only the parent would mix it back into the broader screen. Read the
current sample, replay share, edge, and gate state from the commands below
rather than from a dated prose snapshot.

Evaluating them is part of running this theory:

```bash
python -m tools.cli slices report insider_judgment
python -m tools.cli score report insider_judgment --save   # saves every segment
```

`mined_from_run_ids` names `backtest-2026-08-26-insider-judged-s200`, the
replay that generated the rule; it can never vouch for the slice. The
confirming replays do.

### It is maintained, not absorbed

**The slice being ready is the whole mechanism working.** A candidate
matching its predicate already ranks on the slice's own record --
`ranking_segment` routes it and `promote` uses it -- so a proven
sub-theory drives its bets with nothing adopted, merged or promoted.

**Never rewrite this theory's screen to produce only strong/moderate-NO
rows, and never fold the predicate into the decision procedure.** The bet
would be identical, and it would cost the complement (nobody could check
again whether the NO subset is still the part that works) and the
out-of-sample split that makes the evidence trustworthy. See
`docs/RESEARCH_GUIDE.md`, "A sub-theory is maintained, not absorbed".

**Historical note, because it is instructive.** This slice spent two days
as *orphaned evidence*: v2-v4 were recorded `breaking` under the old
default, so v4 was not entitled to v3's evidence and `promote` escalated
it every session. It was not fixed by adoption. Reclassifying those bumps
to `continues` (`theories.reclassify_bump`, after the 2026-08-31 ruling
that a bump continues the evidence unless it says otherwise) relinked
v1-v4, and the slice became ready at the current version with the screen
untouched. **An orphan is a versioning fact; relink the chain.**

## Report

The floor line carries the full funnel (board → screened → events → gated
out → survivors → judged → bucket distribution → rungs) **and the gate
breakdown by category** — a gate that drops candidates without saying what
it dropped lets a scan claim coverage it never had. Since v5 the tail of
that funnel is rungs from `promote`, not endorsements: "judged N: 2 strong,
5 moderate, 11 weak → R1 2, R5 5, R6 11" is the shape. "Judged N, R1 0" is
a normal, honest line.

## Skip

Skip only when the ledger shows a live run today at the current version
(the go freshness check), or the session log says today's run completed
clean. A run that stopped after stage 4 is not "ran today" — the judgment
stages are the theory.

## Observed funnel — 2026-08-23, v2

Reproduced exactly by `pipeline.run_mechanical_stages` against the same board:

```
96,084  board markets
   765  screened markets / 274 events
   242  gated out  ->  32 events survived
    44  markets judged (32 events; 30 web-researched, 2 judged without search)
     3  recommended by the main model
```

Gate breakdown: 61 aggregate-of-many-people, 47 live sport, 32 weather, 31
crypto, 28 commodity/FX, 20 compute/collectible, 16 scheduled indicator, 7
retail price index.

## The mention-family discovery — now its own theory

A mechanical, no-LLM edge on "will X mention/say/do Y" markets was found as
a side effect of the tier A backtest above, lived here briefly as a v3
sub-path, and moved into its own theory the same day:
`theories/retired/mention_family/`. Its live runbook was deleted on
retirement; retrieve the historical procedure at the git revision recorded
in that theory's `RETIRED.md`. It shared
`theories/insider_bias/screen.py`, the same mechanical filter this theory's
stage 1 uses, but nothing else. Nothing about running this theory's own
decision path changed by the split.

## Known weaknesses

1. **The deterministic gate recognizes only encoded ticker and rules-text
   patterns.** Novel impossible families fall through to the expensive
   analysis stage. Matched removals are reported by category through
   `gate_removed`, but they do not enter the ledger, so periodic audits of
   removed candidates remain necessary.
2. **Model equivalence is an operating assumption.** The judged benchmark used
   Sonnet agents; some live runs used Opus. Match the Sonnet benchmark's
   capability when choosing a Codex or Claude judge and follow the same prompt,
   blindness, buckets, and live web-enabled procedure. Actual classifications
   can differ. Keep provenance for later diagnosis; Opus is not a prerequisite.
3. **The screen is intentionally broad.** It selects tradeable favorites,
   while the judgment stage supplies the thesis term. The ready
   `strong-moderate-no` slice and its complement must remain separate so
   the supported subset drives only matching candidates and keeps accruing
   against its control.
