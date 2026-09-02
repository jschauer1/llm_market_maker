# deadline_drift — lab notebook

Dated, raw, append-only. The distilled version lives in `THEORY.md`.

## 2026-08-29 — proposed, v1, bins not yet collected

Promoted from idea 3 after five audit rounds. Full narrative in
`studies/2026-08-29-deadline-drift-classifier-audit/STUDY.md`; short version
is that a board-wide mechanical screen is unreachable (round 5: 12% against
a 10% bar, not distinguishable from round 4's 16%) and the allowlist is
(round 5b: 70/70 series, exhaustive, no sampling error).

Three things that surprised me, worth a future session knowing:

- **The horizon snapshot nearly fooled me.** First run of the screen
  returned 0 candidates with 856 markets "outside horizon", which reads like
  a dead theory. It is not: the population is long-dated by construction, so
  41-in-window today is a *stock*, and the *flow* is 714 closes over the
  next 12 months. Check flow, not stock, for any theory whose markets are
  long-dated. I nearly reported a viability problem that does not exist.
- **The 7–21 day bucket is empty** — 41 markets at 0–7d, 0 at 7–21d. Close
  dates in these families cluster hard on month boundaries. If the day bins
  come back sparse in the middle of the window, that clustering is why, and
  the bin edges may need to follow the clustering rather than round numbers.
- **`mutually_exclusive` is reliable here and unreliable board-wide.** Looks
  contradictory, is not. The price test catches a partition only when it is
  tightly priced: `KXUKCABOUT` is 23 legs summing 0.90 and is caught;
  `KXSUPERBOWLHEADLINE` is 54 illiquid longshot legs summing 3.64 and is
  missed. A signal's hit rate is a fact about a population, never about the
  signal — backlog index step 0e, which came out of this same work.

Not done and deliberately so: **no hazard bins**. They are the expensive
rate-limited step, section 7 forbids collecting them until the population is
settled, and the population only settled today. That is the next step and
the only thing between v1 and `testing`.

## 2026-08-29 (later) — the thesis, finally measured. It does not hold up.

After five audit rounds spent on the *screen*, the actual claim got tested
for the first time. Tier A, no model anywhere.

**What was collectable, and why that is the headline.** Kalshi archives
settled markets out of its public API ~60 days after close. Walking all 70
allowlist series returned **112 settled markets** — that is not a sample,
it is the *entire fetchable history* for this population. Candles for all
112 gave 2,805 daily observations, saved raw in
`hazard_observations.json`.

**Clustered by market**, because one market contributes ~25 daily rows that
all share a single outcome — treating those as independent would inflate n
by 25x and manufacture significance out of nothing:

```
POOLED, late window (<=21d), entry band ($0.05-0.60), n = 55 markets
  mean yes_ask      0.148
  realized P(YES)   0.182
  gap              -3.4 pts   (SE 5.2, z = -0.66)
```

**The point estimate has the wrong sign.** The thesis says YES is
*overpriced* late, so the gap should be positive. It is negative — YES was
mildly *under*priced — and not significant either way. Kill criterion 1 was
"implied and empirical hazard agree within fees across all bins"; on this
evidence they agree, with the point estimate leaning against the theory.

**What I am NOT doing: writing `hazard_bins.json`.** With `min_n=30`, cell
`d3|p0` (n=31) would squeak through and start emitting +4.4pt "edges" from
a single thin cell. That is manufacturing bets out of noise, so the file
stays absent, `price()` keeps returning nothing, and the theory stays
`proposed`. The bins are data, not a live instrument.

**One pattern, recorded as a hypothesis and explicitly NOT an edge.** The
only positive cells are the cheapest price bin ($0.05-0.15), and they are
the three biggest cells: +1.0 (n=19), +2.8 (n=27), +4.4 (n=31), monotone in
days-remaining. That is longshot bias exactly where the thesis predicts it,
and it is the *only* place the effect appears — everything at $0.15-0.60
runs negative. Per CLAUDE.md's pairing discipline this is a hypothesis to
pre-register for a forward test, never an edge to bet on the data that
suggested it. If it is pursued, the pre-registration is: **NO on allowlist
markets with yes_ask in $0.05-0.15 and 7-21 days to close.**

**The urgent operational finding.** 112 markets is all that exists *today*,
and the window keeps rolling — markets settling now become unfetchable in
60 days. This population produces ~714 closes a year, so a capture job
running from today would hold ~350 by February and ~700 by next August. The
repo has `market_snapshots` and the settled-history machinery already; what
is missing is anything that routinely sweeps THIS population before it
expires. That is worth more than any further screen work, and it is the
thing that decides whether this theory is ever testable at n that matters.

## 2026-08-29 (later still) — CORRECTION: the previous entry was measuring an artifact

**Retract the "-3.4 pts, thesis does not hold" result above.** It was
contaminated by early-settlement lookahead through the *time* axis. Session
09 flagged the general shape while reviewing an unrelated amendment; I
checked, and it had already bitten.

**The bug.** `days_to_close` was computed from each settled market's
`close_time`. These markets carry `can_close_early=true`, and measured
across all 112:

```
              deadline - actual_close      closed >3d early
  YES  n=34   median 209.6d                32/34
  NO   n=78   median  -0.2d                 0/78
```

A NO market runs to its deadline. A YES market stops trading the moment the
event fires — a median of seven months early. So the two arms were on
**different clocks**: "21 days to close" meant *21 days before the deadline*
for NO markets and *21 days before the event* for YES markets, which is
precisely when the price is climbing toward 1.0. The first result therefore
measured "prices rise before events happen", which is true and worthless.

It is also a **selection** error, not only an axis error: a market that
resolves YES early never experiences the quiet-near-the-deadline state the
thesis is about, so conditioning on actual close imported exactly the
population the thesis excludes.

**Re-anchored on the deadline stated in the rules text** (parsed for
112/112), same clustering by market:

```
                        contaminated      corrected
  anchor                actual close      stated deadline
  markets                        55               48
  mean yes_ask                0.148            0.109
  realized P(YES)             0.182            0.062
  gap                        -3.4 pts        +4.7 pts   (SE 3.5, z=1.34)
  net of fees                      —          +4.0 pts
  outcome mix                     —        3 YES / 45 NO
```

**The sign flips.** Corrected, the point estimate is *thesis-consistent*:
YES overpriced late by ~4.7 gross, ~4.0 net after the 0.68pt fee on a NO at
$0.891.

**It is not a demonstration.** z=1.34 is not significant, and the whole
estimate rests on **3 YES outcomes** — one more would move P(YES) from
0.062 to 0.083 and cut the gap by a third. This is a promising point
estimate on a sample far too small to reject zero, and it must not be
reported as anything else.

Two lessons worth carrying, both mine:

- **Check the clock before trusting a hazard measurement.** On any "does X
  happen by D" market, actual close is a function of the outcome. Anchor on
  the *scheduled* deadline, always. The corrected pipeline parses it from
  the rules text and it was recoverable for 112/112.
- **I published the artifact before checking it.** The previous entry and
  its commit stated a conclusion with the wrong sign, and it survived
  because the result was *unsurprising* — a thesis failing is exactly what I
  had been primed to expect after five rounds of screen work. A result that
  confirms your current mood deserves the same scrutiny as one that
  offends it.

### Reproducibility fix, and why dropping early-YES markets is not survivorship bias

The correction above was committed as prose: the numbers retracting a
committed conclusion existed only in one session's memory. Fixed —
`collect_settled.py` persists the raw `list_settled` payloads, per-market
anchors (parsed deadline, actual close, and the gap), and candles carrying
**both** `days_to_close` and `days_to_deadline`; `hazard.py` regenerates
both tables from disk. `python -m theories.deadline_drift.hazard` prints the
contaminated and corrected rows side by side, so the retraction is a number
you can run rather than a claim you have to trust.

`hazard_observations.json` is deleted rather than kept: every row in it was
anchored to actual close with no absolute dates, so it could only ever
reproduce the *wrong* table. `data/candles.json` supersedes it and carries
both anchors.

**On the 7 markets the corrected view drops.** At a glance, excluding
markets that resolved YES before deadline−21 looks like selection — the
correction removes exactly the arm that would raise P(YES). It is not.
Conditioning on "still open at deadline − h" is the hazard-analysis
**at-risk set**: a market that has already resolved YES is not available to
bet at that moment, so excluding it is precisely what makes P(YES) the right
*conditional*. The number answers "given I can still buy NO here, how often
does YES come in?" — the only question a bettor can act on. Anchoring on
actual close does the opposite: it drags each YES market's resolution
moment into the late window and asks a question nobody can trade.

### Canonical numbers

`python -m theories.deadline_drift.hazard` is the canonical source for every
figure in this notebook; anything quoted here that disagrees with it is
stale. Session 09 found the two disagreeing on the YES early-settlement
median (script 212.9 vs notes 209.6) and the data was right: `hazard.py`
was taking `v[len(v)//2]`, which for even n is the upper-middle element
rather than the median. Fixed to `statistics.median`. **209.6 days is
canonical.** A reproducible script is only worth as much as its arithmetic,
and this one was checked against a number written down before it existed —
which is the only reason the bug surfaced.

## 2026-08-29 (cont.) — deadline-drift's classifier audited three times; the spec is missing its biggest exclusion (migrated from RESEARCH_LOG.md)

**Did:** Started backlog #2 (`deadline-drift`) with the piece its own spec
calls "most of the work" and makes a kill criterion: the rules-text
classifier and a 50-market hand audit. Ran the audit **three times** on
disjoint systematic samples of the 117,272-market board. No API calls and
no hazard bins collected — deliberately, because the bins are the
expensive step (Kalshi rate-limits to ~4–5 req/s) and misclassification
poisons them. Study, classifier and all three judged samples:
`studies/2026-08-29-deadline-drift-classifier-audit/`.

| round | population | misclassified /50 | rate |
|---|---|---|---|
| 1 | 7,613 | 20 | **40%** |
| 2 | 5,155 | 10 | **20%** |
| 3 | 4,792 | 6 | **12%** |

**Learned:**

1. **The spec's non-goal list is missing its largest contaminant.** It
   names scheduled certainties and continuous thresholds; the dominant
   family is neither. **Multi-destination "which branch" markets** — "X's
   next team is Y before D", "Z is the first person confirmed as
   Commissioner" — resolve YES only if the event happens *and* lands on
   this branch, making them a hazard **times a conditional multinomial**.
   At board scale that is **2,687 markets, 34% of the whole by-deadline
   population**. Anyone implementing the spec as written pools all of it
   into the hazard bins. Spec amended in place.
2. **The classifier is a long tail of prose, not a pattern set.** Every
   round found a family the previous one had not imagined — prose count
   thresholds ("the number of X ... is at least 5"), role succession
   ("becomes Chief Minister following the 2026 Manx general election"),
   scheduled competition outcomes ("wins a tennis major"), and in round 3
   a price threshold that said "strictly greater than" instead of
   "above". The rate halves each round, which is either convergence or an
   irreducible floor; one more cheap round distinguishes them.
3. **Auditing before collecting was the right order and nearly wasn't
   taken.** The instinct was to build the bins first. At 40%
   misclassification the bins would have been meaningless, and they cost
   hours of rate-limited API time that cannot be parallelised.
4. **The theory itself looks good.** 4,792 markets in 859 series survive,
   3,079 in the entry band, and the survivors are exactly the thesis:
   traded / pardoned / charged / IPO-confirmed / legislation-passed
   before a date.

Idea 3 moved `considered` → `investigating` with all of this recorded.

**Round 4, run immediately after: 16% — it went UP.** That is the
answer. Every fix rounds 1–3 implied was folded in and the rate did not
improve; at n=50 the SE on a 15% rate is ~5 points, so 12% and 16% are
one number — **a plateau near 15%**, above the spec's own bar. Five of
round 4's eight misses were multi-destination *again*, in phrasings no
extension of the round-3 pattern anticipates: "the next club that
Cristiano Ronaldo joins is CF Monterrey", "Russia is the first country to
launch a manned mission", "the next new Secretary of Defense ... is Mike
Pompeo", "leaves before any other Pro Football head coach", "a coalition
that includes SPD make up the next elected ruling government".

**The residue is semantic, not syntactic** — "does this condition on
which branch the event takes?" is a meaning these share, not a string.
That is exactly CLAUDE.md's line for when to reach past code: mechanics
yield to a regex (the gate work earlier today), reading comprehension
does not.

**Next: a user decision, because every option costs something the spec
promised.** (1) a cheap LLM gate — clears the bar, forfeits **tier A**,
which was this theory's defining property; (2) a series allowlist of the
~20 unambiguous recurring families — stays tier A, smaller population,
and reintroduces the maintenance treadmill today's gate work moved away
from; (3) drop it. Spec section 3 amended to say section 4 is not
implementable as written. **No hazard bins under any option until this is
settled.**


## 2026-09-01 — CORRECTION 2: the edge was the bid-ask spread. Measured against the price a NO buyer actually pays, it is gone

Session `llm-market-identifier-9e`, theory lane, focus `deadline_drift`.
**Numbers below are provisional** — the wide capture was still walking when
they were taken. `python -m theories.deadline_drift.hazard` is canonical;
re-run it before quoting anything here.

### Why this theory was picked up at all

It sat at `proposed`, recording nothing, because the corrected 2026-08-29
estimate rested on **3 YES outcomes of 48 markets**. It rested on 3
because the population had been cut from 4,792 markets / 859 series to
981 / 70 on the same day, to keep tier A — this notebook's own words:
*"a cheap LLM gate — clears the bar, forfeits **tier A**, which was this
theory's defining property."*

**That premise stopped being true the day it was written.** CLAUDE.md's
"Structural gates keep tier A" and backtest-theory's five structural-gate
conditions say a gate whose answer cannot be influenced by the outcome
costs the tier nothing. "Does this market condition on which branch the
event takes?" is answerable from the market's text as written at open, so
the allowlist was paying a price that no longer exists. Widening the
capture was therefore the obvious unblock, and it is what surfaced the
finding below — which has nothing to do with the population size.

### The finding: `hazard.py` priced the trade off the wrong side of the book

This theory **buys NO**. A NO buyer pays `no_ask = 1 - yes_bid`, so the
breakeven probability is **`yes_bid`**. `hazard.py` compared realized
P(YES) against **`yes_ask`**, which credits the strategy with the entire
bid-ask spread. On the same 95 markets:

```
                        mkts  YES   price  P(YES)     gap    SE     z     net
YES ask (optimistic)      95   14   0.242   0.147    +9.5   3.6  2.60    +8.2
YES bid (what NO pays)    95   14   0.171   0.147    +2.3   3.6  0.64    +1.4
```

The ask row is not a near miss — at z=2.60 it reads like a demonstrated
edge. The bid row is the same markets, the same outcomes, the same
window, and it is noise. By linearity the mid sits at **+5.9, z=1.65**,
also not significant, so no reading of the book rescues it.

**The spread is big enough to explain all of it.** Over the 358 in-window
daily observations: median 3.0 pts, mean 5.6, p75 5.0, max 43. And the
live board says the same thing from a completely independent direction —
today's 967 allowlist markets have a **median 6.0 pt** spread in the
$0.05–0.60 entry band (5.0 even restricting to volume >= 100), against a
claimed gross edge of +4.7. **The spread was always larger than the
edge.**

The cleanest confirmation is that the ask-side result *dies as the spread
shrinks*, which is what an artifact does and what a real edge does not:

```
priced off YES ASK        mkts   gap      z
all                         63  +8.5   1.73
spread <= 10pts             56  +1.9   0.34
spread <= 6pts              53  +0.9   0.16
spread <= 2pts              41  +2.2   0.33
```

Where the book is tight, ask ≈ bid and both agree the market is priced
about right. The whole +8.5 lives on wide-spread markets, i.e. on the
half of the quote nobody will sell you.

### What this does NOT say

- **Not that the hazard is mispriced in the other direction.** Bid-side
  gap +2.3 ± 3.6 is consistent with zero and with a couple of points
  either way.
- **Not that every slice is dead.** `open interest >= 100` reads +5.1
  (z=1.24) and `volume >= 1000` +4.3 (z=0.82) on the bid side — the only
  cuts that move the number up rather than down. Underpowered, in-sample,
  and one of many cuts tried, so this is a **hypothesis, not a finding**.
  It is also the *opposite* sign to kill criterion 3 ("the effect exists
  only where liquidity is worst"), which makes it worth a proper look
  once the capture finishes.
- **Not a verdict on the 2026-08-29 correction.** Correction 1 (anchor on
  the stated deadline, never actual close) stands and is unaffected;
  `hazard.py` still prints both rows.

### Lesson, and it is not specific to this theory

**The optimistic field is the one named "ask".** CLAUDE.md says entry
prices are "the ask you would actually pay" — and for a NO position that
ask is `1 - yes_bid`, so the rule binds through the field that is *not*
called ask. Reading `yes_ask` does not look like a bug; it looks like
following the rule.

**Checked, and the repo is clean — which sharpens the lesson rather than
softening it.** Every other NO-taking path here gets it right, and three
of them say so in a comment: `insider_bias/replay.py:244`
(`no_ask=1.0 - yes_bid`), `calibration_harvest/collect.py:151` ("to buy
NO you lift the resting YES bid from the other side of the book"),
`no_side_premium/theory.py:135`, and both `screen.py`s price a NO leg off
`market.no_ask`. So the convention exists, is documented, and holds
everywhere it is *used*.

The bug appeared in the one place that bypassed it: an **analysis
script** doing its own arithmetic on raw candle fields instead of going
through `no_ask`. `hazard.py` never touched the domain types — it read
`yes_ask_close` out of a JSON file and compared it to an outcome. That is
the transferable warning: the entry-price convention is enforced by the
*types*, and a measurement script that reconstructs prices from raw
payloads steps outside that enforcement without any signal that it has.
Backtests and mining scripts are exactly the code that does this.

It is also the second collector-throws-away-the-evidence finding in two
days. `calibration_harvest` learned on 2026-09-01 that its collector
computed volume and spread, filtered on them, and persisted neither.
Here the collector fetched `yes_bid_close` and `open_interest` on every
candle and stored neither, so the defect was **unfalsifiable from disk**
— and would have stayed so, because Kalshi archives this data at ~60 days.
Both are now persisted (`_rows`), and legacy rows the archive can no
longer re-serve are stamped `bid_unavailable` rather than dropped: 33 of
the 2026-08-29 markets had already aged past today's floor, so a
wipe-and-refetch would have destroyed them.

### Capture widened, and why the walk is the superset rather than the screen

`collect_settled --wide` now walks **every series holding a by-deadline
market (960)**, not the 68 allowlist ones, and applies no exclusions at
all. **Capture is not classification, and only capture is perishable**:
the screen can be revisited any day, the payloads cannot. Exclusions are
applied offline in `hazard.py`'s `stratum()`, which also reports each
excluded population rather than dropping it silently.

### Also learned, the hard way: two collectors racing lose data silently

Mid-walk, `anchors.json` went 332 -> 294 markets. A collector I had
stopped was still running: **TaskStop stops the shell, not the detached
child**, and `ps -ef` in this Git Bash shows no arguments, so
`ps -ef | grep collect_settled` reports zero while it runs.
`Get-CimInstance Win32_Process | Select CommandLine` is the check that
works. Two load-modify-save collectors then silently overwrite each
other. Ticketed (`maintenance/collector-concurrent-write-race`); this
theory's own data is fine because the walk is resumable and was re-run.

## 2026-09-01 (later) — CORRECTION to the entry above: the spread explains HALF the edge, not all of it. What is left survives every cut I could throw at it

Same session. **Retract the framing of the previous entry**, not its
central fact. The bid/ask correction is right and stands. The conclusion
I drew from it — "the bid row is the same markets ... and it is noise",
"the entire measured edge is the bid-ask spread" — was drawn at n=95
markets on a capture that was **one quarter done**, and it does not
survive the finished walk.

Numbers below are from `hazard.py` and `bootstrap.py` at ~1,300 settled
markets. Both are canonical; re-run them.

### What actually happened to the estimate

Three estimator defects, found in this order, each one changing the
answer:

| # | defect | effect on the gap |
|---|---|---|
| 1 | priced off `yes_ask`, but a NO buyer's breakeven is `yes_bid` | roughly halves it |
| 2 | one vote per MARKET, when the independent unit is the EVENT | raises it |
| 3 | normal-approximation z on a skewed, mostly-zero outcome | z was not a p-value |

Defect 2 is why the first entry was wrong. Market-weighting let single
events dominate in proportion to how finely Kalshi had sliced them:
`KXBIGBROTHERELIMINATION` is 8 events of 11–17 legs paying **exactly one
winner each** (a "which houseguest" partition), and `KXGEMINI` is one
7-leg date ladder on a single unresolved question that was contributing
**30% of the pooled gap by itself**. Averaging within the event first
gives each independent question one vote.

### The current numbers, event-clustered and bootstrapped

```
cut                                  evts     gap        95% CI      P(<=0)
ALLOWLIST (pre-registered), bid        21    -1.7   [-10.7,  +5.1]    0.622
ALLOWLIST, ask (the old view)          23    +5.7   [ -2.4, +12.0]    0.074
wide hazard, bid                       64    +6.3   [ +2.1, +10.3]    0.003
wide hazard, ask (the old view)        66   +11.9   [ +7.9, +15.7]    0.000
  bid, spread<=4pts                    57    +7.3   [ +2.2, +12.1]    0.003
  bid, spread<=2pts                    46    +7.3   [ +0.3, +13.5]    0.021
  bid, minus partition families        56    +6.6   [ +1.8, +11.1]    0.004
  bid, open interest>=100              62    +7.2   [ +3.3, +10.9]    0.001
```

**The decisive diagnostic is the spread ladder, and it runs the other
way from what I claimed.** A gap that IS the spread must shrink as the
spread filter tightens — that is precisely how the `yes_ask` view was
convicted. The bid-side gap **grows**: +6.3 → +7.3 as the filter goes to
2 points. It also survives removing one-winner partition families and an
open-interest floor. That is not the signature of an artifact.

### So the real finding is about the ALLOWLIST, not about the thesis

The two populations disagree, and the disagreement is the point:

- **Wide by-deadline hazard population: +6.3 pts at the tradeable
  price**, CI excluding zero, 64 event clusters.
- **The allowlist the theory actually ships: −1.7, CI [−10.7, +5.1]**,
  21 event clusters. Not evidence against the thesis — it is *no
  evidence either way*, because 70 series is too thin a slice of the
  board to measure anything in a 60-day archive window.

The allowlist was adopted on 2026-08-29 to keep tier A when a structural
LLM gate still cost it. It cut the population ~5x. **That restriction,
not the thesis, is what has kept this theory unmeasurable** — and per
CLAUDE.md's "Structural gates keep tier A" it has been unnecessary since
the day it was adopted.

### What must NOT be concluded from this

The +6.3 is **post-hoc**. I chose the wide population today, measured it
today, and tried a dozen cuts on the way. CLAUDE.md's pairing discipline
is explicit: a pattern found this way is a hypothesis to pre-register,
never an edge to bet on the data that suggested it. It also inherits the
audit's known contamination — the wide population measured ~15%
misclassified, and `partition_families` only removes the part that
settles as a one-winner family.

So: no `hazard_bins.json`, `price()` stays inert, status stays
`proposed`. The pre-registration is written into THEORY.md, and the
out-of-sample test is markets settling **after 2026-09-01**, which the
standing capture obligation now exists to collect rather than merely to
tidy.

### Method notes worth keeping

- **A partial capture is not a small sample, it is a biased one.** The
  walk is alphabetical by series, so the early-close family detector read
  98.0% vs 0.0% at ~200 multi-destination markets and 43.4% vs 0.0% at
  ~525. I committed the 98% into a docstring before noticing. Quote
  nothing from a running walk without saying it is running.
- **The early-close tell is one-directional.** An early NO close nearly
  implies a branch family (allowlist: 0/78); a late one implies nothing,
  because branch families also run to the deadline when no sibling wins
  in time. It finds contamination; it cannot certify a population clean.
  `partition_families` (events paying exactly one winner) catches what it
  misses, including `KXBIGBROTHERELIMINATION`.
- **Two collectors racing lose data silently, and `ps` here cannot see
  it.** `TaskStop` stops the shell, not the detached child; `ps -ef` in
  this Git Bash prints no arguments, so `ps -ef | grep collect_settled`
  reports zero while the process runs. Use
  `Get-CimInstance Win32_Process | Select CommandLine`. I then made the
  same mistake a second time, writing an `until ! ps -ef | grep ...` wait
  loop that exited immediately against a still-running collector.
  Ticketed as `maintenance/collector-concurrent-write-race`.

### The split that explains both populations, and where the premium actually lives

Splitting the wide hazard stratum by allowlist membership (event-weighted,
bootstrapped over event clusters, priced off the bid):

```
  all hazard, bid                  81 evts   +6.7   [ +3.1, +10.0]  p=0.000
    closes before Aug 01           46 evts   +4.6   [ -0.1,  +8.7]  p=0.027
    closes from Aug 01             39 evts   +9.2   [ +2.9, +14.8]  p=0.003
    allowlist series only          22 evts   -1.0   [ -9.8,  +5.7]  p=0.560
    NON-allowlist series only      59 evts   +9.6   [ +6.3, +13.0]  p=0.000
```

Both halves of the capture window are positive, so it is not one bad
fortnight. But the allowlist/non-allowlist split is total: **all of the
effect is outside the allowlist.**

Looking at what is actually in there settles what kind of thing this is.
The top non-allowlist contributors are **one-off newsy questions priced
$0.25–0.55 that did not happen** — "Will the Senate vote on the CLARITY
Act?" (0.54), "Will another GTA VI trailer come out before Aug 2026?"
(0.37), "Will Google release Gemini 3.5 Pro before Aug 21?" (0.35), "Will
Serbia announce a snap election before Aug 1?" (0.27), "Will legislation
reauthorizing FISA 702 pass?" (0.26). Almost all are a single event with
zero YES.

The allowlist, by contrast, is **recurring families** — `KXFEDERALCHARGE`,
`KXNBATRADE`, `KXMLBDEBUT`, `KXMANAGERSOUT` — trading at a mean bid of
0.04–0.06 and pricing about right.

**Proposed mechanism: a recurring family teaches its own base rate.**
Someone who has watched forty coach-out markets resolve knows roughly how
often one fires. A one-off question about a bill, a trailer or a model
release has no reference class anywhere on the board, so the story that
made it interesting sets the price and nothing drags it back. If that is
the mechanism, the premium tracks **non-recurrence**, not subject matter —
which is testable on a property fixed at listing time. Written up as DD-2
in THEORY.md.

**The irony worth recording.** The allowlist was built by asking which
families are *unambiguously* per-subject hazards, and the answer was: the
recurring ones, because you can inspect a family's whole history and be
sure. That selection criterion is close to a proxy for "the ones traders
have also seen before". **The screen was selecting against its own edge**,
and it did so for a good reason that had nothing to do with the thesis.

**What this does not settle.** 5 series carry 37% of the non-allowlist
gap; most contributing series are one event that did not happen; and
`KXBIGBROTHERELIMINATION` (a one-winner partition, ~6% of the gap) proves
the population is still not clean. The bootstrap prices the sampling
uncertainty and cannot price the contamination — that needs the
structural gate, which is what the open ticket is for.

### FINAL numbers — capture complete, 1,908 settled markets in 962 series

The two entries above were written mid-walk and their tables are
superseded by these. **Every number moved down** as the walk finished,
which is the point of the "a partial capture is a biased sample" note:

```
cut                                  evts     gap        95% CI      P(<=0)
ALLOWLIST (pre-registered), bid        22    -1.0   [ -9.8,  +5.7]    0.560
ALLOWLIST, ask (the old view)          23    +5.7   [ -2.4, +12.0]    0.074
wide hazard, bid                       94    +4.6   [ +1.0,  +8.0]    0.007
wide hazard, ask (the old view)        95   +10.1   [ +6.6, +13.4]    0.000
  bid, spread<=6pts                    94    +5.2   [ +1.5,  +8.6]    0.003
  bid, spread<=4pts                    84    +5.3   [ +0.9,  +9.5]    0.009
  bid, spread<=2pts                    69    +5.0   [ -0.8, +10.4]    0.044
  bid, minus partition families        86    +4.8   [ +0.9,  +8.4]    0.009
  bid, open interest>=100              92    +5.3   [ +1.8,  +8.5]    0.002
  NON-allowlist series only            72    +6.3   [ +2.4, +10.0]    0.001
  closes before Aug 01                 51    +2.1   [ -3.6,  +7.1]    0.215
  closes from Aug 01                   49    +6.1   [ -0.3, +12.0]    0.030
```

The trajectory as the walk grew: **+6.7 → +5.8 → +5.0 → +4.6**. It was
still falling at the end. Do not treat +4.6 as settled; treat it as the
in-sample number that DD-1 has to beat out of sample.

**The entry rule turns out to be load-bearing, and that is the thesis
rather than a fragility.** On the hazard stratum, priced off the bid:
entering the *first* qualifying day gives **+3.4**; averaging over every
qualifying day in the window gives **−1.7**. The overpricing decays as
the deadline approaches, so entering as early as the window allows is
where the drift is — which is what "deadline drift" means. It also means
any test that enters late measures nothing.

**Three caveats that belong next to the headline, not below it.**

1. **Concentration got worse with more data, not better.** Top 5
   non-allowlist series carry **46% of the pooled gap on 13 of 72 event
   clusters**, and 10 of the top 12 contributing series are a *single
   event that did not happen* — CLARITY Act vote, another GTA VI trailer,
   Gemini 3.5 Pro, Serbia snap election, FISA 702 reauthorisation. The
   bootstrap prices this as sampling uncertainty; it cannot tell you
   whether the next 60 days serve up a comparable crop of one-off
   questions.
2. **Liquidity is adequate but the gradient is wrong at the top end.**
   Median open interest at entry is ~1,100 and 53% of entries are above
   1,000, so this is not `structural_arb`'s unfillable-size problem. But
   at **OI ≥ 5,000 the gap vanishes** (+0.2, CI [−8.1, +7.9], n=38)
   before reappearing at ≥20,000 (+4.5, n=17). Non-monotonic and
   underpowered at the tail, so it is not a clean liquidity story — but
   it is close enough to kill criterion 3 ("the effect exists only where
   liquidity is worst") that it must be re-checked out of sample rather
   than waved through.
3. **Neither half of the window clears on its own** — +2.1 [−3.6, +7.1]
   early, +6.1 [−0.3, +12.0] late. The pooled result needs both halves.

**Where correction 1 stands at full data.** Still the right call, and
still the same direction: anchored on actual close the hazard stratum
reads −1.4, anchored on the stated deadline +3.0. The gap between those
two rows is smaller than it was on the allowlist-only data, because the
wide population is much shorter-dated — the YES early-settlement median
falls from 209.6 days (allowlist) to 10.2 days (wide).

## 2026-09-01 (later still) — v2 ships, the theory records for the first time, and the LLM gate the ticket asked for was deliberately not built

Session `fleet-w1-g1`, theory lane, focus `deadline_drift`. This closes
`widen-population-and-record`.

**What shipped.** Population widened from the 70-series allowlist to
DD-1's — by-deadline, rules stratum `hazard`, minus partitions — the live
horizon re-anchored on the **stated deadline** instead of `close_time`,
version bumped 1 -> 2 (`continues`; v1 recorded no rows, so nothing pools
either way and this is not a sever), status `proposed` -> `testing`, and
**46 observation rows recorded** on the first run. The theory had n=0 for
its entire existence until today.

```
board 110,121 -> population 4,404 -> 46 candidates
gate removed: not_by_deadline 102,366 | stratum_multi_destination 2,601
              | mutually_exclusive_flag 333 | stratum_threshold 324
              | priced_as_partition 48 | stratum_scheduled 29
              | partition_family_learned 16
```

### The ticket asked for an LLM gate. Building it would have been wrong.

Step 1 of `widen-population-and-record` was a series-level structural
gate (~960 calls) to remove the residual ~15% multi-destination
misclassification. I did not build it, and the reason generalizes:

**DD-1's pre-registered population is defined in code, with no gate in
it** — `hazard.stratum() == "hazard"` minus `hazard.partition_families()`,
volume >= 100, entry band, 21 days to the stated deadline. Adding a gate
makes the shipped population something DD-1 does not name, so the forward
test would no longer be the test that was pre-registered. The
pre-registration is the asset here; spending tokens to invalidate it is a
bad trade twice over.

What the gate's information is worth is not zero, so it is **recorded
rather than filtered**: `branch_family`, `in_allowlist`, `recurring`,
`event_legs`, `event_ask_sum`. All are fixed at listing time, carry no
outcome information, and are legal slice predicates ("data over recorded
fields"). If purity turns out to matter, that is a v3 decision made on
settled rows instead of a guess made before any exist. **The cheapest
version of a gate is usually a field.**

### `partition_families` "cannot screen a live board" — the answers can

Both `partition_families` and `branch_families` say so in their own
docstrings, and it is true of the *functions*: they read settlement
outcomes. It is not true of their *answers*, which are sets of **series**,
and a series' construction is a structural fact that outlives any one
settlement. `population.py` is the bridge — it runs them once over the
capture and persists the answers as a 4 KB JSON the live screen reads
instead of 9.5 MB of candles. Rebuilt automatically at the end of
`collect_settled`, because the walk is the only thing that changes its
inputs and "somebody remembers to rebuild" is not a mechanism.

### Three things nearly lost, and one general lesson under them

1. **`yes_bid_implied` was briefly recorded as `yes_ask`.** I wrote the
   feature dict, dry-ran it, and the sample row said `yes_bid_implied:
   0.2` on a market whose NO ask was 0.87 — i.e. yes_bid 0.13. That is
   **correction 2 reappearing inside the same session that documented
   it**, in new code, written by someone who had just read the warning.
   Now `1 - no_ask`, with `yes_ask_optimistic` recorded beside it and
   `test_the_implied_probability_recorded_is_the_bid_not_the_ask`
   pinning it. The notebook's own lesson holds and deserves restating:
   reading `yes_ask` does not look like a bug, it looks like following
   the rule.
2. **`open_interest` was not being recorded at all.** Kill criterion 3 is
   "the effect exists only where liquidity is worst" and the in-sample
   gradient that has to be re-checked was measured on open interest — but
   the ledger has `spread_at_call` and `volume_at_call` and no column for
   it. Without this the theory could never have checked its own kill
   criterion. Caught after the first 46 rows landed and backfilled from
   the same board pull (median 1,107, matching the in-sample ~1,100).
   **This is the third time this theory has lost this exact field** to
   code that read liquidity, used it, and persisted none of it.
3. **The event was recorded as `event`, and scoring reads
   `event_ticker`.** `score.cluster_key` looks up exactly that key and
   otherwise falls back to stripping the ticker's last dash-segment. On
   these 46 rows the fallback is wrong 4 times, and for
   `KXMEDIARELEASEDATEAHS-26-SEP19-AME` (event
   `KXMEDIARELEASEDATEAHS-26`) it **splits one event into several** --
   the dangerous direction, because it manufactures precision instead of
   losing it. Renamed and backfilled; pinned by
   `test_the_event_is_recorded_under_the_key_scoring_reads`. **This
   theory's first run is 20 event clusters, not 46 rows** -- one event
   (`KXTRUMPSAY-26SEP07`) supplies 22 of them, so anything reading these
   settlements uncluttered will read one question as twenty-two.
4. **`extra_json` is written only at row creation**, never on a
   re-sighting. That is right — it should record the decision point — but
   it means a feature added after a row lands is missing from it forever.
   Add fields before the first run, or backfill the same day.

The general lesson under all three: **the ledger's typed columns are the
part that gets reviewed, and `extra_json` is the part that gets
forgotten.** Everything a theory will need in order to test its own
pre-registered criteria has to be in the row on the day it is written,
because the board moves and none of it is recoverable afterwards.

### There is no clean backtest here, and that is the finding

Standing advice says a theory with fetchable history and no replay is
short of a replay. Not this one. The replay has already been run as
analysis — `hazard.py` and `bootstrap.py` over the full 1,908-market
capture — and **the population was chosen on its results**. Every settled
market this theory can reach is in-sample for that choice, so recording it
as a tier A backtest run would let the data that suggested the population
vouch for it. Under the 2026-08-31 ruling a tier A/B backtest counts as
evidence *by default*, which makes this a live hazard rather than a
theoretical one: the run would silently become credibility.

So the forward test is not the slow path here, it is the only honest one,
and the thing that was actually blocking it was that nobody had made the
theory record. Recorded in THEORY.md's Status section for the next
session that reaches for `backtest-theory`.

### DD-2 registered as a slice

`dd2-one-off` — `{"outcome": ["no"], "extra": {"recurring": false}}`,
where `recurring` is "series has >= 3 settled events", fixed at listing
time. Pre-registered in THEORY.md before any out-of-sample data;
registering it starts the clock today rather than whenever someone gets
to it. Today's 46 rows split 23 one-off / 23 recurring, which is a better
balance than the in-sample 72/22 and means both arms accrue at a usable
rate. No `mined_from_run_ids`: the suggesting analysis wrote no ledger
rows, so there is no run to exclude, and the origin says so explicitly.

### Population purity: what today's board shows

`KXAGTELIMINATION` is 4 of the 46 candidates and is **not** a per-subject
hazard — 11 legs, 2 settled events, **7 YES each**. It is a fixed-k
elimination ("exactly 7 of these 11 acts go"), so the legs are negatively
correlated and P(YES) is structurally ~k/n. `partition_families` misses it
because that requires exactly *one* winner; the price test misses it
because 11 legs sum to 6.67, not ~1.00; the rules regex misses it because
the shape is semantic.

I did **not** invent a rule for it. Two settled events is not enough to
fit "fixed-k" against `KXTRUMPSAY`, which is the same superficial shape
(34 legs, many YES) and *is* genuinely independent — Trump saying
"Antifa" does not preclude "Uranium" — with 7-21 YES per event and real
variance. Distinguishing them needs variance across events, and AGT has
n=2. Recorded as `event_legs` / `event_ask_sum` per row and ticketed;
decide it on settled rows.

**One event supplies 22 of today's 46 rows** (`KXTRUMPSAY-26SEP07`). The
rows are legitimate, but anything reading these settlements must cluster
by event or it will read one question as twenty-two.

## 2026-09-02 — DD-3 INTERIM LOOK at 45% capture (declared, not the verdict)

**This is a peek, and recording it is the point.** The user asked for a
read on the current data while the platform walk was still running. Running
the test now and again at completion is **two looks at the same
hypothesis**, and the way that turns into a lie is by reporting whichever
one looks better. So: this entry exists so the interim number cannot be
quietly forgotten, and **the DD-3 verdict is the complete-sweep result,
whatever it says, however it compares to this.**

Capture state: 6,204 / 13,733 series walked (45%), 507 new markets, of
which 390 are hazard-stratum and liquid, giving 36 event clusters in the
test arm.

```
                                mkts evts  YES   price  P(YES)   gap   SEcl   zcl    net
DD-3 UNSEEN (the test)            36   36   10   0.247   0.274   -2.7   7.0  -0.38  -4.0
seen (control, descriptive)       86   86    9   0.156   0.108   +4.8   2.0   2.45  +3.9
```

**Pre-registered verdict: UNDERPOWERED.** 36 event clusters against a
floor of 80. By the bar fixed in THEORY.md before any of this ran, it
settles nothing in either direction, and that is the honest whole answer
today.

What can be said without overreading:

- **The control reproduces exactly.** The seen arm returns +4.8 gap /
  +3.9 net over 86 clusters, which is the number `hazard.main` prints for
  "...minus partitions, ev-weighted". The driver is measuring the thing it
  claims to measure; a mismatch here would have meant the split was wrong.
- **The point estimate on unseen data is negative (−4.0 net), and the
  interval is useless.** 95% CI [−17.7, +9.8] contains the seen estimate
  (+3.9) comfortably, and zero, and −15. A 7.0-point clustered SE on 36
  clusters cannot distinguish any hypothesis anyone holds.
- **The sample is not random.** `platform_series` walks KX* ordered by
  category — Politics first, then Financials, Sports, Entertainment — so
  at 45% the unseen arm is disproportionately one family. This is a
  biased subsample by construction, which is exactly why the pre-
  registration waits for the sweep.

So the honest summary is: **no answer yet, and the early sign is not
reassuring.** Both halves of that sentence are load-bearing.
