# structural_arb — lab notebook

Append-only. Raw observations, dead ends, data quirks. Distill into
THEORY.md only what changes the claim, the procedure, or the status.

## 2026-08-26 — born

Implemented from the 2026-08-24 backlog spec (priority 3/22, composite
11/15). Design decisions made while implementing, beyond the spec:

- **NO-floor insight**: mutual exclusivity alone (no exhaustiveness)
  gives the NO-basket a payout floor of k−1 — "at most one YES" is
  enough. So the basket-sum check does not need the untestable
  exhaustiveness claim at all on the NO side, and the YES side (which
  does need it) was dropped from v1 rather than built on an assumption.
- Kalshi's event envelope `mutually_exclusive` is real and load-bearing:
  first probe (BEYONCEGENRE-30, 9 siblings) came back `false` — a NO
  basket there would NOT have a k−1 floor. The flag check earns its
  fetch.
- `between` closure is unverifiable from the API (caps like 50999.99
  suggest inclusive bounds with tick gaps, but nothing states the tick).
  All proofs touching a `between` endpoint therefore demand strict
  inequality; the tick-gap "adjacent bands" exhaustiveness proof was
  considered and rejected for v1.
- Same-market YES+NO ask sum < 1 is impossible by construction on Kalshi
  (one book: yes_ask ≡ 1 − no_bid), so that classic check is omitted;
  any hit would be a data error, not an arb.
- Strike-type census on the 2026-08-26 board (108,820 open markets):
  structured 37,460 · greater 31,703 · custom 19,450 · greater_or_equal
  11,696 · none 5,082 · between 2,950 · less 451 · less_or_equal 28.

## 2026-08-26 — first live run: two proof bugs caught by their own output, one real find

The first naive live scan "found" 177 geometry violations; every one was
wrong or unverifiable, and the wreckage was more valuable than a win:

- **Bug 1 (harness): HTTP 414.** Re-quoting 3,438 tickers in one GET
  died, and the exception path silently dropped everything as
  stale_quote. Fix: 100-ticker chunks, per-finding re-decision
  (`scan.refresh_finding`), fetch-failure counted separately.
- **Bug 2 (proof): one event ≠ one underlying.** Top "finds" paired
  Brian Serven's 1+ hits with Darell Hernaiz's 2+ hits — numerically
  nested floors over unrelated quantities. Fix: underlying groups
  (strike-token tail + digit-masked title equality).
- **Bug 3 (data): exact-value markets mislabeled.** KXSTARSHIPSPACE-26
  "-8.0" says `less` floor=cap=8 but means "exactly 8"; believing it
  produced a fake arb (cost 0.53, "floor" 1.0) that actually pays 0
  whenever the launch count lands between the strikes. Fix: one-sided
  types carrying both bounds are refused. **This one would have lost
  real money — it survived live re-quote, because the quotes were
  right and the metadata was lying.**

After the fixes: 108,820 markets → 2,889 scalar events with a provable
multi-strike group → 1 nested-pair violation surviving live re-quote:
KXNASDAQ100MINY-26DEC31H1600 T22800.01 YES @ 0.07 + T22600.01 NO @
0.86, cost 0.943 with fees against a $1.00 floor / $2.00 mid-branch —
+6.0% riskless, +112% if the 2026 Nasdaq-100 low lands between the
strikes. Same-instant issuance (2026-04-20T18:30Z), identical rules
text modulo the threshold. Recorded as opp 9248. Snapshot replay shows
this pair crossed since at least Aug 24 20:21Z (then 9.95c/basket) —
violations here decay in days, not seconds, which is what a manual
workflow needs.

Flag path: all 1,291 arithmetic candidates on today's board fetched and
persisted to theory_facts — **zero are mutually_exclusive**. Cheap
NO-sums live almost entirely in multi-outcome events, exactly the trap
the flag gate exists for. Future boards get these lookups for free.

