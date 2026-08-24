# insider_bias — runbook

How to run this theory end to end, and what to record so the result is
reproducible. `THEORY.md` says *what* the theory believes; this says *how a
run happens*. Anything here that is code is authoritative — where prose and
`pipeline.py` disagree, the code is right and the prose is a bug.

Current version: **3**. Changing any prompt file, `gate.py`, `screen.py`, or
the stage sequence below is a decision-procedure change and **bumps the
version**. v3 (2026-08-24) added the mechanical MENTION-family path below;
it did not change stages 1–6, which is why the 44 v2 live rows stay their
own comparable cohort rather than needing a re-run.

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
from theories.insider_bias import pipeline

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

`insider_bias` declares `uses_llm_judgment`, so `record_opportunity` refuses
rows for a run with no provenance.

```bash
RUN=live-$(date -u +%Y-%m-%d)
python -m tools.cli provenance record --theory insider_bias --version 2 \
    --run $RUN --stage gate --model "none (deterministic)" \
    --prompt-path theories/insider_bias/gate.py --web-search 0
python -m tools.cli provenance record --theory insider_bias --version 2 \
    --run $RUN --stage analysis --model "opus (Agent tool alias)" \
    --prompt-path theories/insider_bias/prompts/analysis.md --web-search 1
python -m tools.cli provenance record --theory insider_bias --version 2 \
    --run $RUN --stage final_review --model "<main session model id>" \
    --prompt-path theories/insider_bias/prompts/final_review.md --web-search 1
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

## The mechanical MENTION-family path (v3, `mention_bucket.py`)

No judgment, no gate, no subagent, no Stage 3 — a wholly separate,
`edge_basis='measured'` path that runs and records without a research pass.
See `mention_bucket.py`'s module docstring for the full reasoning, including
the two caveats that must travel with every result it produces: the measured
rate is bootstrapped from one backtest, not this path's own live history,
and every candidate in the bucket carries the *same* probability (0.871) --
ranking is by price, not by any per-market signal.

```python
from datetime import datetime, timezone
from tools import db, board
from theories.insider_bias import mention_bucket

conn = db.connect()
live_board = board.get_board(conn)          # force=True if freshness matters
now = datetime.now(timezone.utc)

candidates = mention_bucket.find_candidates(live_board, now=now)
rates = mention_bucket.measured_rate(conn)   # reads the v2 backtest, not this run
ranked = mention_bucket.rank(candidates, rates, top_n=20)

if ranked:
    run_id = f"live-{now.date()}-mention"
    ids = mention_bucket.record(conn, ranked, run_id=run_id)
```

No CLI command for this yet — it is cheap enough to run inline, matching how
the stages-1–4 mechanical pipeline is invoked above. Promote it to
`tools/cli.py` once there is a second caller.

**First live run, 2026-08-24: 0 candidates.** Not a bug — checked directly.
490 mention-family markets were open on the board, but the *closest* one to
closing was still 14.6 days out (`screen.MAX_DAYS_AHEAD=14`), and 157 more
were sitting in the 14–20 day range. This looks like a batch of markets that
was recently issued with long horizons, not a sign the family stopped
existing; the near-term filter should start passing candidates within the
next several days as those age in. Re-run rather than assume this path is
broken.

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
