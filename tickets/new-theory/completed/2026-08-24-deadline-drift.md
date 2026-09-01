---
title: Markets needing a discrete unscheduled event by a deadline overprice YES as the clock runs out: buy NO late
lane: new-theory
created: 2026-08-24
created_by: theory-backlog-2026-08-24
author_lane: find-theories
author_context: One of 22 researched design specs written in the 2026-08-24 literature passes; migrated out of docs/superpowers/specs/theories/ on 2026-09-01 so that the spec and the backlog entry are one document with one status.
status: done
closed: 2026-09-01
resolution: BUILT. Theory `deadline_drift` v1, status `proposed`. The 2026-09-01 walk widened settled capture from a 68-series allowlist to all 962 by-deadline series (1,908 markets) and found that the allowlist -- what the theory actually ships -- is uninformative (-1.0, CI [-9.8, +5.7], 22 clusters), while the wide hazard stratum is +4.6 at the tradeable price (CI [+1.0, +8.0], 94 clusters) and post-hoc. price() stays inert and DD-1/DD-2 are pre-registered in its THEORY.md. Live work continues in theories/deadline_drift/tickets/.
---
Effort: M · LLM in decision path: no · Backtest tier: A

**This spec was acted on; the `resolution` field above says what
came of it.** Kept rather than deleted, because a completed ticket
is the record of what was asked for and why — which is what a
future session re-deriving the same idea needs.

## Assessment

**Applicability 4/5 · Implementability 3/5 · Likelihood of success 3/5 ·
Composite 10/15** (rubric in the
[index](../README.md); ordinal priors, not
calibrated probabilities)

- *Applicability 4:* direct NO-side bets with clear entry windows and
  moderate candidate flow; docked one point because NO at $0.40–$0.95
  locks near-full collateral per point of profit.
- *Implementability 3:* the rules-text classifier plus its mandatory
  50-market audit is genuine work with a real misclassification risk —
  the design's own stated weak joint.
- *Likelihood 3:* the mechanism is triangulated from three documented
  effects (longshot bias, capital asymmetry, political horizon
  compression) but this exact expression is unmeasured; the bins may show
  implied and empirical hazard already agree.

## 1. Hypothesis

Markets that resolve YES only if a discrete, *unscheduled* affirmative
event occurs by a deadline (bill signed, resignation, deal announced,
ceasefire declared, indictment filed) systematically overprice YES as the
deadline approaches with no event. Buy NO in the late window when the
market's implied hazard exceeds the historical hazard by more than fees.

## 2. Evidence

Three mechanisms, two documented:

- **Longshot bias:** late-window YES on a quiet market *is* a longshot,
  and longshots are overpriced (see the
  [calibration-harvest spec](2026-08-24-calibration-harvest.md)).
- **Capital asymmetry:** Intrade evidence (500k+ transactions; Berg,
  Nelson & Rietz) — high-likelihood events underpriced and low-likelihood
  events overpriced specifically at long horizon, driven by NO locking
  more capital per unit of profit; hopeful YES holders capitulate slowly.
- **Anchoring:** the story that made the market interesting keeps the
  price sticky as the clock runs out.

Quantitative support from Le 2026: buying NO here means buying a
favorite, and favorites are measurably underpriced in exactly the
relevant cells — political markets (where most unscheduled
affirmative-event markets live) show calibration slopes of 1.48–1.83 from
12h out to a month.

## 3. Non-goals and exclusions

Two families are explicitly *not* the thesis, excluded by the gate with a
per-category report:

- **Scheduled certainties** (games, earnings, launches with fixed dates)
  — no hazard process; the event happens on schedule or the market is
  about its outcome, not its occurrence.
- **Continuous-threshold markets** ("BTC above X by date", weather) —
  level-crossing processes with different math; owned by
  [vol-crossing](../open/2026-08-24-vol-crossing.md).

One direction only: no symmetric YES-side bet (an undocumented thesis
that would muddy the track record).

**Amendment, 2026-08-29 — a third excluded family, and it is the biggest
one.** The 50-market audit section 7 mandates was run (four rounds,
disjoint samples; `studies/2026-08-29-deadline-drift-classifier-audit/`)
and found that the dominant contaminant is neither family named above:

- **Multi-destination / "which branch" markets** — "X's next team is Y
  before D", "Z is the first NFL team to announce a sale before D", "P is
  the first person confirmed as Commissioner before D", "Q becomes Prime
  Minister following the next election". These resolve YES only if the
  event happens **and** lands on this specific branch, so the process is a
  hazard **times a conditional multinomial**, not a hazard.

At board scale this is **2,687 markets, 34% of the entire by-deadline
population** — an implementation following the non-goals as originally
written pools all of it straight into the hazard bins, which is precisely
the poisoning section 7 exists to prevent. Excluding it (plus prose-form
count thresholds and scheduled competition outcomes, both also missed by
the original two families) still leaves 4,792 markets in 859 series,
3,079 in the entry band.

