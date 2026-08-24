---
name: find-edge
description: Scan active theories for live opportunities, research the top candidates, and report a credibility-ranked list of the best bets. Use when the user asks what to bet, where the edge is, or what looks mispriced right now.
---

# Find Edge

Pipeline output is a **candidate set, not a recommendation**. Your job is to
narrow mechanically, then research, then rank honestly.

## 1. Select theories

Default to `status=active`, best-credibility first:

```bash
python -m tools.cli theories list --status active
python -m tools.cli score report <theory_id>
```

Honor a user scope override ("just insider_bias", "all theories").

## 2. Run each theory's stage 1

Open the theory's `THEORY.md` and follow its **Stage 1 — mechanical screen**
section. If this session already ran `go`'s Orient step, it already fetched
the complete board and wrote a snapshot this session — reuse that `board`
rather than fetching again. Otherwise, fetch markets once and reuse across
theories:

```python
from tools.kalshi import markets
board = markets.list_open()
```

`list_open` takes no cap and always pages to exhaustion — there is no
partial-fetch option. Kalshi's `/events` feed is not sorted by close time, so
anything less than the complete board is a biased slice that can silently
exclude almost every near-term market. A full walk is on the order of 60
requests and takes about a minute.

Write snapshots as a side effect so history accrues (skip this if reusing a
board `go` already snapshotted this session):

```python
from tools import db, snapshot
conn = db.connect(); db.init_db(conn)
snapshot.save_kalshi(conn, board)
```

## 3. Filter for executability

Drop candidates that are not really takeable — spread too wide relative to
the claimed edge, or volume too thin to fill. **Report how many you dropped**
so nothing disappears silently.

## 4. Collapse duplicates across theories

If several theories surface the same ticker and side, that is **one bet with
corroboration**, not three bets. Merge them and note the agreement — it is a
genuine positive signal. Also flag when top candidates cluster on correlated
markets; a portfolio of correlated bets is not diversified.

## 5. Research the top candidates (stage 2)

**First check whether this theory has a stage 2 at all.** A theory that
computes its edge mechanically — arbitrage, base rates, order-book structure,
cross-platform divergence — has an empty Stage 2 section and records
`edge_basis="model"`. For those, there is nothing to research: its candidates
arrive with an edge already attached, and you skip straight to ranking (§6).
That is not a degenerate case, it is the preferred one — such theories are
cheaper, reproducible, and backtest at tier A.

The rest of this section applies only when the theory's Stage 2 is non-empty.

Within your scan budget, research the highest-ranked candidates by following
the theory's **Stage 2** section.

**Cascade — don't spend deep reasoning on an unfiltered set.** If the screen
left you more candidates than you can afford to research properly, insert a
cheap gate first: a fast/small subagent answering one binary question ("does
this plausibly fit the thesis?"), batched tens per call, deduplicated by event
where sibling strikes share a verdict. Then send only the survivors to a strong
subagent with high reasoning effort for the real analysis. If the theory's
`THEORY.md` names its own tiering, follow that instead.

Batch within every tier — tens of candidates per call, never one subagent per
candidate. The confidence bucket always comes from the deep stage; a gate
answers "worth a closer look," never "good bet."

**Never ask a subagent for a probability.** Ask for a classification, the
structural features the theory cares about, and a confidence bucket from the
theory's declared scale. A number an LLM introspects is mostly an anchor on
whatever price was in its context — see the theory's stage 2 section and spec
section 7.

**Judge blind to price where the theory allows it.** Send the market question
and resolution rules without the price; reveal it afterwards and compute edge
mechanically. Record `judged_blind=True`.

Convert the bucket to an edge using its measured track record, then record:

```python
from tools import buckets, ledger, score
rates = score.bucket_rates(conn, theory_id, version)
edge, basis = buckets.edge_for(bucket, entry_price, rates, theory_priors)
opp_id, _ = ledger.record_opportunity(
    conn, theory_id=..., theory_version=..., kalshi_ticker=...,
    outcome=..., entry_price=..., edge_pts_net=edge, edge_basis=basis,
    confidence=bucket, judged_blind=True, rationale=...,
)
ledger.interpret(conn, opp_id, "endorsed", "<your reasoning>")
```

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
from the same disposition-matched `score report` row.** Ranking an endorsed
opportunity means all three come from the *endorsed* row — never mix `n` from
one row (e.g. `all`) with realization figures from another (e.g.
`endorsed`). Mixing rows is how a `n=29` sample from `all` ends up shrinking
an edge whose realization was measured on a completely different, unrelated
sample.

**If credibility computes to 0** — realization is 0.0 even though `n` clears
the probation floor — do not present a table of zeroed-out ranked edges. That
reads as "no edge exists" when the truth is "this theory hasn't demonstrated
the edge it claims yet." Report the claimed edge with the shrinkage reason
stated plainly instead, the same way you would never hide the shrinkage on
any other row.

## 7. Report recommendations, then the remainder

**Recommended bets** — one ranked table across all theories: ticker, side,
entry price, confidence bucket (blank for mechanical theories), claimed edge,
**edge basis**, ranked edge, `n`, realization, theory, suggested size, and your
interpretation (blank for mechanical theories).

Two kinds of candidate belong in this table, and `edge_basis` is what tells
them apart:

- **Researched picks** — a judgment theory's candidates that you endorsed at
  stage 2 (`disposition='endorsed'`, `edge_basis` `measured` or `prior`).
- **Mechanical picks** — a code-only theory's candidates
  (`edge_basis='model'`). These stay at `disposition='screened'` because
  nothing interpreted them, which here means *needed no interpretation*, not
  *not yet assessed*. They are recommendable as-is. Do **not** run
  `ledger.interpret(..., "endorsed", ...)` on them just to make them look
  endorsed — that would pollute the endorsed-vs-rejected control group
  `score.interpretation_value` uses to measure stage-2 judgment.

**Unassessed remainder** — candidates from a judgment theory that you did not
reach within the scan budget. A count, plus the top few ordered by whatever
the theory's stage 1 provides (a screen edge, if it computes one). Some
theories — `insider_bias` deliberately among them — produce no screen edge at
all; when a theory provides no ordering, fall back to an unordered list rather
than implying a ranking that does not exist. A mechanical theory never has an
unassessed remainder.

Always show claimed edge next to ranked edge, and always show the edge basis.
`prior` means the number is a placeholder nobody has measured yet; `measured`
means the bucket has earned it. If a theory has no track record, say so
plainly — a 12-point claim from a theory with `n=0` ranks as 3 points for a
reason, and the user should see why.

Rejected candidates and reasons are available on request.
