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

## 2026-08-29 (cont.) — what the violations actually are: 6 in 11 snapshots, all three kinds sterile

Three live sessions, five positions, five depth-gate rejections. Rather
than read that as "the gate is too strict" or "it does not fire", replayed
the theory's own geometry over all **11 stored board snapshots**
(2026-08-24 to 2026-08-29, 96k–117k markets each). No API calls — which
mattered, because a calibration_harvest collector was saturating the
rate-limited history endpoint at the time. Full write-up and reproducible
probe: `studies/2026-08-29-structural-arb-violation-liquidity/`.

**Six distinct violations across 11 snapshots and 5 days**, and they fall
into exactly three sterile classes:

| violation | gross | horizon | return/yr | thin leg vol | snaps |
|---|---|---|---|---|---|
| `KXWTAGTOTAL` ×3 | 4–82% | 15d | 101–1992% | **0.0–0.1** | 1 each |
| `KXNCAAMBWINS-26SJU` 24/27 | 8.7% | 0.56y | 15.6% | **6.0** | **8** |
| `KXNASDAQ100MINY-26DEC31` | 12.4% | 0.34y | **36.4%** | **3,918** | 5 |
| `USCLIMATE` 2025/2030 | 6.6% | 4.34y | **1.5%** | **11,596** | 4 |

1. **Untraded strikes** — quotes no trade has ever tested; the huge
   annualised numbers are arithmetic on prices nobody will fill. Each
   appeared in one snapshot only.
2. **Frozen thin ladders** — `KXNCAAMBWINS` persisted **8 of 11
   snapshots at unchanged prices** on 6- and 40-contract legs. A 15.6%/yr
   riskless return sitting untouched for five days is not an opportunity
   anyone is declining; the live depth check measured 0.47 baskets and
   **$0.02**.
3. **Long-dated ladders** — `USCLIMATE` is genuinely liquid (11,596
   contracts) and genuinely persistent, and pays **1.5%/yr over 4.3
   years**: below cash. Independent arrival at calendar-arb's conclusion.

**Exactly one candidate was both liquid and attractively priced:**
`KXNASDAQ100MINY` (36.4%/yr, 3,918 contracts) — recorded as opp 9248 on
08-27, **rejected as dust**, and by the next session its YES leg had moved
0.07 → 0.21 and the violation was gone.

**So v2's depth gate is validated, not too strict.** All six would have
been correctly rejected, and the one that looked real proved it by
evaporating. Lifetime volume is *not* the right liquidity test — 9248 had
3,918 contracts and was still dust at the prices that mattered — which is
exactly why v2 walks the order book.

**But the tradeable firing rate over 5 days and 11 pulls is zero, and the
mechanism explains it.** A violation both fillable and worth filling is by
construction the one somebody else takes first; what survives to be
visible on a periodic board pull is the residue. Adverse selection, not
bad luck — more sessions of the same scan should not be expected to fix
it.

**No retirement proposal**: n=6, `testing`, 0 settled rows, and this
measures the population rather than the theory's edge. Two cheap changes
are pre-registered in the study for whenever they are wanted: screen out
the three sterile classes in stage 1 (they are all identifiable before the
depth fetch, and it would stop the scan reporting finds it will always
reject), and — if fillable violations really do decay within a day — treat
this as an execution-*cadence* problem rather than a screen problem.

**Method note worth keeping.** The probe's first draft grouped by event
alone and reported **10,799** violations instead of 6 — a 1,800× inflation
— because one Kalshi event holds several independent ladders (a spread
ladder per team, a hits ladder per player) whose strike numbers compare
numerically and mean nothing across subjects. `underlying_key` exists to
prevent exactly that and its docstring says "a false merge costs real
money". Any future replay of this scan must group by event **and**
`underlying_key`, as `scan.scan()` does.

## 2026-08-29 (cont.) — v3: the three sterile classes screened at stage 1

Implemented the cheap change the study above pre-registered. `_drop_sterile`
runs between the flag check and the live re-quote, so a sterile finding
never reaches the orderbook walk:

- `MIN_LEG_VOLUME = 100.0` — catches classes 1 and 2 (untraded strikes and
  frozen thin ladders). Both are the same defect seen at different volumes:
  a quote no trade has tested.
