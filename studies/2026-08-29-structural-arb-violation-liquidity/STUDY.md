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

Note (2026-08-30): re-running this probe against post-compression snapshot rows requires routing raw_json/event_json reads through tools.snapshot.payload_text (spec 5.2 phase 3).

---

## Amendment 2026-09-01 — the probe's board reconstruction was wrong, and the conclusion survives anyway

Session `llm-market-identifier-af`, theory lane, focus `structural_arb`.
Full working in `theories/structural_arb/NOTES.md`, 2026-09-01.

**`probe.py` reads a board with `WHERE captured_at = ?`.** That was
correct when this study ran and stopped being correct on 2026-08-30, when
dedup-on-write landed: a pull now writes no row for a market whose
payload did not change, so an exact-stamp filter returns *the markets
that moved at that pull*. `snapshot.board_as_of` exists for exactly this
and its docstring names the trap.

The bias is not random. Markets that move are the liquid ones, so the
instrument was skewed along the very axis this study measures. Measured
both ways over the same 17 captures:

```
2026-08-27T11:47:05Z   exact:  3,254 markets   as_of: 107,656 markets
2026-08-30T19:22:32Z   exact: 55,433 markets   as_of: 104,304 markets
raw nested violations  exact:     24 total     as_of:      36 total
```

**A third of all violations were invisible to the original probe.**

**The conclusion is unchanged, and the direction of the error is why.**
The violations the old probe missed are the ones in markets that did
*not* move — the more illiquid half. Correcting the reconstruction finds
more violations and they are deader than the ones already counted, so
"real, rare, and sterile" is strengthened rather than overturned.

### Re-run over 17 captures / 8 days, with open interest added

`probe.py` recorded lifetime `volume` only. Open interest is the better
sterility signal — volume is cumulative and backward-looking, OI is
contracts outstanding now — and it was on every snapshot row already.

**16 distinct violations. 14 removed by `MIN_LEG_VOLUME = 100`. Of those
14, zero have both legs at open interest >= 100**; the largest min-leg OI
among them is 6.0, so the verdict holds at any cutoff above 6. The v3
threshold, fit on this study's original six violations, is well placed on
an axis it was never fit on.

The two survivors are both genuinely liquid, which is the screen working:

| violation | captures | min leg vol | min leg OI | what removes it |
|---|---|---|---|---|
| `KXNASDAQ100MINY-26DEC31H1600` T22600/T22800 | 5 | 3,918 | 2,388 | the depth gate (0.32-contract book, opp 9248) |
| `USCLIMATE-2025 + USCLIMATE-2030` | 4 | 11,596 | 2,263 | `MIN_ANNUALISED_RETURN` (1.5%/yr over 4.3 years) |

### New: the firing population is one series, and it is untraded

**12 of the 16 distinct violations are `KXWTAGTOTAL`** — WTA tennis match
totals — with min-leg open interest of 0.00 in nine of the twelve. Each
shows up in one or two captures and disappears.

That is the mechanism behind the theory's daily "2-3 raw violations, 0
survivors": these are not opportunities an arb bot compressed away, they
are **nominal ladders on markets nobody has ever traded**. Nothing forces
untouched quotes to be mutually consistent.

## Reproduce (superseding)

```bash
python studies/2026-08-29-structural-arb-violation-liquidity/probe_volume_threshold.py
```

No network. Reads `market_snapshots` through `snapshot.board_as_of` and
`payload_text`; writes `data/violations_v2.csv`. Prints exact-stamp and
reconstructed counts side by side so the distortion above stays visible.

`probe.py` is **kept, not fixed** — it is the record of what the v3
thresholds were actually fit on, and rewriting it would erase that. Use
the new probe for any fresh measurement.
