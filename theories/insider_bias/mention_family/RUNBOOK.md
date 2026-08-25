# mention_family — runbook

How to run this theory end to end. `THEORY.md` says *what* it believes;
this says *how a run happens*. Fully mechanical — no subagents, no prompts,
no web search, nothing to dispatch. One function call chain, safe to run
inline.

Current version: **1**. Changing `PRICE_BINS`, the mention-family pattern
in `mention_bucket.is_mention_family`, or the volume-tiebreak logic is a
decision-procedure change and bumps the version.

## Standard run — inside the validated 14-day window

```python
from datetime import datetime, timezone
from tools import db, board
from theories.insider_bias.mention_family import mention_bucket

conn = db.connect()
live_board = board.get_board(conn)          # force=True if freshness matters
now = datetime.now(timezone.utc)

candidates = mention_bucket.find_candidates(live_board, now=now)
rates = mention_bucket.measured_rate(conn)   # reads the 2026-08-24 backtest bootstrap
ranked = mention_bucket.rank(candidates, rates, top_n=20)   # each candidate on its OWN price bin

if ranked:
    run_id = f"live-{now.date()}-mention"
    ids = mention_bucket.record(conn, ranked, run_id=run_id)
```

`disposition` stays `'screened'` and `edge_basis` is `'measured'` — nothing
here needs a research pass before being reported as a candidate bet, though
still read `mention_bucket.py`'s module docstring caveats (the
`mention_family_85plus` bin's 100% win rate especially) before treating the
number as more certain than it is.

**Run this close to close, not as a one-off.** 36% of the historical hits
only became eligible on the literal last day before close. A single scan
weeks in advance will miss most of what this theory finds — see THEORY.md's
Stage 2 section and re-run as a recurring check.

## Previewing a wider window

`max_days_ahead` on `find_candidates` defaults to the validated 14 days.
Widening it looks further out than the backtest ever tested, so use
`rank_preview` instead of `rank` — it always returns `edge_basis='model'`,
never `'measured'` — and record with `confidence_suffix` set so a
wider-window run can never pool into a validated bin's rate:

```python
candidates = mention_bucket.find_candidates(live_board, now=now, max_days_ahead=30)
ranked = mention_bucket.rank_preview(candidates, rates, top_n=20)
if ranked:
    ids = mention_bucket.record(
        conn, ranked, run_id=f"live-{now.date()}-mention-preview30",
        confidence_suffix="_preview_30d",
    )
```

## No CLI command yet

Cheap enough to run inline. Promote to `tools/cli.py` once there is a
second caller of this exact chain (a recurring scheduled run would count).

## Provenance

This theory declares `uses_llm_judgment=False` (no LLM anywhere), so
`record_opportunity` does not require a `judgment_runs` row. `record()`
writes one anyway (`model='none (deterministic)'`, `prompt_path=
theories/insider_bias/mention_family/mention_bucket.py`) for the same
reason `gate.py` records itself in `insider_judgment` despite being code —
the artifact that governed a decision should be recoverable, not just
optional metadata.

```bash
python -m tools.cli provenance list --theory mention_family
```

## Known weaknesses

1. **The bootstrap rate is not this theory's own evidence yet.** Every
   `measured_rate()` call currently reads `insider_judgment`'s original
   90-day backtest (`run_id=backtest-2026-08-24-stage1-90d`, recorded back
   when that theory was still named `insider_bias`), not this theory's own
   live settlements. Once enough live rows settle, recompute from
   `score.bucket_rates(conn, "mention_family", 1, run_mode="live")` and
   compare — if it diverges materially from the bootstrap, the bootstrap
   was a single-window artifact, not a durable pattern.
2. **The `mention_family_85plus` bin's 100% win rate (n=41) will very
   likely regress.** No shrinkage is applied. See THEORY.md's Confidence
   buckets section.
3. **Entry timing is unexplored beyond "first eligible day."** Whether
   delaying entry on a market that qualifies early would help or hurt is
   unmeasured — see THEORY.md's Stage 2 section.
4. **Why the edge exists is still an open question**, not just how large it
   is — informed minority vs. base-rate quirk, unresolved. See idea
   `insider-bias-mention-family` for the revisit angle (read a sample of
   actual resolution rules and classify against the same gating question
   `insider_judgment` uses).