- `MIN_ANNUALISED_RETURN = 0.05` over horizons of at least
  `ANNUALISE_MIN_DAYS = 30` — catches class 3 (long-dated ladders). The
  horizon floor matters: a 15-day basket annualises to four digits, so
  applying a per-year hurdle to it would be nonsense in the other
  direction.

**The bar, and the test that pins it.**
`test_the_one_liquid_short_dated_violation_survives` asserts that
`KXNASDAQ100MINY` — the only violation in 11 snapshots that was both
liquid (3,918 contracts) and attractively priced (36.4%/yr) — still
reaches the depth gate. Screening it out would have been the easy way to
get a quiet scan and the wrong one.

`MIN_LEG_VOLUME` is deliberately **not** a liquidity proxy for the depth
gate. Lifetime volume and fillable size are different questions, and
`KXNASDAQ100MINY` is the proof: 3,918 contracts of lifetime volume and
still dust at the prices that mattered. This screen only removes what
lifetime volume *alone* already proves sterile; the orderbook walk still
decides everything else.

**Verified against today's board.** Same 3 geometry findings as the v2 run
earlier today (2 × `KXWTAGTOTAL` at volume 0.11/0.0, `KXNCAAMBWINS` at
6.0); all three now removed at stage 1 as `untraded or near-untraded leg`,
0 candidates, and **6 orderbook fetches not spent** on a rate-limited
endpoint. Under v2 the same three were fetched and then rejected.

Not an edge change — all six historical finds were rejected either way.
What it buys is a scan that no longer announces finds it will always throw
away. Suite 890 green.

## 2026-08-29 — the flag path validated, and exhaustively empty

The event envelope landed in `tools/` today (`09a66f7`, session 78), which
made the `mutually_exclusive` flag free and complete instead of a
150-per-screen fetch budget. Three things follow, none of which changes
this theory's procedure — recorded so a v4 proposal can cite measurement
rather than hope.

### 1. The expensive path was correct

`theory_facts` holds **2,042** flags accumulated one event at a time
across every session this theory has run. Against the envelope on the
first envelope-bearing capture (`2026-08-29T13:14:32Z`, 110,628 markets),
**1,502 overlap and 0 mismatch.** The per-event fetch was never wrong; it
was only slow.

### 2. Every one of those 2,042 cached flags is `false`

The theory has never once confirmed a mutually-exclusive event, and the
envelope explains why that was never observable: it says `true` for
**6,414** events on this board, and this theory had fetched **none** of
them. Its candidates are *arithmetic hits* (a NO-basket already summing
below its payout), and that population and the ME population barely
intersect — so the budget was being spent where the answer is almost
always `false`.

That is not budget exhaustion and not a broken guard. It is a search
order aimed at the wrong end.

### 3. Inverting the search does not help — measured, not assumed

The obvious v4 was: start from the 6,414 ME events and check *their*
arithmetic, rather than starting from arithmetic hits and paying to check
exclusivity. Now free, so it was worth testing directly.

**Of 6,414 mutually-exclusive events, exactly 1 has a full NO-basket
costing less than its guaranteed payout** — `KXLOWTDC-26AUG29`, $0.005
over 4 legs = **0.125c/leg**, against this theory's 1c/leg buffer. **0
clear the buffer.**

So the inversion finds nothing either. The `no_basket` path has nothing
to find on this board from *either* direction, and that statement is now
**exhaustive over every ME event** rather than limited to 150 fetches.

### What a v4 should and should not claim

Worth doing: source the flag from `m.event.get("mutually_exclusive")`,
falling back to `theory_facts` then a fetch when the capture predates the
envelope (`None` means UNKNOWN, never `False` — reading absent as false
would silently discard real violations). That removes a network budget,
makes coverage complete, and lets the funnel report `flag_confirmed`
against the whole board.

Not worth claiming: that it will find more. It will find the same
nothing, faster and provably. The honest v4 rationale is *coverage and
cost*, not edge — and since it changes where a decision input comes
from, it bumps the version and is the user's call.

## 2026-08-29 — v4: the exclusivity guard is free, and now checks everything

`tools` stopped discarding Kalshi's event envelope on every board pull
(`09a66f7`, session `llm-market-identifier-78`), so `mutually_exclusive`
now rides on every market. This theory had been re-fetching it **one
event at a time** under a 150-per-screen budget, spending the budget on
the largest violations first and reporting the rest as
`flag_fetch_capped`. All of that is gone.

