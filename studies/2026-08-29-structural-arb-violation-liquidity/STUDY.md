# structural_arb's violations are real, rare, and all three kinds are sterile

**Date:** 2026-08-29 · **Status:** complete · **Tier:** A (no model in the
measurement path) · **Verdict:** the v2 depth gate is validated; the
theory's *tradeable* firing rate over 11 board snapshots is **zero**, and
the reason is structural rather than bad luck

## Question

`structural_arb` has run live on three consecutive sessions and produced
five positions, **all five rejected** by its v2 depth gate. Before reading
that as either "the gate is too strict" or "the theory does not fire", it
is worth asking what the violations actually are.

The repo holds 11 stored board snapshots spanning 2026-08-24 to
2026-08-29 (96k–117k markets each), so the theory's own geometry can be
replayed over all of them with no API calls at all — which matters,
because Kalshi rate-limits the history endpoint to ~4–5 req/s
(`theories/calibration_harvest/NOTES.md`, 2026-08-29) and a collector was
already using it.

## Method

`probe.py` replays `scan._nested_pair_findings` over every snapshot,
grouped **exactly as `scan.scan()` groups** — by event *and then* by
`underlying_key`. Each distinct leg-pair is tracked across snapshots: how
many it appears in, whether its cost ever moves, and the lifetime volume
of its thinner leg.

Geometry only. The mutually-exclusive flag check and the depth gate are
skipped, and both only ever *remove* findings, so this is an upper bound
— the conservative direction for "are any of them tradeable?"

### A wrong first answer, kept here because it is the trap

The first draft grouped by event alone and reported **10,799
violations**, thousands per snapshot, many on legs with thousands of
contracts of volume. All nonsense. One Kalshi event holds several
independent ladders — a spread ladder per *team*, a hits ladder per
*player* — whose strike numbers compare numerically and mean nothing
across subjects. `KXCFLSPREAD-...-MTL8` against `...-WPG4` is not a
nesting; both legs can lose. `underlying_key` exists precisely to prevent
that, its docstring says so ("a false merge costs real money"), and
omitting it inflated the count by **1,800x**. Same family of error the
calendar-arb study hit from the other direction.

## Results

**Six distinct violations across 11 snapshots and 5 days** — a firing
rate of 1–4 per board pull.

| violation | gross | horizon | return/yr | thinner leg volume | snapshots |
|---|---|---|---|---|---|
| `KXWTAGTOTAL-...GIBVEK` 18/23 | 47.1% | 15d | 1146% | **0.0** | 1 |
| `KXWTAGTOTAL-...RAKKRE` 15/20 | 81.8% | 15d | 1992% | **0.1** | 1 |
| `KXWTAGTOTAL-...RAKKRE` 15/25 | 4.2% | 15d | 101% | **0.0** | 1 |
| `KXNCAAMBWINS-26SJU` 24/27 | 8.7% | 0.56y | 15.6% | **6.0** | **8** |
| `KXNASDAQ100MINY-26DEC31` | 12.4% | 0.34y | **36.4%** | **3,918** | 5 |
| `USCLIMATE` 2025/2030 | 6.6% | 4.34y | **1.5%** | **11,596** | 4 |

They fall into exactly three classes, and each is sterile for a different
reason:

1. **Untraded strikes (3 of 6).** Lifetime volume 0.0–0.1 contracts. The
   quotes are a market maker's opening marks that no trade has ever
   tested, so the spectacular annualised numbers are arithmetic on prices
   nobody will fill. Each appeared in exactly one snapshot — they are not
   persistent opportunities, they are noise that gets adjusted.
2. **Frozen thin ladders (1 of 6).** `KXNCAAMBWINS-26SJU` persisted
   through **8 of 11 snapshots at essentially unchanged prices**, on legs
   with 6 and 40 contracts of lifetime volume. A 15.6%/yr riskless return
   that sits untouched for five days is not an opportunity anyone is
   declining — it is a quote pair nobody can trade against. The live
   depth check measured it directly: 0.47 baskets fillable, **$0.02** of
   floor profit.
3. **Long-dated ladders (1 of 6, the liquid one).** `USCLIMATE`
   2025-vs-2030 is genuinely liquid (11,596 contracts) and genuinely
   persistent (4 snapshots), and returns **1.5%/yr over 4.3 years** —
   below cash. This is calendar-arb's conclusion arrived at
   independently: cross-date nesting survives only where carry dwarfs it.

**That leaves exactly one candidate in the whole dataset that was both
liquid and attractively priced:** `KXNASDAQ100MINY`, 12.4% over four
months (36.4%/yr) on a leg with 3,918 contracts of volume. It was
recorded live on 2026-08-27 as opp 9248 and **rejected as dust** — its
lifetime volume was high but the size available *at the arb prices* was
not. By the next session its YES leg had moved 0.07 → 0.21 and the
violation was gone.

## What this means

**The v2 depth gate is validated, not too strict.** All six would have
been correctly rejected, and the only one that looked genuinely
attractive proved the point by evaporating within a day. Lifetime volume
is not the right liquidity test — 9248 had 3,918 contracts and was still
dust at the prices that mattered — which is exactly why v2 walks the
order book instead.

**But the theory's tradeable firing rate over 5 days and 11 pulls is
zero, and the mechanism explains why.** A violation that is both fillable
and worth filling is, by construction, the one somebody else takes first.
What survives to be visible on a periodic board pull is the residue:
quotes too thin to fill, or horizons too long to be worth it. That is
adverse selection, not bad luck, and more sessions of the same scan
should not be expected to fix it.

## Standing, and what would change it

**No retirement proposal.** n=6 is far too small to reject anything, the
theory is `testing` with 0 settled rows, and the gate is doing precisely
its job. This study measures the *population*, not the theory's edge.

The theory's viability now rests on one specific, testable question:
**does a fillable violation on a liquid, short-dated ladder ever appear?**
The dataset says: once in five days, and it was gone within a day. Two
implications worth pre-registering before any version bump:

- If such violations decay in well under a day, a once-per-session board
  pull is structurally the wrong instrument, and the fix is *frequency*,
  not screen logic. That is an execution-cadence change the user would
  have to want.
- The three sterile classes are all mechanically identifiable *before*
  the depth fetch — untraded (volume ~ 0), frozen-thin (volume < ~100),
  long-dated (return/yr below a cash floor). Screening them out in stage
  1 would cost nothing and would stop the theory reporting finds it will
  always reject. That is a cheap version bump whenever someone wants the
  scan output to stop being misleading.

## Reproduce

```bash
python studies/2026-08-29-structural-arb-violation-liquidity/probe.py
```

No network. Reads `market_snapshots`; writes `data/violations.csv`.
