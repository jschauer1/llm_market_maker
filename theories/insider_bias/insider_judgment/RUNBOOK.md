# insider_judgment — runbook

How to run this theory end to end, and what to record so the result is
reproducible. `THEORY.md` says *what* the theory believes; this says *how a
run happens*. Anything here that is code is authoritative — where prose and
`pipeline.py` disagree, the code is right and the prose is a bug.

`theory_id='insider_judgment'` (renamed from `insider_bias` 2026-08-24 —
see `THEORY.md` Hypothesis section for why). The package path is
`theories.insider_bias.insider_judgment`; `theories/insider_bias/` is now a
shared parent folder, not this theory's own name.

Current version: **4** (2026-08-29 — `gate.py` now reads resolution rules
as well as ticker prefixes, cutting survivors 130 -> 18 on a full board;
and a confidence bucket now supplies its own realized edge rather than a
probability, and must span `buckets.MIN_BUCKET_DAYS` settlement days
before it may replace its prior. See THEORY.md Version). Carried forward from the
`insider_bias` rename, not reset. Changing any prompt file, `gate.py`, `screen.py`, or the stage
sequence below is a decision-procedure change and **bumps the version**.
v3 (2026-08-24) marks the point where the mention-family discovery
happened; it briefly lived here as a mechanical sub-path before moving into
its own theory the same day (`theories/insider_bias/mention_family/` — see
its own RUNBOOK.md for how to run it). It did not change stages 1–6, which
is why the 44 v2 live rows stay their own comparable cohort rather than
needing a re-run, and why the version number stayed at 3 rather than
reverting.

**There are zero rows recorded at v3, and that is expected, not a gap to
fill.** The 44 live rows in the ledger (`run_id=live-2026-08-23`, 3
endorsed / 41 rejected) are recorded at `theory_version=2` — they travelled
through v2's exact procedure, which is what actually ran that day. They
stay at v2 rather than being relabeled v3, because v2 is what produced
them; v3 exists as a version *number* (marking the mention-family
discovery point and the parent-folder rename) without this theory's own
procedure ever having changed since v2. The next live run of this theory's
stages 1–6 will be the first one legitimately recorded at v3 — and since
the procedure is unchanged, it should be directly comparable to the v2
rows, not treated as a break in the cohort.

## The LLM-judged path (v1–v2, stages 1–6)

| # | stage | who decides | artifact | recorded as |
|---|---|---|---|---|
| 1 | mechanical screen | code | `screen.py` | — |
| 2 | event dedup | code | `pipeline.dedupe_by_event` | — |
| 3 | **gate** | code (no model) | `gate.py` | `stage='gate'` |
| 4 | blind payload build | code | `pipeline.build_blind_payload` | — |
| 5 | **deep analysis** | subagents | `prompts/analysis.md` | `stage='analysis'` |
| 6 | **final review** | main session | `prompts/final_review.md` | `stage='final_review'` |

Stages 1–4 are one call. Stages 5–6 are judgment and cannot be scripted.

## 1–4. Mechanical (reproducible by execution)

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

## 5. Deep analysis — subagents

- **Prompt:** `prompts/analysis.md` (substitute `{input_path}`, `{n_events}`,
  `{n_markets}`, `{today}`, `{output_path}`)
- **Model:** `opus` — the strong tier. This is the stage the whole bucket
  calibration rests on; do not economize here.
- **Batching:** ~16 events per subagent. Batch within the tier; never one
  subagent per candidate.
- **Web search:** on. Load via `ToolSearch` inside the subagent.
- **Blind to price:** yes, guaranteed by stage 4.

Write `out["payload"]` to a file and pass the path — do not paste the payload
into the prompt, or the prompt text stops matching the recorded sha.

> **Model ids are aliases.** The Agent tool takes `opus`/`sonnet`/`haiku`/
> `fable` and resolves them harness-side without reporting back. Record the
> alias, not a pinned id nobody verified — an alias that silently remaps is
> exactly the drift the record exists to expose.

## 6. Final review — the main session

Follow `prompts/final_review.md`. This stage is required: no candidate
reaches the user as a suggested bet without it. It may lower a bucket and may
decline a candidate whose bucket implies positive edge; it may **not** raise a
bucket, because it has seen the price and the subagent had not.

## Recording — before any opportunity is written

`insider_judgment` declares `uses_llm_judgment`, so `record_opportunity`
refuses rows for a run with no provenance.

```bash
RUN=live-$(date -u +%Y-%m-%d)
python -m tools.cli provenance record --theory insider_judgment --version 4 \
    --run $RUN --stage gate --model "none (deterministic)" \
    --prompt-path theories/insider_bias/insider_judgment/gate.py --web-search 0
python -m tools.cli provenance record --theory insider_judgment --version 4 \
    --run $RUN --stage analysis --model "opus (Agent tool alias)" \
    --prompt-path theories/insider_bias/insider_judgment/prompts/analysis.md --web-search 1
python -m tools.cli provenance record --theory insider_judgment --version 4 \
    --run $RUN --stage final_review --model "<main session model id>" \
    --prompt-path theories/insider_bias/insider_judgment/prompts/final_review.md --web-search 1
```

Then record opportunities with `edge_pts_net` from `buckets.edge_for`,
`judged_blind=True`, and `extra_json.final_recommendation` per
`prompts/final_review.md`. `disposition='endorsed'` means *the main model
recommends this bet*, not that arithmetic produced a positive number.

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
`theories/mention_family/` — see that theory's own `RUNBOOK.md` for how to
run it (it shares `tools/screen.py`, the same shared mechanical filter this
theory's stage 1 uses, but nothing else). Nothing about running *this*
theory's own stages 1–6 changed by the split.

## Known weaknesses

1. **The gate classifies by series-ticker prefix and never reads resolution
   rules.** Its error rate is unmeasured. An audit on 2026-08-23 found at
   least two likely misses in the `aggregate of many independent people`
   bucket — `KXMAMDANIMENTION` (speech content: speechwriters are a named
   informed group) and `KXEOWEEK` (executive orders, explicitly a YES case in
   THEORY.md). Both were filed as counts because the ticker names read that
   way. Fixing this bumps the version.
2. **False eliminations are invisible.** The gate errs toward keeping an
   unrecognized family, but inside a matched family it drops silently and
   nothing downstream reports it. Sampling ~30 of the gated-out set and
   judging them blind against THEORY.md's rules would turn the error rate
   into a measured number.
3. **The screen has no thesis term in it** — it selects tradeable favourites,
   not markets an insider could know, which is why 88% of its output is
   gate-rejected. See THEORY.md Learnings.
