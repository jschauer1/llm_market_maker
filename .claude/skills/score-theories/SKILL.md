---
name: score-theories
description: Settle resolved opportunities and recompute calibration scores. Use when checking how recommendations performed, or as part of a research session.
---

# Score Theories

## 1. Find what has resolved

```python
from tools import db, ledger
from tools.kalshi import markets
conn = db.connect(); db.init_db(conn)
rows = ledger.list_opportunities(conn, unsettled_only=True)  # skip what already has a settlement
quotes = markets.quotes([r["kalshi_ticker"] for r in rows])
```

`unsettled_only=True` matters: without it this re-quotes every opportunity
ever recorded, on every run, unbounded — a ledger with 95 tickers today only
grows. A row with a settlement already on file has nothing left to check
here.

A Kalshi market is settled when its status is `finalized` and `result` is set.

## 2. Record settlements

```python
from tools import score
score.record_settlement(conn, ticker, result, resolved_at=...)
```

## 3. Recompute scores and bucket rates

```bash
python -m tools.cli score report <theory_id>
```

Then recompute what each confidence bucket is actually worth — this is what
replaces guessed probabilities with measured ones:

```python
rates = score.bucket_rates(conn, theory_id, version)
score.save_bucket_rates(conn, theory_id, version, rates)
```

Report any bucket that crossed 10 settled results: it has just graduated from
a declared prior to a measurement, which changes every future edge that theory
claims. If a bucket's measured rate is far from its prior, say so — a `strong`
bucket that turns out to be worth nothing is one of the most valuable findings
this system can produce, and the theory's priors in `THEORY.md` should be
updated to match reality.

The score report returns all four dispositions. The one that matters most:

```python
score.interpretation_value(conn, theory_id, version)
```

- **Positive delta** — interpretation is adding edge. The pipeline is a
  candidate generator; your judgment is the product.
- **Near zero** — interpretation adds nothing. Strengthen stage 1 or trust the
  pipeline and save the research time.
- **Negative** — interpretation is destroying value. Say so plainly.

It is `None` until both endorsed and rejected samples have settled.

## 4. Apply lifecycle flags

- `n = 20` with *net* calibration edge (`calibration_edge_net`) ≤ 0 → flag for
  review.
- `n = 50` with *net* calibration edge (`calibration_edge_net`) ≤ 0 → pause.
  **First check the disposition split**: a theory whose *endorsed* subset
  performs well while the overall screen does not is not dead, it needs a
  tighter stage 1.
- Retiring? Record why against the originating idea:
  ```bash
  python -m tools.cli ideas status <slug> dead \
      --outcome "<why it failed>" --revisit-angle "<or omit>"
  ```

## 5. Report both ROI numbers

`roi_all` is hypothetical — it assumes every suggestion was taken. `roi_taken`
is real money. Never present the first as if it were the second.