Snapshot replay (tier A, run backtest-2026-08-26-structarb-snap, no
ledger rows — existence only): 6 snapshots Aug 24–27, findings
1/3/3/3/1/2. USCLIMATE-2025/2030 (2.2–4.2c) and KXNCAAMBWINS-26SJU
24/27 (3.5c) existed Aug 24, gone by Aug 27.

Open v2 ideas: cross-event date-ladder nesting belongs to calendar-arb
(idea 21), not here; YES-basket needs an exhaustiveness source; the
underlying-key could use `yes_sub_title` masking to recover date-strike
ladders the token rule drops.

## 2026-08-27 (same session) — depth post-mortem on opp 9248: real, riskless, and 32 cents deep

Orderbook check (GET /markets/{t}/orderbook -> `orderbook_fp`,
price/size lists in dollars): the YES leg @0.07 has ~61 contracts, but
the NO leg @0.86 rests against a 0.32-contract dust YES bid at 0.14 —
next level implies NO @0.99, which un-crosses the pair. Fillable
profit: ~$0.30 total. Interpreted the row rejected with the depth
rationale. Mystery of the multi-day persistence solved: nobody cleans
up an arb worth thirty cents.

Lesson for the theory: top-of-book existence (what the screen measures,
what the spec scoped v1 to) and fillable size are different claims, and
the gap between them was 200x here. v2 candidate: fetch orderbooks for
finalists only (a handful per session), compute depth-aware fillable
size and profit, and put both in the rationale; a min-fillable-profit
threshold would be a decision-path change -> version bump. Session
judgment covered it this time — exactly the "pipelines propose,
judgment disposes" split — but the check is mechanical and belongs in
stage 1 eventually. Also learned: the orderbook endpoint's schema is
`orderbook_fp.{yes,no}_dollars` = resting BID lists (asks are implied
from the opposite side), size is fractional-contract decimal.

## 2026-08-27 — v2: the depth gate goes mechanical

Session re-ran the v1 scan on today's board (107,656 markets): 1
survivor, KXNCAAMBWINS-26SJU 24/27 nested pair back again at 4.8%
riskless floor (it existed Aug 24, vanished, returned). Orderbook check:
the NO-27 leg rests against a 0.47-contract YES bid at 0.50; next level
0.02 implies NO @0.98, un-crossing the pair. Fillable riskless profit
~$0.02. Recorded opp 9309 and interpreted it rejected by hand — the
second consecutive live finalist killed by exactly the depth check
NOTES sketched as a v2 candidate yesterday (9248: ~$0.30 fillable).

Two-for-two is enough: promoted the heuristic into stage 1 as v2
(TDD; 10 new tests, 701 repo-wide green). Design:

- `scan.implied_ask_ladder(fp, side)` — the API's `orderbook_fp` lists
  resting BIDS; buying a side lifts the opposite side's bids, so the
  ask ladder is `1 - opposite_bid` at that bid's size, cheapest first.
- `scan.fillable_floor(ladders, min_payout)` — lockstep greedy walk:
  the marginal basket always fills at every leg's cheapest remaining
  level, so greedy is exact; stop when marginal cost + unrounded fees
  reaches the floor payout or a ladder runs out.
- `theory.price()` (live only): fetch each finalist leg's book (20/run
  budget, per-ticker cache), compute (baskets, $), put both in the
  rationale. < $5 fillable → `disposition="rejected"` (recorded — the
  dust finds are a free control group that settles). Unreadable book →
  screened + `Depth UNVERIFIED`, the v1 behavior made explicit.
- Backtest path untouched: snapshots carry no orderbooks, so tier-A
  replays keep measuring existence only, as THEORY.md already stated.

