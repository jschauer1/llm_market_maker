# Multi-Leg Positions — Baskets in the Ledger

Date: 2026-08-24
Status: design approved, implementation not started
Scope: `db/schema.sql`, `tools/ledger.py`, `tools/score.py`, `tools/cli.py`
Prerequisite for:
[theory-layer OOP](2026-08-24-theory-layer-oop-design.md) — see section 8

**In one line:** three backlog theories bet on *baskets* of markets whose
payoff is joint, and the ledger can only store one leg per row — so their
edge would be recorded as several independent bets that it is not.

## 1. Problem

`opportunities` stores exactly one position per row
(`db/schema.sql:81-83`):

```sql
kalshi_ticker  TEXT NOT NULL,
outcome        TEXT NOT NULL,
entry_price    REAL NOT NULL,
```

and scoring joins one row to one settlement (`tools/score.py:89`):

```sql
FROM opportunities o
JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker
```

Three theories in the backlog do not produce single positions:

| Theory | Position | Legs |
|---|---|---|
| `structural-arb` | `sum(YES asks) < 1 − fees`; ask-side monotonicity | 2..N |
| `calendar-arb` | `ask(YES, later) + ask(NO, earlier) < 1 − fees` | 2 |
| `implication-graph` | `ask(A_yes) + ask(B_no) < 1 − fees` | 2 |

Their thesis is a **joint** payoff. `calendar-arb`'s spec works through the
payoff matrix explicitly and concludes the basket "pays ≥ $1 in all three
[outcome branches] exactly when nesting holds." That claim is about the
basket. It is not a claim about either leg.

Recorded as N separate rows, scoring counts N independent bets, each won or
lost on its own — which is not merely imprecise but *directionally wrong*.
A nesting-violation basket that pays exactly $1 has one winning leg and one
losing leg; scored separately that is a 50% win rate and a mediocre ROI,
when the actual position returned `$1 − cost` with certainty. The theory
would look worthless while being a riskless arbitrage.

Recorded as one row for the "primary" leg, the other legs vanish and the
recorded `entry_price` understates what was actually paid.

Both failure modes corrupt `calibration_edge_net`, which is the number every
theory is ranked by.

### 1.1 Why this matters more than three theories

These are the theories CLAUDE.md most wants: pure arithmetic,
`edge_basis="model"`, no LLM in the decision path, tier A backtests from day
one. *"Sibling-strike monotonicity violations, a NO-basket summing below its
payout"* are the document's own examples of edges a script decides with no
model in the loop.

The specs already sense the gap without naming it — `structural-arb` warns
that "by the time the user places leg 3, legs 1–2 may have moved" and
`calendar-arb` says "the report should present both legs with explicit
instructions" — but neither says how the ledger stores one, because it
cannot.

## 2. Non-goals

- **No change to single-leg behavior.** Thirteen of twenty-two backlog
  theories and both existing theories are single-leg. Every existing row,
  query, and score stays exactly as it is; this is additive.
- **No execution modelling.** Leg-by-leg fill risk is real (see section 7.3)
  but is reported to the user, not simulated. The user places every bet
  manually.
- **No portfolio or correlation layer.** A basket is one position. Grouping
  positions across theories is a different problem and is not started here.
- **No change to `settlements`.** Legs settle individually, keyed by ticker,
  exactly as today. What changes is how a basket's payoff is *computed* from
  them.

## 3. Design

### 3.1 A position has legs

The value type (lands in `tools/domain.py`, per the OOP spec):

```python
@dataclass(frozen=True, slots=True)
class Leg:
    market: Market
    side: str            # "yes" | "no"
    price: float         # the ask actually payable for this leg

@dataclass(frozen=True, slots=True)
class Candidate:
    legs: tuple[Leg, ...]
    days_to_close: float

    @property
    def is_basket(self) -> bool:
        return len(self.legs) > 1

    @property
    def cost(self) -> float:
        return sum(leg.price for leg in self.legs)

    @property
    def ticker(self) -> str:
        """Single-leg convenience. Raises on a basket."""

    @property
    def entry_price(self) -> float:
        """Single-leg convenience. Raises on a basket; use .cost."""
```

**One type, no second-class path.** A single position is the one-leg case,
so the thirteen single-leg theories are unaffected in substance.

The accessors that cannot mean anything for a basket **raise** rather than
return `legs[0]`. Silently returning the first leg is precisely the bug this
spec exists to prevent, and it would be invisible — the same
"impossible rather than discouraged" principle `record_opportunity` already
applies to provenance.

### 3.2 The edge formula generalizes rather than forking

For a single position the existing formula is
`edge = (P(win) − entry_price) × 100 − fees`.

For a basket, `cost` replaces `entry_price` and the payout replaces the
implicit `$1`:

```
edge_pts_net = (E[payout] − cost) × 100 − fee_pts(all legs)
```