**The guard did not get cheaper. It got *complete*.**

| | v3 | v4 |
|---|---|---|
| candidates checked | 150 (largest) | **1,449 (all)** |
| network fetches | up to 150 | **0** |
| `theory_facts` writes | one per fetch | none |

Live verification on today's board: 1,449 flag candidates, **1,449
rejected as not mutually exclusive**, 0 confirmed, 0 unknown, screen in
11.7s with no rate-limited calls.

### The finding that made this the right change rather than an optimisation

Session `78` measured that **46% of the 14,065 open events are
`mutually_exclusive=true`** — so this theory's all-false cache of 2,042
flags was not Kalshi failing to set the flag. I predicted the cause was
*selection*, and the cross-reference confirmed it exactly: of my 1,445
flag candidates on that board, Kalshi calls **zero** exclusive (1,436
false, 9 closed between pulls).

The mechanism: this theory only asks about an event once the NO-basket
arithmetic already clears. On a genuine partition that arithmetic *is* an
arbitrage, so makers price it to sum correctly and it essentially never
clears. Conditioning on "the arithmetic looked profitable" therefore
selects almost perfectly *against* real partitions.

**So `flag_candidates -> 0 confirmed` is the guard working, not budget
exhaustion and not a dead path.** Without it those 1,449 become 1,449
false arbitrage claims. I had been one step from proposing the path be
cut for lack of true values; that would have been a wrong conclusion
drawn from a real observation, and it took a number I could not cheaply
get myself (the 46%) to stop it.

### Tri-state, deliberately

`_me_flag` returns True / False / **None**, and None is not False. A
board snapshot from before 2026-08-29 carries no envelope, and reading
absence as False would let a replay silently accept a partition it never
verified. Unknown falls back to `theory_facts` — the 2,042 flags this
theory already paid for one fetch at a time are kept and still read —
and is reported as `flag_unknown` if that misses too. Nothing writes new
flags any more, because nothing fetches.

Two tests were deleted rather than adapted (`test_flag_persists_to_
theory_facts`, `test_flag_fetch_cap_reported`): both pinned the fetch
path, which no longer exists. The cache's surviving role is covered by
`test_the_theory_facts_cache_is_still_a_fallback`.

### Synthesis of the two 2026-08-29 entries — what each does and does not license

Two entries above were written hours apart by different sessions and are
often going to be cited together, so: they are complementary, not
duplicates, and neither alone supports what the pair does.

**The v4 entry (mechanism, from the candidate side).** Conditioning on
"the NO-basket arithmetic already clears" selects almost perfectly
*against* real partitions, because on a genuine partition that arithmetic
*is* an arbitrage and makers price it to sum correctly. This is why 2,042
lifetime fetches returned all-false, and it is the reason to **keep** the
guard: without it, 1,449 candidates become 1,449 false arbitrage claims.

**The exhaustive entry (population, from the ME side).** Checking all
**6,414** mutually-exclusive events directly — the approach most
favourable to the thesis — finds **1** with a NO-basket under its payout,
at 0.125c/leg, and **0** clearing the 1c/leg buffer.

**What only the pair licenses.** The v4 entry alone leaves open that real
partitions with tradeable slack exist and this theory's search order
simply misses them; that reading would make an inverted screen the
obvious next move. The exhaustive check closes it: they do not exist on
this board in tradeable size. Conversely the exhaustive check alone might
suggest cutting the path — wrong, because the guard is what stops 1,449
false claims.

So the accurate joint statement is: **the guard is correct and necessary,
and the path should not be expected to produce finds.** Its value is
rejecting false positives, not generating trades.

One phrase to avoid when citing: *"the guard is working"* on its own
implies it separated a mixed population. It never saw a true value at
all — the candidate and ME populations barely intersect. Say
"conditioning on the arithmetic selects against real partitions", which
is the fact.

## 2026-08-29 — corrections to the v4 entry, from supervisor review (session 09)

Session 18 requested a review of v4 before it ended; session 09 reviewed
and applied these fixes (docstrings, THEORY.md, and two test changes)
since the author was gone. Two claims in the entries above are corrected
here rather than rewritten in place — the entries stay as written, this
supersedes them.

