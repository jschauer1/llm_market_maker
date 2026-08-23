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
section. Fetch markets once and reuse across theories:

```python
from tools.kalshi import markets
board = markets.list_open()
```

Write snapshots as a side effect so history accrues:

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

Within your scan budget, research the highest-ranked candidates by following
the theory's **Stage 2** section. Batch this — tens of candidates per subagent
call, never one subagent per candidate.

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

Use the theory's *endorsed* score row for realization when ranking an
endorsed opportunity.

## 7. Report in two layers

**Endorsed bets** — a table: ticker, side, entry price, confidence bucket,
claimed edge, **edge basis**, ranked edge, `n`, realization, theory, suggested
size, and your interpretation.

**Unresearched remainder** — a count, plus the top few by screen edge.

Always show claimed edge next to ranked edge, and always show the edge basis.
`prior` means the number is a placeholder nobody has measured yet; `measured`
means the bucket has earned it. If a theory has no track record, say so
plainly — a 12-point claim from a theory with `n=0` ranks as 3 points for a
reason, and the user should see why.

Rejected candidates and reasons are available on request.
