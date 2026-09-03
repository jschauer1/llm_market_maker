# The aggregation gap is spread, and its headline case is not the identity it claims

**Verdict: DO NOT BUILD `aggregation-gap`.** Killed on the criterion the
ticket itself nominated — *"The gap does not exceed fees plus the cost of
holding both legs. This is the LIKELY killer and must be tested first."*

Session `fleet-w2-g2`, new-theory lane, 2026-09-01. Spec:
`git show 6e7d920:tickets/new-theory/completed/2026-09-01-aggregation-gap.md`, registry
idea 30. Measured on the session board (110,121 markets, pulled 21:59Z),
`python measure.py` -> `output.txt`.

## 1. The structural finding: the House ladder does not span the support

The ticket carries its own scope limit, and it is correct:

> "E[wins] is only recoverable where the strike ladder SPANS THE FULL
> SUPPORT. NFL qualifies (1..17 for a 17-game season). NBA and NCAAF do
> NOT... Any implementation must verify ladder completeness per family
> before computing anything, or it will manufacture enormous fake gaps."

**That warning applies to the ticket's own headline case, and was not
applied there.** `KXHOUSEWINSTATE` does not list a `>k` ladder. Each state
has **exactly one** "more than k" strike plus a short run of "exactly k":

| state | districts | A-strikes | E-strikes | bound width on E[seats] |
|---|---|---|---|---|
| AL | 7 | [2] | [0,1,2] | 0.06 |
| GA | 14 | [7] | [5,6,7] | 0.20 |
| LA | 6 | [2] | [0,1,2] | 0.09 |
| SC | 7 | [2] | [0,1,2] | 0.40 |
| TN | 9 | [2] | [0,1,2] | 0.18 |
| FL | 26 | [10] | [] | 1.73 |
| NC | 12 | [7] | [3..7] | 0.28 |

So `E[Dem seats]` is **bounded, not determined** — the mass above the top
strike has no conditional expectation. In SC the bound width (0.40) is
*larger than the claimed mid gap* (0.40 vs +0.40); across the five states
the widths run 0.06–0.40 against claimed gaps of +0.21 to +0.40.

The consequence is not a rounding quibble. **The exact conservation law the
ticket relies on does not exist for this family.** For NFL, a complete
1..17 ladder means `E[wins] = sum_N P(wins>=N)` replicates with one
contract per rung and the basket is riskless. With a single `A` strike
there is nothing to replicate, so the House instance is a *relative-value
bet on which of two quotes is wrong*, not an arbitrage — and the ticket's
own third kill criterion then binds: "The identity says they disagree; it
does not say WHICH is wrong. Settling that needs settled outcomes."
Those outcomes arrive **2027-11-03**.

## 2. The economics, which kill it independently of any of the above

At worst-case executable quotes — districts marked at **bid**, the state
expectation at **ask**, the most adverse assumption available — with the
truncation handled honestly as a lower bound:

| state | legs | gap @ mid | gap @ worst | fees $ | **net @ worst** |
|---|---|---|---|---|---|
| AL | 11 | +0.227 | −0.037 | 0.074 | **−0.111** |
| GA | 18 | +0.219 | −0.792 | 0.082 | **−0.874** |
| LA | 10 | +0.101 | −0.143 | 0.038 | **−0.181** |
| SC | 11 | +0.161 | −0.142 | 0.079 | **−0.221** |
| TN | 13 | +0.271 | −0.085 | 0.092 | **−0.177** |
| **mean** | 12.6 | **+0.196** | **−0.240** | **0.073** | **−0.313** |

**Positive at mid in 5 of 5, negative at executable prices in 5 of 5.**

**And the arithmetic that needs no adjudication at all:** the ticket's own
most favourable worst-case figure is **+0.073 seats**. The measured fee
cost of the basket that would capture it is **$0.073**. Those are the same
number. Even taking the spec's own numbers at face value and ignoring
every structural objection above, **fees consume 100% of the edge** — before
the 14-month capital lockup to a 2027-11-03 close.

The fee figure is a **lower bound**: it charges one contract per leg, while
replicating a seat count actually needs `k` contracts of each "exactly k"
leg. The real basket is larger and costs more.

## 3. This is rule 0f for the eighth time

`tickets/new-theory/README.md` rule 0f lists seven ideas killed or gutted
by measuring at mids instead of executable prices, and says: *"It is not
seven findings; it is one finding, seven times."* This is the eighth, and
it has the same shape as `combo-vs-leg`, the closest prior case: a real
mid-price gap sitting **entirely inside the spread**.

The NFL instance was already this, by the ticket's own honest reporting —
`SUM yes_mid = 274.25` against a true `<= 272`, but a bid/ask band of
`[264.03, 284.47]` straddling 272, and both riskless baskets failing at
executable prices (all-NO costs 279.96 against a 272 floor). The ticket
called that "NOT SIGNIFICANT... a sign, not a violation" and was right.
**What is new here is that the House case, offered as the stronger one,
fails the same way and additionally is not an identity.**

## 4. What survives, and is worth keeping

- **The gap's sign is not stable across the wider population.** Extending
  past the ticket's five states to all 14 with ladders, the mid gap is
  strongly negative in AZ (−1.78), IL (−1.69), MI (−3.73), NY (−5.34),
  OH (−2.55), PA (−3.64). The ticket attributes these to incomplete
  district coverage and that is consistent — Kalshi lists 8 of Michigan's
  13 districts, 20 of New York's 26 — but it means the *screen* for this
  theory would have to verify delegation completeness per state from
  outside Kalshi, which is another unpriced dependency.
- **`KXHOUSEWINSTATE` ladder shapes are worth not rediscovering**: FL's
  partition sums to 0.115 and NC's to 0.880, so these are not always
  coherent distributions and any future work must check before summing.
- The NFL family **does** have a complete 1..17 ladder and therefore a
  genuine conservation law (`sum over 32 teams of E[wins] = 272 - ties`).
  It is simply not violated at executable prices. That is a clean negative
  on the strongest available form of the cross-event test, and it belongs
  beside `combo-vs-leg` in rule 0's evidence list rather than being
  re-derived.

## Reproducing

```bash
python measure.py     # session board, no force; writes the tables above
```