A single leg is the case where `E[payout] = P(win) × $1` and
`cost = entry_price`. Nothing forks; the single-leg path computes the same
number it computes today, which is what keeps section 6's golden files
green.

For the arbitrage theories `E[payout]` is not a probability estimate at all
— it is `$1` (or `$(k−1)` for a NO-basket) by construction whenever the
structural claim holds. That is why they carry `edge_basis="model"`: the
model is arithmetic.

### 3.3 Schema

`opportunities` gains two columns and keeps every existing one:

```sql
position_kind  TEXT NOT NULL DEFAULT 'single'
               CHECK (position_kind IN ('single','basket')),
leg_count      INTEGER NOT NULL DEFAULT 1,
```

New table:

```sql
CREATE TABLE IF NOT EXISTS opportunity_legs (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id)
                   ON DELETE CASCADE,
    leg_index      INTEGER NOT NULL,
    kalshi_ticker  TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    entry_price    REAL NOT NULL,
    spread_at_call REAL,
    volume_at_call REAL,
    PRIMARY KEY (opportunity_id, leg_index)
);

CREATE INDEX IF NOT EXISTS idx_opportunity_legs_ticker
    ON opportunity_legs (kalshi_ticker);
```

For a basket the header row carries the aggregate: `entry_price` is the
basket `cost`, `edge_pts_net` is the basket edge, `leg_count` is N.

**Single-leg rows do not get leg rows.** `position_kind='single'` with
`leg_count=1` means the header *is* the position, exactly as today. Writing
one leg row per single position would double the table for no gain and would
force every existing query to change. This is the one asymmetry in the
design and it is deliberate: it is what makes the change additive.

### 3.4 The basket's `kalshi_ticker`

CLAUDE.md requires every suggestion to resolve to a specific Kalshi ticker,
and the column is `NOT NULL`. A basket resolves to several.

The header carries a deterministic synthetic key:

```
BASKET:<first 16 hex of sha256 of "ticker:side" for each leg, sorted>
```

and the **tradeability guarantee moves to the legs**: `record_opportunity`
requires at least one leg and a real, non-empty ticker on every one. The
guarantee is unchanged in force, just asserted at the granularity where it
is true.

Determinism matters for the existing dedup rule. The `UNIQUE (theory_id,
theory_version, run_id, kalshi_ticker, outcome)` constraint is what makes
re-sighting the same thesis update a row rather than insert one — CLAUDE.md:
"a market that stays mispriced for a week is one bet seen seven times, not
seven bets." A hash over sorted legs gives the same basket the same key on
every scan, so that property carries over unchanged. `outcome` for a basket
header is the literal `'basket'`.

### 3.5 Settlement and scoring

`settlements` is untouched — legs resolve individually by ticker.

`compute_score` gains a basket branch. A basket is **one observation**, and
it is settled only when **every** leg has settled; a partially-settled
basket is excluded exactly as an unsettled single position is.

```
payout  = sum($1 for each leg whose settlement matches its outcome)
profit  = payout − cost − fees
won     = profit > 0
roi     = profit / cost
```

`won` for a basket means *the position made money*, which is the honest
analogue of a single position resolving your way. A basket that pays exactly
its cost is not a win.

The existing single-leg SQL path is unchanged. The basket path is a separate
aggregate query unioned into the same result set, so `n`, `win_rate`, and
`roi_all` count one basket once.

## 4. What the theories get

- `structural-arb` — records a NO-basket or a monotonicity pair as one
  position with its true cost, and settles jointly. A basket that would have
  lost becomes detectable, which is the audit `calendar-arb` asks for: "any
  basket that would have lost is a classifier bug."
- `calendar-arb` — the two-leg nesting position is one row; the payoff-matrix
  claim in its spec becomes a testable property of a settled basket.
- `implication-graph` — same, across two events.
- Every other theory — unchanged.

## 5. Migration plan

Three phases, each independently green.

| # | Phase | Touches | Behavior change |
|---|---|---|---|
| 0 | Schema + `Leg`/basket write path | `schema.sql`, `ledger.py` | none for single-leg |
| 1 | Basket settlement and scoring | `score.py` | none for single-leg |
| 2 | CLI and reporting | `cli.py` | additive output only |

`db.py` already reads `CREATE TABLE IF NOT EXISTS` statements out of
`schema.sql`, so adding a table follows the existing path. The two new
`opportunities` columns need an `ALTER TABLE` in the migration helper, both
with defaults that make every existing row correct as written
(`'single'`, `1`) — no backfill, no rewrite.

## 6. Testing

**Non-regression is the primary claim**, exactly as in the OOP spec:

- The existing suite passes with nothing deleted, skipped, or weakened.
- `tests/test_ledger.py` and `tests/test_score.py` are the characterization
  set here: every single-leg assertion must hold byte-for-byte, because the
  single-leg path is not supposed to change at all.