**1. The tri-state rationale above is inverted.** "Reading absence as
False would let a replay silently accept a partition it never verified"
is wrong: the consumer in `screen()` excludes a candidate on False and
None alike — only True confirms — so absence-as-False could never accept
anything. What it would actually do is *mislabel*: a replay over a
pre-envelope snapshot would report every candidate as
`not_mutually_exclusive` ("venue said no") when the venue said nothing,
re-manufacturing the same all-false illusion this path barely survived
this morning. The tri-state protects the record, not the decision. Same
error shape as 0e, in a rationale instead of a measurement. Docstring,
test docstring, and THEORY.md now say the correct thing; the v4 commit
message (117a258) is immutable and carries the wrong version.

**2. "Without it those 1,449 become 1,449 false arbitrage claims"
overstates.** Deadline-drift round 5 proved Kalshi's flag reads False on
semantically exclusive events (`KXBOND-30`, one next Bond;
`KXSUPERBOWLHEADLINE-27`, one headliner), so flag=False does not mean
not-a-partition, and rejected candidates are *unverifiable*, not
proven-false. This also bounds the exhaustive entry above: it was
exhaustive over *flagged* events, not actually-exclusive ones. Session 78
then measured the gap rather than leaving the caveat (2026-08-29): with
the priced-as-partition definition ≥3 legs sharing one deadline, sum in
[0.90, 1.05] —

    events priced as a partition   : 53
      Kalshi flags them exclusive  : 43
      unflagged (the gap)          : 10
      gap ∩ clearing candidates    :  0

So no real arb is being rejected **today**, and "nothing to find from
either direction" survives — for a measured reason instead of an assumed
one. **Standing check, not a one-off:** the intersection moves with
prices. Recompute the three numbers from the board (partition events by
the definition above; diff against `mutually_exclusive`; intersect with
`flag_candidates`) before repeating "nothing to find" as settled. Kept
out of `screen()` deliberately — it is a research check, not a decision
input, and the test suite must stay deterministic, so it lives here.

**3. Flag stability is assumed, never measured.** The `theory_facts`
fallback in a replay consults a 2026-08-2x observation at an earlier
decision point, justified only by "the flag is a stable property of an
event". Envelopes ride on every capture since `09a66f7`, so a
cross-capture diff of `mutually_exclusive` (the same scan 4f ran for
rules/title text, which found text *does* drift) settles this in
minutes once a few days of captures accumulate. Run it before any real
backtest leans on the cache; cache rows carry `established_at`, so a
strict replay can also filter to entries established before its
decision point.

## 2026-08-26 — structural_arb implemented from backlog; first live riskless find recorded (migrated from RESEARCH_LOG.md)

**Did:** Settled 15 newly finalized tickers (insider_judgment noscan
weak rows 5W/1L; two of its Aug-23 rejects settled — one rejection
correct, one missed win; mention_family preview 4W/2L, consistent with
the standing retirement proposal). Then implemented `structural_arb`
(backlog idea 4, priority 3/22): pure-code within-event consistency
scanner — nested-pair (ladder monotonicity via YES-interval
containment), geometry NO-baskets (weighted-interval-scheduling DP over
provably disjoint strikes), flag NO-baskets (event mutually_exclusive
envelope, persisted to theory_facts). 26 tests. Registered v1, status
testing. Live scan: 108,820 markets → 1 verified find, recorded as
**opp 9248**: KXNASDAQ100MINY-26DEC31H1600 T22800.01 YES@0.07 +
T22600.01 NO@0.86 — $0.943 all-in vs $1.00 guaranteed floor (+6.0%
riskless, +112% if the 2026 NDX low lands between strikes; crossed
since Aug 24 per snapshots). Tier-A existence replay over all 6 stored
snapshots recorded (backtest-2026-08-26-structarb-snap): 1–3 violations
per snapshot, day-scale persistence. All 1,291 flag candidates fetched:
zero ME.

**Learned:** The first naive scan was a masterclass in why proofs must
be conservative — three defects (414 on bulk re-quote; per-player
strikes sharing one event; Kalshi strike metadata lying on exact-value
markets, which would have recorded a losing "riskless" basket) all
caught before anything hit the ledger; details in
theories/structural_arb/NOTES.md. Also: Polymarket's whales filter
returned a sub-threshold trade (live test now failing on filterAmount
semantics) — needs a look before any whale-based theory trusts it.

**Next:** Watch opp 9248 (mark-taken if entered). Re-run structural_arb
each session — flag lookups are now nearly free. calendar-arb (idea 21)
is the natural sibling: same interval machinery across events in a
series (date ladders). mention_family retirement still awaits the
user's ruling.

