## Learnings

Distilled; the raw record is in `NOTES.md` (2026-09-01).

- **The three `taker_*` fields are one bit.** Over 93,399 trades they took
  exactly two joint values. `normalize()` raises on anything else rather
  than silently collapsing a side that no longer means what it did.
- **The trade feed does not reach past the archive floor.** It retains
  ~67 days against `/markets`' ~60 — a one-week extension, not a route to
  lost history. The ticket that proposed this theory claimed otherwise; it
  had mistaken a market's oldest *retained* trade for its open.
- **The pre-registered rule failed.** `|imbalance| > 0.6` at a 24h
  decision buffer: +0.70 pts, t=+0.62, CI [−1.51, +2.91]. The single-name
  localisation that the rule was built to test showed **no difference at
  all** (+0.71 single-name vs +0.69 broad-based). That specific claim does
  not replicate on Kalshi at a tradeable horizon.
- **The effect is a tail, not a gradient**, and this is the finding worth
  keeping: `strong` (0.6–0.9) is −0.78 pts over 618 clusters, while
  `extreme` (≥0.9) is +4.29 pts over 280 clusters (t=+2.04). Mined
  post-hoc, so it is registered as the slice `extreme-imbalance` with the
  mining run declared — it starts at n=0 out-of-sample and has to earn its
  record forward.
- **The tail survived every partition check** that could have killed it:
  top series is 3% of the cell, positive in all five price bands, positive
  on both sides, stable across time (+4.46 then +4.21), and
  leave-one-series-out worst case is still +3.50. Consistency across
  partitions is not significance, but it rules out the one-lucky-corner
  explanation.
- **Flow does not predict the next price move.** Lead correlation at a
  25-trade horizon is −0.008. Whatever this is, it is not short-horizon
  price prediction.
- **Liquidity filters do not imply payability.** A one-cent-wide book at an
  ask of 1.00 with 2,000 open interest passes every liquidity test this
  theory has and is still not a position. Caught by looking at the extreme
  values of the first live run rather than by reading the code; any theory
  pricing from a population average should check both.

**What would move it to `active`:** the `extreme-imbalance` slice clearing
its evidence gates (≥10 event clusters, ≥5 settlement days, out of sample)
with positive net edge. **What would send it to `under_review`:** the
slice reaching its gates flat or negative, which would make the mined
+4.29 a multiple-comparison artifact and leave the theory with nothing.