- A pre/post score comparison on a copy of the live database must be
  identical.

**New tests:**

- `Candidate.ticker` and `.entry_price` raise on a basket, and the message
  names `.cost` / `.legs` as the fix.
- A basket writes one header plus N leg rows; `leg_count` matches.
- Re-recording the same basket updates rather than inserts (the synthetic
  key is stable across scans and leg orderings).
- A basket with any leg unsettled is excluded from scoring.
- A fully-settled basket contributes exactly one observation.
- **The `calendar-arb` payoff property:** construct a nesting-valid two-leg
  basket, settle it through all three outcome branches, and assert
  `payout ≥ $1` in each — the end-to-end audit that spec asks for.
- A basket whose legs sum to more than its payout scores as a loss, proving
  the arithmetic is not assumed.
- `record_opportunity` refuses a basket with zero legs, or any leg with an
  empty ticker.

## 7. Risks

### 7.1 Silent leg loss — highest severity

The failure this spec exists to prevent is also the one it could introduce:
a basket written with a leg dropped looks like a valid, cheaper position and
nothing complains. `leg_count` on the header is the guard — it is written
from the `Candidate`, and a scoring-time check that `leg_count` equals the
number of leg rows raises rather than scoring a partial basket.

### 7.2 Double-counting a basket's legs

If any future query joins `opportunity_legs` to `settlements` without
grouping by `opportunity_id`, a basket contributes N observations and the
bug looks like a suspiciously large `n`. Mitigation: scoring never reads leg
rows except through the aggregate path, and a test asserts `n` counts a
basket once.

### 7.3 Execution risk is real and is not modelled

`structural-arb` states it plainly: by the time the user places leg 3, legs
1–2 may have moved. A basket edge that assumes simultaneous fills overstates
what is achievable manually.

This is **not** simulated here. It is reported: a basket suggestion carries
every leg with its own ask and top-of-book size, plus an explicit
verify-all-legs-before-entering instruction. Recording a modelled edge the
user cannot actually capture would be exactly the dishonesty `edge_basis`
exists to prevent, so the honest position is to report the arithmetic edge
and let the user see the legs.

### 7.4 Scope creep into portfolio management

Baskets invite correlation limits, shared-leg caps, and position netting.
`parlay-fade` already asks for one ("max concurrent combos sharing any
single leg"). None of that is in scope; a basket is one position and nothing
here reasons across positions.

## 8. Relationship to the OOP migration

**This spec is executed first**, for a specific reason rather than
preference.

The OOP migration's entire safety argument is *no behavior change, proven by
golden files*. A schema change plus new settlement logic **is** a behavior
change. Folding it into that migration would forfeit the one property that
makes the refactor reviewable, and would leave no clean signal to escalate
on if a golden diff appeared.

It must also come first because `Candidate`'s shape depends on the outcome.
Designing `Candidate` as a single market and retrofitting legs afterwards
means changing the type underneath two already-ported theories, which is
strictly more work and more risk than designing it with legs from the start.

The OOP spec's section 4.1 therefore adopts the `Leg` / `Candidate.legs`
shape defined here, and its section 3.1 non-regression list gains the
single-leg score parity requirement from section 6.

**Cheaper interim, if this is deferred:** baskets record as single
`disposition='screened'` rows with the legs in `extra_json` and are simply
not scored. That is honest and non-corrupting — nothing enters the
calibration math wrongly — but it leaves the three arbitrage theories
unable to accrue evidence, which is most of their value.

## 9. Success criteria

1. Every existing test passes, none weakened; single-leg scores on a copy of
   the live database are identical before and after.
2. A two-leg `calendar-arb` basket records as one position, settles jointly,
   and satisfies the payoff property in all three outcome branches.
3. A basket contributes exactly one observation to `n`.
4. `Candidate.ticker` on a basket raises with a message naming the fix.
5. A basket with a missing or unsettled leg is excluded from scoring rather
   than scored partially.
6. No change to `settlements`, and no new concept beyond `Leg`, two columns,
   and one table.

## 10. Open questions

1. **NO-basket payout.** `structural-arb`'s `sum(NO asks) < (k−1) − fees`
   pays `$(k−1)`, not `$1`. Section 3.5's `payout` computation handles this
   naturally by summing per-leg payouts, but the exhaustiveness of the
   mutually-exclusive set is an assumption the theory must verify — it is a
   theory-level guard, not a ledger-level one. Confirmed at implementation.
2. **Fees on a basket.** `tools/sizing.py:fee_pts` is per-contract; a basket
   pays fees per leg. Phase 0 confirms summing per-leg fees is correct
   against Kalshi's published fee schedule rather than assuming it.
3. **Partial user fills.** If the user takes two legs of a three-leg basket,
   `mark-taken` currently records one size for the position. Whether that
   needs per-leg user actions is deferred until a real basket is taken —
   speculating now would build a schema nobody has needed.
