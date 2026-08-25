# Multi-Leg Positions — Baskets in the Ledger

Date: 2026-08-24
Status: **implemented, with one blocking decision open — see below**
Implemented on branch `feat/multi-leg-positions` (15 commits, 522 tests
passing). Scope: `db/schema.sql`, `tools/db.py`, `tools/ledger.py`,
`tools/score.py`, `tools/cli.py`, `.claude/skills/score-theories/SKILL.md`
Prerequisite for:
[theory-layer OOP](2026-08-24-theory-layer-oop-design.md) — see section 8

**In one line:** three backlog theories bet on *baskets* of markets whose
payoff is joint, and the ledger can only store one leg per row — so their
edge would be recorded as several independent bets that it is not.

---

## ⛔ BLOCKING DECISION — read before building any basket theory

**A basket whose payout can land strictly between $0 and its declared
`max_payout` currently RAISES at scoring time. This is deliberate. It stays
that way until someone decides the question in section 10.1.**

`calendar-arb` is exactly such a theory, so **it cannot accrue any evidence
today**. `structural-arb`'s NO-basket and any other all-or-nothing basket
work normally and are unaffected.

Nothing is silently wrong — the guard exists precisely so a wrong number
can never be recorded. But do not build `calendar-arb`, and do not relax the
guard, until section 10.1 is answered and this spec is amended. The error
message points here by path.

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

**This section is about the *claimed* edge, and that distinction is where
the gap in section 3.5 came from.** `edge_pts_net` above is what a theory
computes when it proposes a bet. It is a different quantity from
`calibration_edge`, which scoring computes *afterwards* as
`(win_rate − price_implied_rate) × 100` to measure whether the theory's
claims came true. The claimed edge does generalize cleanly, exactly as
described here. The *measured* one does not, because a basket has no obvious
`price_implied_rate` — and this spec never noticed it had only specified
one of the two. Section 3.5 documents the consequence; section 10.1 is the
decision that resolves it.

### 3.3 Schema

`opportunities` gains three columns and keeps every existing one:

```sql
position_kind  TEXT NOT NULL DEFAULT 'single'
               CHECK (position_kind IN ('single','basket')),
leg_count      INTEGER NOT NULL DEFAULT 1,
max_payout     REAL NOT NULL DEFAULT 1.0,
```

`max_payout` was added during planning, after this section was first
written: a NO-basket over `k` outcomes pays `$(k−1)`, and without a declared
maximum there is nothing to normalize `implied_rate` against. It must be a
positive number — `record_basket` rejects `None`, non-numeric values, `bool`,
`NaN`, zero, and negatives, because a basket that can never pay anything is
not a position. Note that section 10.1 turns on what this column means, so a
decision there may change how it is declared.

`ALTER TABLE ADD COLUMN` cannot carry a CHECK, so a database migrated in
place enforces `position_kind`'s domain in application code only — see
section 10.3.

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

**Gap found in implementation — this section was incomplete.** The four
lines above define `payout`, `profit`, `won`, and `roi`, but never define
`implied_rate` — the price-side quantity `calibration_edge` compares the
realized win rate against. A single position contributes its `entry_price`,
which *is* the market's implied probability of the event `won` measures. A
basket has no such obvious analogue, and the spec never supplied one.

The implementation chose `implied_rate = cost / max_payout`. That is
correct **only** when the basket is all-or-nothing, because then
`won` ⟺ `payout == max_payout` and the two quantities describe the same
event. When a basket has a payout floor they describe different events, and
`calibration_edge_net` inflates badly:

| position | cost | pays | ROI | recorded `calibration_edge_net` |
|---|---|---|---|---|
| single | 0.95 | 1.00 | 4.90% | 4.67 pts |
| basket, `max_payout=2.0` | 0.95 | 1.00 | 1.76% | **50.86 pts** |

Identical economics, an order of magnitude apart, in the number every theory
is ranked by. Section 10.1 is the decision that closes this.

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

Status as implemented on `feat/multi-leg-positions`:

1. ✅ Every existing test passes, none weakened; single-leg scores on a copy
   of the live database are identical before and after. Verified twice
   independently, once across 160 segments against real data.
2. ⛔ **Unmet, and blocked on section 10.1.** A two-leg `calendar-arb`
   basket records as one position and settles jointly, but only one of its
   three branches can be *scored* — the other two pay a $1 floor against a
   $2 maximum and raise. This is the honest state, not a defect to paper
   over: the alternative was recording an edge inflated by an order of
   magnitude.
3. ✅ A basket contributes exactly one observation to `n`.
4. ⚠️ Deferred by design. `Candidate.ticker` does not exist — `tools/
   domain.py` belongs to the [OOP migration](2026-08-24-theory-layer-oop-design.md),
   which runs after this and adopts the `Leg` shape defined here. The
   equivalent guarantee is enforced at the ledger instead.