## 2026-08-27 — structural_arb v2: depth gate mechanical; queue re-quoted, mostly decayed (migrated from RESEARCH_LOG.md)

**Did:** Settle pass: 0 newly finalized (220 active, 5 closed awaiting
finalization — most of the queue resolves tonight). Scores unchanged
(insider_judgment n=12 +8.28 net; the two new theories n=0).
insider_judgment and no_side_premium already saw today's date
(last night's late session); not re-run. structural_arb re-run against
a fresh 107,656-market board: 1 survivor (KXNCAAMBWINS-26SJU 24/27
nested pair, 4.8% riskless at top-of-book), killed by the manual
orderbook check — 0.47 contracts deep, ~$0.02 fillable (opp 9309,
rejected). Second consecutive live finalist to die exactly this way,
so promoted the depth check into stage 1 as **v2** (TDD, 10 tests,
701 green): `implied_ask_ladder` + lockstep `fillable_floor` walk in
scan.py, orderbook fetch per finalist leg in live price(), <$5
fillable → recorded rejected, unreadable book → screened + `Depth
UNVERIFIED`. Registry bumped. v2 validated live: same find,
mechanically rejected with the hand-check's numbers (opp 9310).
Details: theories/structural_arb/NOTES.md 2026-08-27.

Queue re-quoted (9 endorsed untouched, none settled): GTA ladder
converged to the endorsed [15,30) view (YES-10 0.93→0.97, YES-15
0.87→0.96, NO-45 0.94→0.96; NO-30 moved 6pts against, 0.85→0.79);
BB-DRE NO@0.82 broken (NO now 0.54 — house plan shifted, the risk the
Aug-24 correction flagged); CANUSDEAL NO 0.97→0.98 and CMPS NO
0.91→1.00 have no buyable edge left; NTLA NO 0.88→0.90 thinner,
rules-divergence caution stands. Opp 9248's arb fully gone at
top-of-book (YES leg 0.07→0.21), consistent with its dust rejection.

**Learned:** Top-of-book existence vs fillable size is not an edge
case for this theory — it is the *typical* failure of its finds
(2 of 2). The book's implied-ask structure (`orderbook_fp` = resting
bids; asks implied from the opposite side; fractional dust sizes) is
now encoded and tested. Greedy lockstep ladder walk is exact for the
riskless-fill question because the marginal basket always takes every
leg's cheapest remaining level.

**Next:** Tonight settles most of the queue (GTA video length ladder,
both Big Brother legs) plus the two taken bets' markets soon after
(Grok 4.7 by Sep 4, GTA trailer by Sep 1) — tomorrow's settle pass is
the first real scorecard for insider_judgment v3's endorsed tier and
no_side_premium's cells. calendar-arb (idea 21) remains the natural
next build (same interval machinery, cross-event date ladders).
Ask the user to mark-taken/skipped: 187, 188, 192, 9134, 9140, 9203,
9204, 9238, 9239.

## 2026-08-29 (cont.) — structural_arb: six violations in 11 snapshots, and all three kinds are sterile (migrated from RESEARCH_LOG.md)

**Did:** Three live sessions had produced five `structural_arb` positions
and five depth-gate rejections. Rather than guess whether the gate was
too strict or the theory simply does not fire, replayed the theory's own
geometry over all **11 stored board snapshots** (2026-08-24 → 2026-08-29,
96k–117k markets each). No API calls, which mattered because the
calibration_harvest collector was saturating the rate-limited history
endpoint at the time. Study:
`studies/2026-08-29-structural-arb-violation-liquidity/`.

**Learned:**

1. **Six distinct violations in 5 days, in three sterile classes.**
   Untraded strikes (3, lifetime volume 0.0–0.1 — the 100–1992%/yr
   figures are arithmetic on prices nobody will fill); one frozen thin
   ladder (`KXNCAAMBWINS`, persisting **8 of 11 snapshots at unchanged
   prices** on 6-contract legs, worth $0.02 fillable); and one long-dated
   liquid ladder (`USCLIMATE` 2025/2030, 11,596 contracts, **1.5%/yr over
   4.3 years** — below cash).