The audit's other result belongs here too, and it changes the spec's
implementation plan. Misclassification went **40% → 20% → 12% → 16%**
across four rounds. Round 4 folded in every fix the first three implied
and came back worse; at n=50 the SE on a 15% rate is ~5 points, so 12%
and 16% are one number — **a plateau near 15%, above this spec's own 10%
bar.**

The residue is semantic, not syntactic. The irreducible family is
multi-destination — "does this market condition on *which branch* the
event takes?" — which Kalshi expresses in unboundedly many ways: a
possessive ("X's next team is Y"), a relative clause ("the next club that
X joins is Y"), an ordinal ("is the first country to launch"), a
comparative ("before any other head coach"), a composition ("a coalition
that includes SPD make up the next government"). These share a meaning,
not a string, so section 4's "rules-text patterns" cannot express them
and section 8's effort estimate is optimistic.

**Section 4 as written is therefore not implementable at this spec's own
quality bar.**

**Amended later on 2026-08-29 — two repo changes reopened this.** First,
`tools` stopped discarding Kalshi's event envelope (`09a66f7`), so
**`mutually_exclusive` is free on every market** and answers the
multi-destination question as *data*. Second, the user amended the tier
rule (`0f06265`): tier A now means no *outcome* judgment, so a
**structural gate no longer costs tier A**.

So the choice is no longer "three options that each sacrifice something".
In the repo's own preference order — data, then code, then a structural
gate, then outcome judgment — the options are: **take the
`mutually_exclusive` data** (free, exact, unambiguously tier A, and named
in CLAUDE.md as the worked example with the instruction that no prompt
should re-derive it); a **structural LLM gate**, which *plausibly* keeps
tier A but only if it passes the contamination probe, which is **unrun**
— and an unrun probe counts as outcome judgment; a **series allowlist**
(mechanical, smaller population, maintenance treadmill); or **drop it**.

**Do not collect hazard bins under any option until that is settled** —
they are the expensive, rate-limited step and the one misclassification
poisons.

## 4. Decision procedure

Fully mechanical, no LLM.

- Screen: by-date affirmative-event markets identified from rules-text
  patterns ("occurs by", "before <date>", "on or before") plus the family
  exclusion list (gate.py pattern with category report).
- Filter: days-to-close ≤ 21; YES ask in ~$0.05–$0.60 (above the band the
  market believes the event happened or is locked; below it fees eat the
  residual); liquidity floor on the NO ask.
- Edge: empirical bins over settled by-date markets —
  `P(resolves YES | price p, t days remaining)` in (time × price) bins
  from ~12 months of candlesticks.
  `edge = (1 − P_hat(YES)) − NO_ask − fees`, `edge_basis="model"`.
- Rejected alternative, recorded deliberately: fitting a per-market
  constant-hazard curve from the market's own early price path assumes
  the early price was right — that contaminates the measurement.
  Parametric hazard by category is a v2 once bins have data.

## 5. Data requirements

In-repo only: board, rules text (`rules_primary` via
`tools/kalshi/markets.py`), candlesticks, fee math.

## 6. Backtest design

Tier A. Bin rates from the first half of history, P&L on the second.
Lookahead trap specific to this idea: "the event hasn't happened yet"
must be inferred only from the price path at decision time (price not yet
≥ ~0.90), never from the settlement we already know.

## 7. Kill criteria

- Implied and empirical hazard agree within fees across all bins → the
  market prices decay correctly; kill.
- Screen misclassification > ~10% on a hand-audited sample of 50 → fix
  the screen before trusting any bin. Misclassified threshold markets
  pool a different stochastic process into the bins and poison the
  measurement — this is the design's known weak joint.

## 8. Implementation plan

`theories/deadline_drift/{THEORY.md,screen.py,hazard_bucket.py}` + tests.
The rules-text classifier and its audit are most of the work; the bucket
math is mention_bucket.py again. Effort M.

## 9. Testing approach

Unit tests: rules-text pattern matching against real rule strings (both
families of exclusions), bin assignment, hazard-edge arithmetic. A
50-market hand-audit fixture for the classifier (section 7's threshold is
tested, not aspirational).

## 10. Open risks

- Rules-text phrasing drifts as Kalshi adds series; the classifier needs
  the audit re-run when its match-rate on the board shifts materially.
- The $0.05–$0.60 band interacts with the calibration-harvest fade band
  in weather-adjacent families — exclusion lists keep the screens
  disjoint, but verify at implementation time.

## 11. Sources

- [Berg, Nelson & Rietz — Accuracy and Forecast Standard Error of Prediction Markets](https://www.biz.uiowa.edu/faculty/trietz/papers/forecasting.pdf)
- [Interest-bearing positions and the long-horizon problem](https://arxiv.org/pdf/2602.21091) — the capital-lockup mechanism.
- [Le 2026](https://arxiv.org/pdf/2602.19520) — political-market compression at the relevant horizons.