5. ✅ A basket with a missing or unsettled leg is excluded rather than
   scored partially, and a `leg_count` mismatch raises.
6. ⚠️ Three columns, not two — `max_payout` was added during planning
   because a NO-basket paying `$(k−1)` cannot be normalized without it.
   `settlements` is unchanged as promised, and `Leg` is a plain dict until
   the OOP migration types it.

Beyond the original list, implementation added two guarantees this spec did
not ask for and should have:

7. ✅ Settlement discovery resolves a basket through its **leg** tickers.
   The original design would have quoted the synthetic `BASKET:<hash>` to
   Kalshi, so no basket could ever have settled.
8. ✅ Duplicate `(ticker, outcome)` legs are refused. Without it a basket
   could fabricate a payout above its declared maximum.

## 10. Open questions

### 10.1 ⛔ BLOCKING — how is a variable-payout basket scored?

**This is the decision that unblocks `calendar-arb`. Nothing else in this
spec is waiting on anything.**

**The question:** for a basket that does not pay all-or-nothing, what is
`implied_rate` — the price-side quantity `calibration_edge` compares the
realized win rate against? Section 3.5 documents why the current answer
(`cost / max_payout`) is wrong for this case.

Note this is **not** a bug to fix by picking whichever formula looks
tidiest. It decides what `calibration_edge_net` *means* for a whole class of
positions, and that number is what `rank.py` uses to weight every theory
against every other. It is a research-design call.

**Three ways it could go, none of them obviously right:**

1. **Restrict baskets to all-or-nothing.** Keep the current guard
   permanently, document that a basket must pay `0` or `max_payout`, and
   require `calendar-arb` to be expressed differently or dropped.
   *Cost:* loses a theory the spec's own section 1 names as motivating.
2. **Score variable-payout baskets on ROI rather than calibration.** A
   position with a guaranteed floor has no meaningful "win rate" — it always
   wins. Give such baskets `edge_basis="model"`, an ROI-based track record,
   and exclude them from `calibration_edge` entirely.
   *Cost:* two scoring regimes; `compare-theories` must not pool them.
3. **Redefine `implied_rate` as `cost / E[payout]`.** Requires the theory to
   declare an expected payout, not just a maximum — which for `calendar-arb`
   means declaring branch probabilities, which is exactly the introspected
   number CLAUDE.md forbids unless it comes from base rates.
   *Cost:* pushes a hard modelling problem onto every basket theory.

**Until it is answered:** `_basket_observations` raises on any basket whose
payout is neither `0` nor `max_payout`, naming the opportunity, both
figures, and this file. `tests/test_baskets.py` pins that behavior in
`test_nesting_branch_with_a_payout_floor_is_unsupported_and_raises` — when
the decision lands, that test becomes the assertion of whatever it decides,
rather than being deleted.

### 10.2 Resolved during implementation

1. **NO-basket payout.** `structural-arb`'s `sum(NO asks) < (k−1) − fees`
   pays `$(k−1)`, not `$1`. Section 3.5's `payout` computation handles this
   by summing per-leg payouts. The exhaustiveness of the mutually-exclusive
   set remains a theory-level guard, not a ledger-level one. **Note this is
   an all-or-nothing basket, so it is unaffected by 10.1.**
2. **Fees on a basket — RESOLVED.** Kalshi charges per contract:
   `tools/sizing.py:fee_pts` is documented as the per-contract fee and
   `order_fee_dollars(price, contracts)` scales by count. Summing `fee_pts`
   per leg is correct. Implementation additionally divides the total by
   `max_payout` so fees share `implied_rate`'s scale — if 10.1 changes that
   scale, this divisor changes with it.

### 10.3 Still deferred

1. **Partial user fills.** If the user takes two legs of a three-leg basket,
   `mark-taken` records one size for the position. Whether that needs
   per-leg user actions is deferred until a real basket is taken —
   speculating now would build a schema nobody has needed.
2. **`position_kind` CHECK on migrated databases.** SQLite cannot add a
   CHECK via `ALTER TABLE`, so databases migrated in place enforce the
   domain in application code only. Latent: `ledger` is the only writer and
   always writes a literal. Revisit if the table is ever rebuilt.
3. **Baskets and bucket rates.** `score.bucket_rates` now explicitly filters
   `position_kind = 'single'`, because a basket header's ticker is synthetic
   and never matches a settlement. Baskets therefore contribute nothing to
   the confidence-bucket win rates `tools/buckets.py` converts into
   probabilities. Correct today — baskets carry `edge_basis="model"`, not
   `"measured"` — but it must be revisited if a basket theory ever wants a
   measured bucket.