Validation: re-ran live under v2 — same find, mechanically rejected
with the same numbers the manual check produced (~0.47 baskets,
~$0.02), recorded as opp 9310 (v2's own row). Version bumped in code
and registry; drift tests forced the registry fixture update, which is
the system working.

Fee note for the walk: fees are computed per level price, so a deeper
(more expensive) level pays a different fee — the marginal-basket
riskless test is exact per level, not an average.

Still open for v3: nothing new. The remaining v2 ideas from yesterday
(YES-basket exhaustiveness source, `yes_sub_title` masking for date
ladders) stand; cross-event date ladders remain calendar-arb's.

## 2026-08-27 (evening) — third consecutive find is the same pair; v3 should remember

Re-ran v2 against tonight's fresh board (110,399 markets, pulled 23:18Z —
11h newer than this morning's 107,656). Funnel: 11,602 multi-outcome
events → 3,099 scalar → 1 nested raw violation → 1 geometry finding;
1,447 flag candidates all removed as `not_mutually_exclusive`, 0 confirmed.

**1 survivor, and it is the same pair for the third run running:**
`KXNCAAMBWINS-26SJU` 24/27, YES-24 @ 0.42 + NO-27 @ 0.50 = 0.92 + 0.0346
fees against a guaranteed 1.00 floor → 4.8% riskless at top-of-book.
Depth gate: **~0.47 baskets fillable, ~$0.02 floor profit**, below the $5
floor → recorded `rejected` (opp 9311). Identical numbers to opp 9310 this
morning and to the hand-check on 9309 before that.

So the gate is working exactly as designed and the theory is behaving
correctly. But the *reporting* is now misleading in a small way worth
fixing: each session's scan announces "1 survivor" as though it found
something, when it is re-finding a known, persistently-dust pair. Three
sessions have each spent an orderbook fetch and a ledger row on it.

**v3 candidate — dust memory.** Before the depth fetch, check whether this
exact leg-set has been rejected for depth before and how recently; if so,
either skip the fetch and re-record cheaply, or fetch but report it as
"known dust, unchanged" rather than as a new finding. The ledger already
holds what is needed (`opportunity_legs` + `disposition='rejected'` +
rationale), so this is a query, not new storage. Care needed on one point:
a pair that was dust yesterday can legitimately gain depth today, so the
memory must never *suppress* the check — only change how it is fetched and
reported. That distinction is the whole design.

Not doing it tonight; recorded as idea `arb-dust-memory` so it does not
get rediscovered a fourth time. No version bump — nothing about the
decision procedure changed.

## 2026-08-29 — third consecutive run, third depth-gate kill

Live run `live-2026-08-29` against the session's 117,272-market board.
Funnel: 12,616 multi-market events → 3,577 scalar events → 4 raw nested
violations → 3 geometry findings → 3 survivors. Gate removed 1,490
not-mutually-exclusive events and capped 37 flag fetches; 1,527 flag
candidates checked, **0 confirmed**.

All three survivors rejected mechanically by the v2 depth gate:

| position | apparent riskless | fillable | floor profit |
|---|---|---|---|
| `KXWTAGTOTAL-26AUG30RAKKRE` 15/20 (YES 0.13 / NO 0.42) | 73.9% | ~0.01 baskets | ~$0.00 |
| `KXWTAGTOTAL-26AUG30GIBVEK` 18/23 (YES 0.13 / NO 0.56) | 39.8% | ~0.01 baskets | ~$0.00 |
| `KXNCAAMBWINS-26SJU` 24/27 (YES 0.42 / NO 0.50) | 4.8% | ~0.47 baskets | ~$0.02 |

The two WTA games-total pairs are new and instructive: both are US Open
first-round matches listed 2026-08-27 with essentially no trading
(volume 0.11 and 0.0), so top-of-book is a market-maker's opening quote
that has never been tested. An untraded ladder is the *cheapest* place to
find an apparent monotonicity violation and the least likely place to
fill one — 73.9% "riskless" against one one-hundredth of a basket. That
is the same failure as the two hand-checked kills that motivated v2,
arriving now from a new direction: not thin depth behind a real quote,
but no depth behind a nominal one.

`KXNCAAMBWINS-26SJU` is the same position rejected on 08-27 and 08-28
(opp 9310), unchanged. Nothing endorsed. Three live runs, three finds,
three depth kills, zero recordable arbitrage.
