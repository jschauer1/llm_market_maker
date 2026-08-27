# no_side_premium — lab notebook

Append-only. Raw observations, dead ends, data quirks. Distill into
THEORY.md only what changes the claim, the procedure, or the status.

## 2026-08-26 — born as a forward test

Implemented from idea 14's revisit angle after two fullcov measurements
(details in the idea record and THEORY.md). Deliberate choices:

- Cells record at the **fresh ask at scan time**, not the board pull's
  ask — the board can be hours old, and the backtests entered at
  point-in-time asks, so scan-time asks are the honest forward analogue.
- Cell B rows are `rejected`, not `screened`, so the avoid claim is
  tested by the existing control-group machinery instead of polluting
  `roi_all` with rows the theory says are bad.
- First live day (board 108,820): population 807, cell A = 8 (all
  KXTRUMPSAY-26AUG31 strikes), cell B = 59. Cell A being one event's
  strikes today is fine for rows but means early cell-A settlements are
  event-clustered — the n >= 40 interim look must count events, not
  just rows, before believing anything.