2. **Exactly one was both liquid and attractive**, and it evaporated.
   `KXNASDAQ100MINY` paid 36.4%/yr on a 3,918-contract leg, was recorded
   as opp 9248, was **rejected as dust**, and by the next session its YES
   leg had gone 0.07 → 0.21.
3. **So the v2 depth gate is validated rather than too strict** — and
   lifetime volume is not the right liquidity test, which is precisely
   why v2 walks the order book instead.
4. **The zero tradeable firing rate is structural, not unlucky.** A
   violation both fillable and worth filling is by construction the one
   someone else takes first; a periodic board pull sees the residue.
   More sessions of the same scan will not change that.
5. **`USCLIMATE` is calendar-arb's conclusion arrived at independently**
   — cross-date nesting survives only at horizons where carry dwarfs it.
   Two studies, two directions, same answer.
6. **A method error worth remembering.** The probe's first draft grouped
   by event alone and reported **10,799** violations instead of 6, a
   1,800× inflation, because one Kalshi event holds several independent
   ladders (spread per team, hits per player) whose strike numbers
   compare numerically and mean nothing across subjects. `underlying_key`
   exists to prevent that and says so; any replay must group by event
   **and** underlying, as `scan.scan()` does. Recorded in the study
   because the wrong answer was superficially far more exciting than the
   right one.

**No retirement proposal** — n=6, `testing`, 0 settled rows; this
measures the population, not the edge. Two cheap changes are
pre-registered in the study: screen the three sterile classes out in
stage 1 (all identifiable before the depth fetch), and treat sub-daily
decay as an execution-*cadence* question if it is confirmed.

## 2026-08-29 (cont.) — structural_arb v3: the sterile classes screened at stage 1 (migrated from RESEARCH_LOG.md)

**Did:** Implemented the cheap change the snapshot study pre-registered an
hour earlier. `_drop_sterile` removes the three never-actionable violation
classes before the orderbook walk: `MIN_LEG_VOLUME = 100` (untraded
strikes and frozen thin ladders) and `MIN_ANNUALISED_RETURN = 0.05` over
horizons ≥ 30 days (long-dated ladders). Version 3, TDD, suite **890**
green.

**Learned:**

1. **The test that mattered was the keep-case, not the drop-cases.**
   `test_the_one_liquid_short_dated_violation_survives` pins that
   `KXNASDAQ100MINY` — the single violation in 11 snapshots that was both
   liquid and attractively priced — still reaches the depth gate.
   Screening it out would have produced a quieter scan and a worse
   theory; writing that test first is what stopped the thresholds drifting
   toward "remove everything".
2. **Lifetime volume is not a liquidity proxy, and the code says so.**
   `KXNASDAQ100MINY` had 3,918 contracts of lifetime volume and was still
   dust at the prices that mattered. The new screen only removes what
   lifetime volume *alone* already proves sterile.
3. **Verified live:** today's board gives the same 3 findings as this
   morning's v2 run, all now removed at stage 1, and **6 orderbook
   fetches not spent** on the endpoint the collector is competing for.

Not an edge change — all six historical finds were rejected either way.
It buys a scan that stops announcing finds it will always throw away.

## 2026-08-29 (cont.) — structural_arb v4: the guard is free, and now complete (migrated from RESEARCH_LOG.md)

**Did:** Took the theory side of the envelope change above.
`structural_arb` v3 → **v4**: `mutually_exclusive` now reads off the
board, and `MAX_FLAG_FETCHES`, `_me_flag_fetch` and the `theory_facts`
write-back are gone. Suite **964** green.

**Learned:**

1. **The gain is coverage, not speed.** v3 could afford to check the
   **150 largest** of ~1,449 flag candidates; v4 checks **all 1,449**,
   with zero network calls. Live verification: 1,449 candidates, 1,449
   rejected as non-exclusive, 0 confirmed, 0 unknown, screen in 11.7s.
   Previously the honest claim was "the 150 largest were all false";
   now it is complete.
2. **I was one step from cutting the path for the wrong reason.** The
   all-false cache of 2,042 flags looked like Kalshi never setting the
   flag. It isn't — **46% of open events are `true`**. The real cause is
   *selection*: this theory only asks once the NO-basket arithmetic
   clears, and on a genuine partition that arithmetic *is* an arbitrage,
   so makers price it to sum correctly and it never clears. The
   cross-reference confirmed it exactly — **0 of 1,445 candidates
   exclusive**. So `0 confirmed` is the guard doing its job; without it
   those 1,449 become 1,449 false arbitrage claims. A real observation,
   a wrong inference, stopped only by a number I could not cheaply get
   myself.
