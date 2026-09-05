# calibration_harvest — backtest performance

<!-- research-memory-route -->
> [Find related lessons and their applicability](learnings/README.md). This document is
> source evidence: read its verdict and limits first, then the relevant method
> or result section. A useful short answer needs no duplicate summary.
<!-- /research-memory-route -->


**Distilled 2026-09-02 at retirement.** The raw payloads
(`backtests/{weather,politics,econfin,size}.json`, 508K) were deleted; this
file is what they measured. The user's ruling of 2026-09-01 was "theory +
notes + backtest performance with details, not the entire backtest".

**Every number below comes from one of exactly two surviving sources**, and
each is labelled:

- **[payload]** — the collector checkpoints
  `theories/calibration_harvest/backtests/*.json` at rev
  `d3ef5c6cfb571979586da9c60ad87aba174ba447`, re-read at retirement.
- **[rationale]** — the retirement rationale recorded on the theory's
  registry row (`theories.get(conn, 'calibration_harvest')
  ['retirement_rationale']`), written by the session that retired it.

Nothing here was estimated, re-derived or inferred. Where a number could
not be sourced from one of those two, it is absent rather than guessed —
including the per-cell tables, which live in `THEORY.md` and `NOTES.md`
beside this file.

## The kill criterion, and that it was met

Fixed in `THEORY.md` before any data existed: **"No cell clears fees
out-of-sample at n ≥ 30 *and* n_days ≥ 8."** [rationale]

**Met.** Across three complete populations: **47 cells past both floors,
ZERO positive net edges.** Six domains, ~7,500 collected rows. [rationale]

## Populations walked

Each checkpoint is per series: markets seen, observations kept, rows
written, and why rows were dropped.

| population [payload] | series entries | settled seen | obs | written | below floor | no candles |
|---|---|---|---|---|---|---|
| weather (`weather.json`) | 154 | 83,788 | 3,273 | 3,260 | 56,105 | 14,465 |
| politics (`politics.json`) | 2,508 | 3,567 | 1,541 | 944 | 444 | 9 |
| econfin (`econfin.json`) | 1,181 | 36,888 | 2,666 | 1,366 | 28,687 | 1,678 |

Two reconciliation notes, recorded rather than smoothed over. The weather
checkpoint's observations total **3,273** [payload] against the **3,267**
reported at the time in `THEORY.md`; the politics checkpoint holds **2,508**
series entries against the **2,507** reported. Both differences are one part
in ~500 and neither was reconciled before the payloads were deleted. The
checkpoints were the surviving artifact, so their totals are the ones
carried here.

A fourth payload, `econfin.json.pre-volume-bak` (121 series, 284 obs
[payload]), was the pre-volume-fields checkpoint superseded by the full
econfin walk. It is recorded here only so that its existence is not
mistaken later for a fourth population.

## What the third population settled

The econfin walk is the one that closed the theory, and it is genuinely
out of sample — the cell grid was drawn on weather and politics, and this
population was walked after. [rationale]

- Run `backtest-2026-09-01-calharvest-econfin`, **1,181/1,181 series,
  2,666 obs, five mapped domains.** [rationale; series and obs confirmed
  independently against `econfin.json` — payload]
- **27 cells clear both floors. ZERO clear fees.** [rationale]
- Net edge at the v4 bound runs **−6.57 to −25.29**. [rationale]
- **0 of 27 econfin cells survives Holm.** [rationale]

## The horizon axis reverses sign out of sample

Horizon was the only axis that ever showed structure, and it does not
survive the fresh population: **`1mo+` reads +9.38 on weather+politics and
−5.09 on econfin.** [rationale]

That claim had already been retracted once — on 2026-08-29, as a
pre-registration failure. [rationale] The reversal is therefore the second
failure of the same claim, not its first test.

## Sports: the counter-argument, checked

The forward corpus turned out to be dominated by a domain nobody had
labelled:

- Re-derived read-only from `extra_json.series_ticker` plus the complete
  `/series` map over all 7,000 settled live rows: **6,102 (87%) are
  Sports**, reading **−6.69 gross over 4 settlement days.** [rationale]
- Wrong sign. To rescue the theory the sign would have to flip **and**
  reach **+3.5** to clear the v4 frontier. [rationale]
- The theory's **−2.87 headline was an unlabelled sports number**;
  labelled, it did not improve. [rationale]

## And the sports walk is not affordable

The `collect size` cost probe priced the walk that would have settled it:

| [payload] `size.json` | |
|---|---|
| series scoped | 236 |
| series actually fetched before the probe stopped | 69 |
| candlestick fetches spent | 18,779 |
| Sports series scoped | 21 |
| Sports candlestick fetches | 9,270 |
| of which `KXMLBKS` alone | 8,911 |

Settled markets seen per category [payload]: Sports 10,925, Crypto 5,497,
Commodities 3,871, Economics 2,070, Financials 766, Science and Technology
90.

`collect size` hit a **429 after 21 *Sports* series**, by which point it
had already spent **9,270 candlestick fetches, 8,911 of them from
`KXMLBKS`** — figures the payload reproduces exactly. Sports is an order of magnitude dearer than
any population walked, and rate-limited in practice rather than only in
theory. [rationale]

## The test was fair — which took arranging

Until v4 the theory had a real excuse, and it is worth keeping because it
generalises: `cell_edge` was bounded on `n_days` with the design effect
pinned at **rho = 1**, and at that value the rule was **arithmetically
incapable of firing** — at `MIN_CELL_DAYS = 8` no cell above ask 0.65 could
emit a positive edge at any realized rate, and the `0.92–0.97` band needed
**79 days against 58 reachable**. A theory that cannot express an edge and a
theory that has none produce identical empty reports. v4 removed the excuse
on a structural argument (**measured rho median 0.027 against the assumed
1.0**), demonstrably without changing anything bettable — and only then did
the fresh population come back empty. [rationale]

The liquidity split, newly capturable in that session, **shows no ordering
in either direction.** [rationale]

## What is NOT claimed

**Not proof of absence.** Sports and Entertainment are unwalked at tier A,
and **12 of 20 domain-band cells are underpowered**. A future session with
days of budget could walk them. This record says so, so a revival is a
matter of evidence rather than archaeology. [rationale]

## What survives

[rationale]

- `cells.effective_n` and the design-effect argument — *a conservative
  default is a modelling assumption, and an unmeasured one can silently
  disable the thing it protects.*
- The `collect size` cost probe.
- The liquidity fields the collector persists.
- **Three complete tier-A calibration populations any future theory can
  read for free.**
