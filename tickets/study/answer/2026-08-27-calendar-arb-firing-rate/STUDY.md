# calendar-arb does not fire, and its premise is false at every tradeable horizon

**Date:** 2026-08-27 ·
**Tier:** A (no model in the measurement path) ·
**Verdict:** do not build the spec as written

## Question

calendar-arb (spec: `git show 6e7d920:tickets/new-theory/completed/2026-08-24-calendar-arb.md`)
(backlog #12, effort S) proposes trading date-monotonicity violations:
P(X by June) ≤ P(X by July) is a hard logical constraint, so buying the
later-deadline YES and the earlier-deadline NO locks a profit whenever
`ask(YES, later) + ask(NO, earlier) < 1 − fees`.

Its premise is explicit: *"Kalshi lists these as separate events, priced by
separate crowds, with no cross-event margining — so date-monotonicity
violations at executable quotes are a hard-logic arbitrage no within-event
scanner sees."*

The spec's own first deliverable is measuring the firing rate from snapshot
history. That is cheap, so it was done **before** building anything.

## Method

Ten stored board snapshots, 2026-08-24T01:34Z → 2026-08-27T23:18Z
(96k–110k markets each). Within each, group markets into date-ladder
families and check every ordered pair.

**Grouping is strike-aware, and that matters.** A first, naive pass keyed
only on (series, title with the deadline clause removed) and produced three
"violations" — one of which was `KXU3MAX-30-20` ("unemployment reaches 20%
by 2030") paired against `KXU3MAX-27-4.5` ("reaches 4.5% by 2027"). Those
are **not nested**: different thresholds, and *both legs can lose*. Trading
that pair loses money outright. The strike (`floor_strike`, `cap_strike`,
`strike_type`) therefore joins the key. This is the by/in classifier trap
the spec calls "the whole risk concentrated in one place", and a naive
implementation walks straight into it.

Prices are the snapshot's own `yes_ask_dollars` / `no_ask_dollars` —
executable top-of-book, never mids. Fees are
`min(0.07·P·(1−P), 0.035)` per leg.

Reproduce with `probe.py`; raw findings in `data/`.

## Result 1 — the firing rate is zero at any usable buffer

| execution buffer | pairs checked | violations |
|---|---|---|
| 1¢ per leg (the spec's own starting buffer) | 18,877 | **0** |
| none at all | 18,877 | 7 |

The seven no-buffer hits are only **two distinct positions**; one recurs
across six consecutive snapshots.

| position | profit/basket | resolves | annualized |
|---|---|---|---|
| `KXDECLAREPRESFIRSTD-…-KHAR` (cross-event) | 1.21¢ | Nov 2028 | ~0.55%/yr |
| `KXFDAAPPROVE-MDMA` (same-event) | 0.60¢ | Jan 2031 | ~0.14%/yr |

Both are worse than holding cash, and neither survives a 1¢/leg buffer.
`structural_arb`'s live experience adds the rest: both of its own
top-of-book finds died on orderbook depth (~$0.02 and ~$0.30 fillable), and
nothing here suggests these would fare better.

## Result 2 — the premise is false where it would matter

Splitting all 1,944 ladder pairs on the newest board by horizon and by
whether the two legs share an event page:

| later-leg horizon | scope | pairs | min cost |
|---|---|---|---|
| **≤ 90d** | **same-event** | **295** | **1.000** |
| ≤ 90d | cross-event | **0** | — |
| 90d–1y | same-event | 668 | 1.000 |
| 90d–1y | cross-event | 39 | 1.050 |
| 1y–3y | same-event | 593 | 0.990 |
| 1y–3y | cross-event | 43 | 0.980 |
| > 3y | same-event | 292 | 0.960 |
| > 3y | cross-event | 14 | 1.040 |

**There is not one cross-event date-ladder pair inside 90 days.** Kalshi
lists near-dated date ladders as *sibling markets within a single event*
(`KXGROK-GROK5` carries "Before July" and "Before October" as siblings on
one page), which is the exact opposite of the spec's premise. Those
siblings sit on the same page, get compared by the same crowd, and are
priced **exactly consistently**: the minimum cost across all 295 near-dated
pairs is 1.000, never below.

Cross-event ladders — the ones the premise correctly describes as
uncompared — exist only at **1+ year** horizons, where the best violation
observed (0.980 gross) is dwarfed by years of carry.

Two conclusions follow, and together they close the theory:

1. Where the arbitrage would be worth taking (near-dated), the pairs are
   same-event and perfectly priced — and same-event nesting is already
   `structural_arb`'s territory, not a new lens.
2. Where the premise holds (cross-event), the horizon is measured in years
   and the mispricing in tenths of a cent per year.

## Verdict

**Do not build calendar-arb as specced.** Recorded against idea 21 as
`dead`, with the revisit angle below. This cost one session-hour and saved
building an effort-S theory that cannot fire.

## Revisit angle — the v2 is untouched by this

The spec's own deferred v2 — *soft* relative value, where a later deadline
trades implausibly close to an earlier one, implying an absurd conditional
hazard — is a **forecast** theory, not an arbitrage. It needs no hard
violation and is therefore completely unaffected by everything above.

It is also unusually well-supplied: the 295 near-dated same-event pairs
sitting at exactly cost 1.000 are a ready-made dataset for asking whether
the *implied conditional hazard* between two deadlines is ever absurd. That
is a real question this study does not answer and did not try to.

Anyone picking it up should treat it as a new theory with its own
pre-registration, not as calendar-arb v2 — the mechanism, the evidence, and
the risk profile all differ.

## Limits

- Four days of snapshots, all within one week. A rare violation regime
  (a mispriced ladder appearing after a news shock) would not show up.
  The Result 2 structural finding does not depend on the window, though:
  it is about how Kalshi *lists* these markets.
- The deadline is proxied by `close_time` rather than parsed from rules
  text. For genuine ladders these agree; a series where they diverge would
  be misordered, which would create false positives, not hide real ones.
- Title-regex subject matching is coarser than the rules-text classifier
  the spec asks for. It is deliberately *over*-inclusive (1,944 pairs from
  325 families), so it cannot be hiding violations by under-matching.

Note (2026-08-30): re-running this probe against post-compression snapshot rows requires routing raw_json/event_json reads through tools.snapshot.payload_text (spec 5.2 phase 3).

---

# Addendum 2026-09-01 — re-run on correctly reconstructed boards

*Maintenance lane, session `fleet-w3-g2`, ticket
`calendar-arb-probe-exact-stamp-board`. Facts only: this addendum does
**not** revisit the verdict, which stands. `probe.py` is left exactly as
run; `probe_as_of.py` supersedes it and produced everything below. Raw
output: `data/rerun-2026-09-01-board-as-of.txt`.*

**What was wrong.** `probe.py` rebuilds each board with
`WHERE captured_at = ?`. Dedup-on-write (spec 5.2 phase 2, 2026-08-30)
means a pull writes no row for a market whose payload did not change, so
that query returns *the markets that moved at that pull*. The probe ran on
2026-08-27, before dedup, so **its published numbers were correct when
made** — but every capture it walked is now re-read short, and the
truncation is severe and biased toward liquid markets:

```
2026-08-27T11:47:05Z    exact  3,254 markets    as_of 107,656 markets
2026-08-27T11:46:17Z    exact 19,005           as_of 107,660
2026-09-01T11:34:32Z    exact  5,580           as_of 103,940
```

**Result 1 changes as stated, and does not change as concluded.** Over the
20 captures now stored, on correctly reconstructed boards:

```
snapshots=20   pairs checked=38,124   violations=25   cross-event=22
median profit/basket=0.0134
```

So "the firing rate is zero" is **no longer literally true** and should be
read as *"~7 violations per 10,000 ladder pairs, none of them near-dated."*
What the violations are matters more than the count:

- **19 of 25 are one recurring pair**, `KXDECLAREPRESFIRSTD-28NOV07-KHAR`
  against `-28NOV01-KHAR`, at +0.004 to +0.023 per basket on a **2028**
  horizon. That is two years of carry for one to two points, which is the
  study's own Result 2 argument, not a counter-example to it.
- **3 are `KXTRUMPSAYMONTH` pairs whose NO leg asks 0.01.** A one-cent ask
  is the placeholder-quote trap this repo has now hit in three separate
  studies (the mirror image of the 0.980–0.995 artifact that made the
  series-bias pass-3 unreadable). Treat as artifact until depth is checked.
- The four earliest captures (2026-08-24) still return **zero** on the
  corrected board.

**Result 2 has NOT been re-derived, and that is the open piece.** The 295
near-dated same-event pairs at min cost 1.000 — the structural finding that
actually closes the theory, and the dataset
`tickets/new-theory/open/2026-09-01-calendar-arb-soft-relative-value.md`
proposes to reuse — came from a separate horizon/scope tabulation that
`probe.py`'s `main()` does not compute, so `probe_as_of.py` does not
reproduce it either. It was measured on a board that was **~90k markets
short**. Whoever picks up the soft-relative-value ticket must re-derive that
table before leaning on the 295 figure; ticketed.

**Verdict unchanged: do not build the spec as written.** Nothing here
disturbs it — the violations that appeared are long-dated or one-cent-ask,
which is what Result 2 predicts. What changed is that the zero is not a
zero, and one of the two supporting tables is unverified.