3. **Tri-state, and `None` is not `False`.** A pre-2026-08-29 snapshot
   carries no envelope; reading absence as False would let a replay
   accept a partition it never verified. Unknown falls back to the 2,042
   cached flags, then reports `flag_unknown`.
4. **Two tests were deleted rather than adapted**, because both pinned
   the fetch path itself. Adapting a test whose subject no longer exists
   produces a test that passes and means nothing.

**Process note.** Three sessions ran this repo today. What made it work
was not the parallelism but that nobody was the last reader of their own
numbers: 4f overturned my politics headline, I found the knob in their
replacement, 78 supplied the one figure that stopped me cutting a working
guard, and I found the API trap that would have bitten their validation.
Every one of those was caught by someone reproducing an arithmetic claim
before arguing with it.


## 2026-08-30 — the COMBO family is liquid AND flat; the parlay edge is in a different product

**Context.** Peer session `ec` measured cross-game parlays trading **+7.06
pts above the product of their legs** and reported `active_quoters = 0`
across 2,134 events, concluding "real mispricing, almost certainly
untradeable". Checked the executability half independently against today's
board, because it is the claim that decides whether any of it matters to
this theory — and because every arb in this repo so far has died on
exactly this step.

**The two products must not be conflated, and the headline changes if they
are:**

| product | on the standard board? | quoting | edge found |
|---|---|---|---|
| multivariate event collections (RFQ parlays) | **no** — 0 of 104,304 board markets carry `mve_selected_legs` | 0 active quoters | **+7.06 pts** |
| `*COMBO` markets | yes, 86 of them | **liquid and tight** | ~0 |

So: **the edge and the liquidity are in different products.** `ec`'s
"untradeable" is correct *for the RFQ parlay product where the +7.06
lives*, and it should not be repeated about the `*COMBO` family, which is
the opposite of untradeable.

**Measured on the `*COMBO` family** (86 markets, today's board):

- **71 of 86 carry a real two-sided book**; all 86 have lifetime volume
  and open interest above zero.
- Spreads: median **4c**, 53 of 86 at **≤ 5c**, tightest at 1c.
- The large ones are very large: `KXBALANCEPOWERCOMBO-27FEB-RR` shows
  **4.17M lifetime volume / 2.73M open interest** at bid 0.15 / ask 0.16.

**And it is priced coherently**, which is the part that matters to this
theory. The `KXBALANCEPOWERCOMBO-27FEB` 2x2 partition {DD, DR, RD, RR} is
mutually exclusive and exhaustive, so its four YES prices must sum to 1:

```
asks 0.47 + 0.39 + 0.013 + 0.16 = 1.033   -> buying the basket loses 3.3c
bids 0.46 + 0.38 + 0.012 + 0.15 = 1.002   -> selling it nets 0.2c gross
```

0.2c gross against Kalshi fees on four legs is not a trade. This
independently corroborates `ec`'s own COMBO result (34 constructions, 1
profitable at zero buffer at +0.05 pts, 0 at a 1c/leg buffer) by a
different route — their route was the cross-event synthetic identity,
this one is the within-partition sum.

**What this means for `structural_arb`.** The COMBO family is the single
best place on Kalshi for this theory's thesis to pay off — a
mutually-exclusive partition with millions in open interest and 1c
spreads, where a violation could actually be filled at size. There is no
violation there. That is a stronger negative than the usual "the edge
existed but died on depth": here the depth is real and the edge is
absent.

Today's scan is consistent: 1,411 flag candidates all removed as
`not_mutually_exclusive` on Kalshi's own envelope field, 1 nested
violation killed by an untraded leg, 0 recorded.

## 2026-08-31 (UTC) - clean run, v4

Floor run per RUNBOOK on the shared board (99,064 markets, pull
2026-08-31T00:38Z). Funnel: 10,473 multi-market events / 2,788 scalar
events -> 2 raw nested violations -> 1,362 flag candidates. Gate removed:
1,362 not_mutually_exclusive, 2 nested violations with an untraded or
near-untraded leg. 0 survivors, 0 recorded. Same shape as 2026-08-30
(1,411 flags, all removed). Ran clean; this note is the record, the
ledger has no rows to carry it.
