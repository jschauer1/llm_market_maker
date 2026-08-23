---
name: compare-theories
description: Compare theories by demonstrated performance, including whether interpretation adds value and what user divergences suggest. Use when asked which strategy works best or how theories stack up.
---

# Compare Theories

## 1. Gather

```bash
python -m tools.cli theories list
python -m tools.cli score report <id>   # for each
```

## 2. Keep separate what is different

- **Versions.** A v1 and v2 track record are different theories. Never merge.
- **Live vs. backtest.** Never blend.
- **Tier C backtests.** Mark clearly; excluded from credibility.
- **Small `n`.** Below 20 settled, say so beside every number. Below 10, the
  theory is on probation and its credibility is a floor, not a measurement.

## 3. Rank on demonstrated edge

Sort by `calibration_edge_net` with `n` shown, not by claimed edge.
`calibration_edge_net` is fees-adjusted and is the figure that is actually
comparable to a theory's claim, which is net by definition — sorting on gross
`calibration_edge` instead lets a theory that breaks even after fees look
like it has edge. (Gross `calibration_edge` is still worth reporting
alongside it for diagnosis — a theory that looks fine net but weak gross is
running on thin margins.) Include `realization` — how much of what a theory
claimed it actually delivered. A theory claiming 10 points and realizing 2 is
worse than one claiming 3 and realizing 3.

## 4. Report the interpretation-value breakdown

For each theory, endorsed vs. rejected vs. all. This is often the most
actionable number in the system: it says whether the research step is earning
its cost.

## 5. Mine divergences for new theories

```python
rows = ledger.list_opportunities(conn)
reasons = [(r["user_action"], r["user_reason"]) for r in rows
           if r["user_reason"]]
```

Where the user took something you did not endorse, or skipped something you
did, the reason usually encodes an unwritten heuristic. Recurring patterns are
candidate theories — run `propose-theory` on them (which will check the idea
registry first).

This is one of the most direct routes from tacit intuition to a testable
theory.
