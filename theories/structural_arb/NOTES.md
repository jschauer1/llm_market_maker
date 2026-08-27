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
