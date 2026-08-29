# Which existing backtests are exposed to the early-close anchor bug?

**Date:** 2026-08-29 · **Tier:** A (no model) · **Status:** measurement
complete, remediation is not mine to decide

## Why

`deadline_drift`'s first hazard estimate came out with the wrong sign
because it anchored "days to close" on each settled market's **actual**
close. On a "does X happen by D" market, actual close is a *function of the
outcome*: a NO runs to the deadline, a YES stops the moment the event fires
(measured: median 209.6 days early, 32/34). Corrected, the sign flipped
from −3.4 to +4.7 pts (`theories/deadline_drift/NOTES.md`, `a6302a8`).

Session 4f then measured the phenomenon at population scale: **66.8% of
173,632 settled markets close early**, median 3h, max 490 days.

`theories/insider_bias/replay.py:218` anchors on `settled.close_time` and
feeds it to the real `screen.screen()`, so the repo's two largest tier-A
backtests use the same anchor this bug lives in. **A 3-hour median is
harmless settlement mechanics; the question is the tail inside each
population.** So: measure, don't speculate.

## Method

Random sample of 70 distinct tickers from each fullcov run's ledger rows,
re-fetched from `/markets/{ticker}`, comparing `close_time` against the
deadline parsed from `rules_primary`
(`theories.deadline_drift.collect_settled.parse_deadline`). Markets with no
parsable by-deadline phrasing are date-certain or differently worded and
carry no exposure by this mechanism.

## Result

| run | sampled | fetched | with a parsed deadline | median early | >3d early | >30d early |
|---|---|---|---|---|---|---|
| `insider-fullcov` (n=3,195) | 70 | 68 | **15** | **152.4 d** | 12/15 | 9/15 |
| `mention-fullcov` (n=3,441) | 70 | 68 | 3 | −0.58 d | 0/3 | 0/3 |

**`mention_family` is not exposed.** Only 3 of 68 carry by-deadline
phrasing at all, and those closed *at* their deadline. Mention markets hang
off scheduled earnings calls, so close is date-certain by construction. Its
−1.53 net full-coverage result stands unaffected.

**`insider_judgment`'s full-coverage population is partly exposed.** About
22% of it is the by-deadline family, and within that family 80% closed more
than three days early, by a median of five months (max 1,275 days). So
roughly **18% of the population sits on a contaminated time anchor**, with
wide uncertainty — this rests on 15 markets.

## What the bias does, and why it probably does not rescue anything

For an exposed market the replay walks candles backwards from the *event*
rather than the deadline, so the screen samples it during the price run-up
toward resolution. The screen selects favorites. A market climbing toward
YES therefore enters as a high-priced YES favorite and then resolves YES —
**the bias inflates measured favorite win rates.**

That direction matters for how worried to be:

- Where the measured result was **negative or flat**, the true result is
  *worse*, so the conclusion strengthens rather than reverses. That covers
  the headline full-coverage numbers.
- Where a **positive** slice was drawn from the exposed population, the bias
  is a live alternative explanation and the slice needs re-checking on a
  deadline anchor.

`no_side_premium` deserves a specific look for that reason: its cell B
(non-mention YES favorites $0.80–0.90, claimed −3.89 net) is drawn from
exactly this population. The claim there is that those markets **lose**, and
an inflating bias makes the true loss larger — so cell B is conservative,
not at risk. Cell A comes from the mention population, which is unexposed.
Both look safe, but that is a reasoned expectation, not a measurement.

## Limits

- 15 exposed markets is a thin base for the 22%/80% split. A full pass over
  both populations would tighten it and is cheap.
- The parse only catches explicit `before <Month D, YYYY>` phrasing.
  Differently worded deadlines are counted as unexposed and may not be, so
  22% is a **floor** on exposure, not an estimate.
- Nothing here re-runs either backtest. The finding is where to look.

## Not acted on

Remediation touches `theories/insider_bias/`, which is not this session's
to change, and re-running a full-coverage backtest is a decision with a
real cost. Reported to session 09 for routing.
