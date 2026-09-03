# The new-theory backlog — shared contracts

**Every ticket in `open/` is a spec.** A theory does not get built from a
one-line idea here: the ticket carries the mechanism, the population, the
kill criteria, the backtest tier and the relation to existing work, written
so a session with no context beyond CLAUDE.md can pick it up. Filing the
spec *is* proposing the theory.

This file holds what all of them share — the pre-implementation rules, the
assessment rubric, the scoreboard, the parked ideas and the sources. A
ticket links here instead of repeating any of it.

## Where things live

| | |
|---|---|
| `open/` | proposed theories, one spec each — the backlog a session chooses from |
| `build/` | **ready to implement** — accepted, a build order rather than a proposal, and the last state a spec has |
| `reference/` | the graded evidence ledger and full reading notes behind the claims these specs make |

**There is no measurement stage, and that is deliberate** (user ruling
2026-09-03): **a theory proves itself when it is implemented.** It runs,
it records, it is scored, and the ledger answers the question the spec
asked. The lane used to hold a spec in `evidence/` until its cheapest
decisive test cleared the bar the spec wrote before looking, and
`advance` refused `open → build` to keep the stage unskippable. Both are
gone. A thesis you would rather settle before building can still get a
study — the study lane exists for exactly that, and `calendar-arb` and
`smile-smoothing` each died there in an afternoon — but that is a
judgment about one thesis, not a toll every spec pays.

**There is no `completed/`, and a finished spec is deleted** (2026-09-02).
That is not carelessness about history — it is where the history actually
lives. A spec ends as one of two things, and both already have a better
home than a folder: a **built** one is recorded by the theory it became,
and a **dead** one by its ideas-registry row, which `cli tickets close`
refuses to proceed without. `completed/` held a third copy of a verdict
those two already owned, and the third copy is the one that goes stale —
by the time it was removed, **all 16 specs that had passed through it
carried a `resolution:` string that no longer parsed as any of the four
words below**, because the vocabulary was introduced after they were
written and nothing re-read them. Git keeps every deleted spec:
`git log --diff-filter=D -- tickets/new-theory/` finds one and
`git show <rev>:<path>` retrieves it. The 16 removed on 2026-09-02 are at
rev `6e7d920`, which is what the citations pointing at them now say.

The reading notes used to live in a folder that later became a state
(`evidence/`, since removed), and had to move the day it did: a ticket's
state IS its directory, so the backlog lists every `.md` in a state
folder and reported all three reference files as `!! MALFORMED` tickets
with blank titles. That is the
false positive this repo has already paid for once — an alarm that is
always on is worse than no alarm, because the day a real one fires it is
indistinguishable from the noise. `reference/` is not a state, so
`backlog()` never looks in it.

**A resolution starts with one of four words**, and `cli tickets close`
refuses anything else. Closing a spec **deletes it**, so the resolution
is not stored anywhere on disk — it selects the verdict and drives the
registry check below, and the ideas registry is what keeps it:

| word | means | re-proposable? |
|---|---|---|
| `built` | became a running theory — name it | — |
| `disproven` | the bar was met and the thesis failed | **no** |
| `underpowered` | the measurement could not reach the bar — population too thin, history too short, liquidity too low | **yes**, when conditions change |
| `superseded` | folded into another spec or theory | — |

The prose still goes after the colon (`--resolution "disproven: 97.6% of
rungs sat on their own fit"`). The vocabulary exists because `disproven`
and `underpowered` mean opposite things about re-proposing and free text
made them look identical six months later — which is how a dead thesis
gets rebuilt and a merely-unmeasured one gets abandoned. `calendar-arb`
and `smile-smoothing` are the worked `disproven`: measured properly, and
the answer was no.

Closing `disproven` or `underpowered` **requires the finding in the ideas
registry first** — `what_was_tried` and `outcome`, plus a
`revisit_angle` for `underpowered`. That is not bookkeeping: **closing
deletes the spec**, so the registry entry is the only thing that survives
it. The check runs before anything is removed — the durable fact leaves
the file before the file leaves the tree.

An idea to try **on an existing theory** is not a new-theory ticket — it
belongs in that theory's own folder (`cli tickets new --lane theory
--theory <slug>`), because a theory folder is supposed to hold everything
its expert needs.

**History.** Twenty-two of these came from the 2026-08-24 literature
passes (12 from the first, 5 from the second, 5 from the third) and lived
in `docs/superpowers/specs/theories/` until 2026-09-01. They were moved
here because the split had gone exactly as badly as a duplicated status
field always does: **all 22 still read "Status: backlog — not yet proposed
as a theory"** — including the one that had been retired, the two that were
dead, and the four that had become running theories. One document, one
home, one status.

## Before implementing any spec

0. **Does this theory's edge live *between siblings of one Kalshi
   event*? If so, expect to find nothing, and measure before you
   build.** Kalshi lists and quotes the markets inside an event
   *together* — the same makers post the whole ladder or date-set — so
   they come out internally consistent by construction. Three independent measurements in 2026-08, from different
   directions, and no spec anticipated it:

   - **`calendar-arb`** (dead): zero violations at its own
     1c/leg buffer across 10 snapshots. Near-dated date ladders are
     siblings inside ONE event, so basket cost never fell below 1.000;
     cross-event ladders exist only at 1y+ where carry dwarfs a
     cent-scale edge. Study:
     `tickets/study/answer/2026-08-27-calendar-arb-firing-rate/`.
   - **`smile-smoothing`** (dead): at a tradeable liquidity
     floor, **97.6% of 959 strike rungs sat *exactly* on their own
     isotonic fit**, max deviation 1.5c, zero candidates. Deviations
     appeared only in rungs with median volume **0**, where the "mid" is
     an empty book rather than a price. Study:
     `tickets/study/answer/2026-08-29-smile-smoothing-ladder-flatness/`.

   - **`structural_arb`'s NO-basket path** (2026-08-29, exhaustive):
     with the event envelope making Kalshi's `mutually_exclusive` flag
     free, all **6,414** mutually-exclusive events on one board were
     checked directly. **Exactly 1** had a NO-basket costing less than
     its guaranteed payout, at 0.125c/leg against a 1c/leg buffer — **0
     tradeable**. This is the strongest form of the finding: not a
     sample, the whole board, from the direction most favourable to the
     thesis. See `theories/structural_arb/NOTES.md` 2026-08-29.

   - **combo-vs-leg, the first CROSS-event probe** (2026-08-30): Kalshi's
     92 listed `*COMBO` markets are 2x2 partitions (DD/DR/RD/RR) whose
     *legs* sit in separate events, so `{DD, DR}` is an **exact
     synthetic** of the standalone leg market — an arbitrage identity
     that holds *whatever* the correlation between legs, unlike a
     product-of-legs test. **34 exact riskless constructions at
     executable prices with real fees: 1 profitable at zero buffer
     (+0.05 pts), 0 at a 1c/leg buffer.** Mid-price gaps up to 6.4 pts
     exist but sit entirely inside the spread, and the most liquid case
     (`KXBALANCEPOWERCOMBO`, 10.7M volume, 1c spread) has the
     *smallest* gap. Study:
     `tickets/study/answer/2026-08-30-parlay-markup/` (rule-0 section).

   - **`aggregation-gap`, the second CROSS-event probe** (2026-09-01):
     `KXNFLWINS` lists 32 teams as 32 separate *events*, each a complete
     1..17 ladder, so `E[wins] = sum_N P(wins>=N)` is exact and the 32
     expectations must sum to `272 - ties` — a conservation law across
     events, correlation-free like the combo synthetic. The mid sum is
     274.25 against a true `<= 272`, but the bid/ask band is
     **[264.03, 284.47]** and straddles it; both riskless baskets fail at
     executable prices (all-NO costs 279.96 against a 272 floor). The
     companion House-seats case turned out **not to be an identity at
     all** — `KXHOUSEWINSTATE` carries one `>k` strike per state, so
     `E[seats]` is bounded rather than determined. Evidence:
     `tickets/study/answer/2026-09-01-aggregation-gap-probe/`.

   The cheap check is a one-board measurement of the *dispersion the
   thesis needs*, run before any theory scaffolding — every one of the
   above was settled in well under a session that way. Cross-**event**
   relative value is **no longer untested**: the combo-vs-leg channel is
   now measured and flat, by the strongest available test (an exact
   synthetic, correlation-free), and the NFL conservation law is a
   second, independent identity measured flat the same way. What remains
   open is cross-event relative value where no arbitrage identity
   exists — a *forecast* disagreement between two separately-priced
   events, which is a different and much weaker claim than a violated
   identity.

   **Matching trap, recorded because it is silent:** KS/NH/OH list
   governor and senate contests from **different election cycles** under
   adjacent tickers (`GOVPARTYKS-27-D` beside `SENATEKS-26-D`). Matching
   legs by ticker year-suffix pairs the wrong election and produces a
   confident, wrong arbitrage. Match on `close_time`.

0b. **A pre-registration must name its inclusion rules and its power
   floor, not just its contrast.** Naming only the hypothesis leaves the
   rules that decide who is *in* the sample undeclared — and those rules
   routinely span the entire conclusion. Two independent failures on
   2026-08-29, hours apart, in different theories, by different sessions:

   - **`calibration_harvest`**: the pre-registered bar fixed a four-way
     horizon ordering. It failed. A two-group long-vs-short collapse was
     then chosen *after* seeing where the sign flipped and published as
     "pre-registered" (t 3.50 — also the best of three available splits).
     The proposed replacement estimator was no safer: a day-level
     regression on horizon-bin rank reads **+0.50/t 0.26** including days
     with ≥2 horizon bins and **+3.14/t 2.68** including only days with
     ≥3. The inclusion rule *was* the result. Retracted; see that
     theory's `NOTES.md` 2026-08-29 (correction).
   - **`series-bias-mining`**: the bar used *series count* as its power
     proxy. Count says nothing about whether a series can resolve the
     3–6pt effect worth betting; the median tested series had a minimum
     detectable effect of **13.5 pts**, so "0 of 17 flagged" meant *not
     measured*, not *calibrated*. See
     `tickets/study/investigation/2026-08-29-series-bias-mining/`.

   **Caveat found the same day, by the floor's own author:** an
   SE-based power floor is **not outcome-neutral for binomial data.**
   Bernoulli variance is `p(1−p)`, so a series with an extreme win rate
   has a small SE and therefore a small MDE — the floor preferentially
   admits exactly the candidates where a large gap can sit. Measured in
   `series-bias-mining` pass 2: mean win rate **0.864** among series with
   MDE ≤ 8 versus **0.829** among MDE > 8, and the single flagged series
   was the most extreme in the population *and* had the lowest MDE. So
   prefer a floor on `n` and `n_days` where the design allows it, and
   where an SE-based floor is used, **report the outcome composition of
   who passed it** so the selection channel is visible rather than
   silent.

   So write down, before looking: the contrast **and** who is in the
   sample **and** the smallest effect the design can detect. If the
   answer to the last one is larger than a theory-grade edge, the run
   cannot inform the question and should be resized before it is run,
   not reinterpreted after. Report a failed pre-registered test *as
   failed*; a better-looking cut found afterwards is a hypothesis for the
   next population, never the headline.

0c. **If the theory scans many candidates, give it a negative control
   — a slice whose answer is already known.** A screen that reports hits
   tells you nothing on its own; a screen that reports *no* hits on data
   known to be fairly priced is a screen whose next positive is worth
   reading. Build the control into the run, not into a follow-up.

   Worked example: `series-bias-mining` carried `mention_family`'s ten
   series as a control, because that family is known from a
   full-coverage backtest (n=3,441, −1.53 net) to be priced fairly. All
   ten came back non-significant. That is the one thing that run
   established about its own guard — and it cost nothing, because the
   series were already in the population.

   Two rules that follow: measure the control, and **keep it out of the
   multiple-comparisons family** — correction budget spent on series
   nobody would promote only dilutes the real tests.

0d. **Build the fixtures before touching real data.** A fixture universe
   with a planted effect among known-null cases catches the bugs that
   look like discoveries. `series-bias-mining`'s caught one that would
   have flagged **every calibrated series**: its statistic was net of
   fees, and fees are a near-constant −1 to −3pt offset, so a perfectly
   calibrated series scored −1.12 with the *same sign in both halves* —
   sailing through the split-sample guard that existed to stop exactly
   that. A guard defeating itself, and it would have read as a finding.
   Score a bias gross; report net beside it for whether the bias is
   bettable.

0e. **Validate a replacement signal on the cases the old one got
   *wrong*, never on the cases it got right.** When a new signal is
   meant to replace or repair an existing method, its agreement with
   that method is measured almost entirely on the population the old
   method already handled — which is free, uninformative, and reads as
   overwhelming confirmation. The only number that matters is its hit
   rate on the **residue**: the cases the incumbent missed, which is the
   entire reason a replacement was wanted.

   This shape produced **four** wrong or nearly-wrong conclusions in the
   repo on 2026-08-29 alone, in three different sessions, twice *after*
   the lesson had been written down:

   - `structural_arb` had 2,042 cached `mutually_exclusive` flags, every
     one `false`, and read it as "Kalshi never sets this flag". The board
     is 46% `true`. The cache was conditioned on "the NO-basket
     arithmetic already cleared", which selects almost perfectly against
     genuine partitions. One step from cutting a working guard.
   - `deadline-drift` round 5 adopted that same flag on the strength of
     **98% agreement** with the screen's 2,687 existing exclusions — all
     of them markets the screen *already caught*. On the residue the flag
     is `false` **every time**, and the round came in at 12% against a
     10% bar.
   - The price-partition test in the same round was fitted on round 4's
     misses and projected ~8%; out of sample it contributed nothing.
   - Rounds 1–4 of that classifier each tuned against the previous
     round's misses, which is why the rate plateaued rather than
     converged: 40 → 20 → 12 → 16.

   So before adopting a replacement signal, **partition the population by
   whether the incumbent was already right, and report the new signal's
   rate on each half separately.** A single pooled agreement figure hides
   exactly the half you are buying the signal for. If the residue is too
   small to measure, that is the finding — the signal is unvalidated
   where it counts, not confirmed.

0f. **Measure the effect at *executable* prices before building
   anything — not at the mid, and not gross of fees.** This is the single
   most common way an idea dies here, and it has now killed or gutted
   eight of them. It is not eight findings; it is one finding, eight
   times:

   - `calendar-arb` — basket cost never fell below 1.000 at executable
     quotes, though mid-price violations existed.
   - `smile-smoothing` — ladder deviations appeared **only** in rungs
     whose median volume was 0, where the "mid" is an empty book.
   - `structural_arb` — 1 NO-basket violation in 6,414 events, 0
     tradeable; 12 of 16 observed violations at zero open interest.
   - **combo-vs-leg** — mid gaps up to 6.4 pts on an exact synthetic,
     sitting entirely inside the spread; 0 profitable at a 1c/leg buffer.
   - `series-bias-mining` pass 3 — 23% of observations at asks of
     0.980–0.995 realizing 0.801, because the ask was a placeholder
     rather than an offer.
   - `mid-band-favorite-fade` — the composition control *passed*
     (−3.90, t=−3.30) and the idea still died on arithmetic: two asks
     sum to 1 + spread, so `fav_net + dog_net == −(spread + fees)`
     exactly. **A one-sided net edge of −N does not imply +N on the
     other side; it implies −(round_trip − N).** Both sides lose.
   - `calibration_harvest` — 47 cells cleared both floors across three
     complete populations and **zero** cleared fees.
   - **`aggregation-gap`** (2026-09-01) — the House-seats gap is positive
     at mid in **5 of 5** complete-coverage states (mean +0.196 seats) and
     **negative at worst-case executable quotes in 5 of 5** (mean −0.240).
     The line needing no adjudication: the spec's own most favourable
     worst-case gap was **+0.073 seats** and the measured fee cost of the
     basket capturing it is **$0.073** — the same number, so fees take
     100% of the spec's own edge before a 14-month lockup. Evidence:
     `tickets/study/answer/2026-09-01-aggregation-gap-probe/`.

   Two consequences worth stating separately. **A liquidity filter must
   be a real one** — spread *and* open interest, never a price cap, and
   never a candle's per-period `volume` mistaken for a lifetime figure.
   And **the literature this backlog was built on mostly measures at
   mid or gross**: two of its own sources say so outright, Angelini &
   De Angelis verbatim ("executable-style returns … are negative") and
   Becker's −1.12% per taker trade. An effect reported in a paper is a
   reason to look, never a reason to expect it to survive the ask.

0g. **A market whose title states a cumulative deadline is not
   necessarily nested — check whether the series *resets per period*.**
   Any theory that pairs markets by parsing dates out of titles will
   eventually pair two legs of a rolling monthly (or weekly) series and
   read them as a date ladder. They are not one: each contract opens on
   the first of its own period and only counts events from its own open,
   so both legs can lose and the "arbitrage" is a classifier error.

   Worked example, measured 2026-09-03 in
   `tickets/study/answer/2026-08-27-calendar-arb-firing-rate/`
   (Addendum, Exception 1). `KXTRUMPSAYMONTH-26OCT01-ANTI` ("Will Trump
   say 'Antifa' before Oct 1, 2026?") against
   `KXTRUMPSAYMONTH-26SEP01-ANTI` ("…before Sep 1, 2026?") looks
   perfectly nested and prices 0.64 against a September leg that has
   **already resolved YES at ask 1.00**. Under real nesting the October
   leg would have to be ~1.00; the pair "costs" 0.65, i.e. a claimed
   **35-cent riskless arbitrage on a two-sided board**.

   Three things to carry:

   - **The price is the cheapest detector, and it beats reading the
     rules text.** The rules of both legs above say "before <date>" and
     are, read literally, genuinely nested. The *listing convention* is
     what differs, and the quote reveals it for free. A gap that large
     on a liquid pair is a bug in your grouping, never a find — treat
     "too good" as a classifier alarm.
   - **A strike-aware key does not catch this.** Rule 0's `KXU3MAX`
     trap is two markets sharing a subject and differing in *threshold*,
     fixed by joining `floor_strike`/`cap_strike`/`strike_type` to the
     key. Here the strikes are identical and the *period* differs, so
     the same fix does not apply. Compare `open_time`, not just
     `close_time`: a later-closing leg that also opens later is a reset,
     not a superset.
   - **It is nearly invisible, which is why it needs writing down.** The
     two legs of a monthly series are on the board together only during
     the rollover — about ten hours, once a month. It appeared in 2 of
     21 stored captures, and both were inside that window. A probe run
     on any other day sees nothing and concludes the population is
     clean.

1. `python -m tools.cli ideas search "<slug>"` — confirm nothing has
   changed since the spec was written (each is registered under its slug;
   check `status` and `outcome`).
2. Use the `propose-theory` skill to formalize the chosen idea into
   `theories/<slug>/` with a THEORY.md before writing procedure code
   (some tickets say otherwise in their own opening line —
   `maker-mode-execution` lands as changes to `tools/` rather than a
   theory, and `new-market-anchor` starts as a measurement study).
3. Follow the repo contracts in CLAUDE.md. Most-missed: entry prices are
   the **ask**, never the mid; every recorded edge carries an
   `edge_basis` (`measured`/`model`/`prior` — never a felt sense); any
   LLM in the decision path requires provenance records and prompts on
   disk; any change to a decision procedure bumps the theory version;
   backtest tier A means **no outcome judgment anywhere in the decision
   path** (amended 2026-08-29, 0f06265 — it previously read "no LLM
   anywhere". A *structural* gate, one whose answer cannot be influenced
   by the outcome, keeps tier A if it meets CLAUDE.md's four conditions
   and its contamination probe has actually been run; an unrun probe
   counts as outcome judgment. The preference order is unchanged and
   still binds: data, then code, then a structural gate, then outcome
   judgment).
4. Reuse the validated patterns already in the repo: the price-bin bucket
   pattern in `mention_bucket.py` (`PRICE_BINS`, `bucket_for_price`,
   measured rates via `tools/buckets.py`) — that theory was retired and
   its code deleted 2026-09-02, so read the pattern at `git show
   450db428ec0e7542852fae6484ab8370aaeddfad:theories/insider_bias/
   mention_family/mention_bucket.py`, and read `theories/retired/
   mention_family/RETIRED.md` first: the procedure those bins drove
   measured **dead** at full coverage (−1.53pts net, n=3,441). The bin
   *mechanics* are the reusable part, not the claim. The
   code-gate-with-category-report pattern in
   `theories/insider_bias/insider_judgment/gate.py`, the tier-A backtest
   pattern in `theories/insider_bias/insider_judgment/backtest.py`, and
   fee math from `tools/sizing.py`. The session board comes from
   `tools.board.get_board(conn)` — never `markets.list_open()` directly.

## Assessment rubric

Every spec carries an Assessment block scoring three metrics, 1–5 each.
These are **ordinal priors for prioritization** with stated reasoning —
the same epistemics as a confidence bucket, never a calibrated
probability — and they are deliberately honest: two specs score their own
likelihood 2/5 because the best available evidence points against them.

- **Applicability (A):** how directly the theory serves this repo's use
  case — a manual Kalshi bettor asking "what's the best bet right now."
  Considers whether output is directly bettable on Kalshi, candidate
  frequency, and capital/holding profile.
- **Implementability (I):** data in hand vs external, code and
  statistical complexity, dependencies on other specs, and effort to
  first evidence.
- **Likelihood of success (L):** strength and directness of the evidence
  (measured on Kalshi > measured on an analogous market > mechanism
  argument), threat of fee/spread erosion, competition, and how much
  sample it takes to prove.

## The scoreboard

A/I/L are each spec's own Assessment scores under the rubric above —
ordinal priors with stated reasoning, never calibrated probabilities.
**The priority column is gone.** It was a second numbering for the same
22 ideas, and the registry's insertion order is the one every ticket
already cites (`idea 17 (maker-mode-execution)` is row 16 of the old
table). Slugs are the identity; there are no numbers.

Sorted by composite, then by outcome.

| spec | lens | A | I | L | Σ | effort | what happened |
|------|------|---|---|---|---|--------|---------------|
| calibration-harvest | signed price/horizon/domain cells | 5 | 5 | 4 | 14 | S | **retired** — 0 of 47 cells cleared fees |
| series-bias-mining | per-series base rates | 4 | 4 | 4 | 12 | M | **study** — pass 3 not measured by its own bar |
| [maker-mode-execution](open/2026-08-24-maker-mode-execution.md) | execution layer: spread capture | 5 | 4 | 3 | 12 | M | **open — see the note below** |
| structural-arb | within-event logic | 3 | 5 | 3 | 11 | S | **built** — 0 tradeable violations |
| no-side-premium | YES/NO side bias (optimism tax) | 4 | 4 | 3 | 11 | S–M | **built** — null at its 8-day bar |
| [overreaction-fade](open/2026-08-24-overreaction-fade.md) | political move reversal | 4 | 4 | 3 | 11 | M | open |
| deadline-drift | affirmative-event hazard | 4 | 3 | 3 | 10 | M | **built** — shipping allowlist uninformative |
| parlay-fade | combo markup vs product-of-legs | 3 | 3 | 4 | 10 | M | **study** — 0 tradeable at a 1c buffer |
| ~~smile-smoothing~~ | ladder shape | 4 | 3 | 3 | 10 | M | **DEAD 2026-08-29** |
| ~~calendar-arb~~ | date-ladder nesting logic | 3 | 4 | 3 | 10 | S | **DEAD 2026-08-27** |
| [news-drift](open/2026-08-24-news-drift.md) | underreaction continuation | 4 | 4 | 2 | 10 | M | open |
| [weather-model-gap](open/2026-08-24-weather-model-gap.md) | ensemble forecast vs market | 4 | 3 | 3 | 10 | M | open |
| settled-but-trading | resolution-source staleness | 4 | 3 | 3 | 10 | M–L | **killed** — favourable case quotes 1.000; the residual is rules ambiguity |
| [new-market-anchor](open/2026-08-24-new-market-anchor.md) | issuance mispricing (study) | 3 | 5 | 2 | 10 | S | open |
| [cross-venue-fair-value](open/2026-08-24-cross-venue-fair-value.md) | cross-venue convergence | 3 | 3 | 3 | 9 | M | open |
| [econ-anchoring](open/2026-08-24-econ-anchoring.md) | consensus anchoring on releases | 3 | 3 | 3 | 9 | M | open |
| [attention-model](open/2026-08-24-attention-model.md) | Wikipedia attention vs box office | 3 | 3 | 3 | 9 | M | open |
| [metaculus-gap](open/2026-08-24-metaculus-gap.md) | forecaster aggregate vs market | 2 | 3 | 3 | 8 | M | open |
| [whale-follow](open/2026-08-24-whale-follow.md) | proven-wallet mirroring | 3 | 2 | 3 | 8 | L | open — see `block-trade-whale-follow` |
| [vol-crossing](open/2026-08-24-vol-crossing.md) | barrier-option model | 3 | 3 | 2 | 8 | M | open |
| implication-graph | cross-event logic | 2 | 2 | 3 | 7 | L | **killed on class evidence** — cross-event identities measured flat twice |
| [insider-flow-radar](open/2026-08-24-insider-flow-radar.md) | anomalous fresh flow | 2 | 2 | 2 | 6 | L | open |

### Read this table honestly: it has been anti-predictive so far

Ten of the 22 have been acted on, and **not one has produced a bettable
edge.** The four highest-composite specs are retired, not-measured, open,
and sterile respectively. Meanwhile every result this repo actually has
came from somewhere else: `insider_judgment` (the only positive segment,
`strong-moderate-no` at +3.76 net over 90 clusters) predates this backlog
entirely; `mention_family` was found by accident while backtesting that
screen; `taker_flow` came from a find-theories session reading an outside
paper. Even `no_side_premium`, which *is* from this backlog, got its
founding evidence from the mention and insider full-coverage backtests
rather than from the literature its spec cites.

Twelve untouched specs is a real selection caveat — the top ones were
built first and so had more chances to fail. But the pattern is one to
weigh before treating a high composite as a reason to build: **an idea
sourced from a paper and an idea sourced from this repo's own settled
rows are not equally likely to survive contact with the ask.** Rule 0f is
the mechanism behind most of it.

### Two consequences for what to pick up next

**`maker-mode-execution` is the most undervalued ticket here.** It is the
only spec that attacks rule 0f directly — its opening line is *"Every spec
in this backlog prices entries at the ask, paying the spread"* — it scores
Applicability 5/5, it is tier A, and section 5 reads *"Data requirements:
None new."* It sat at row 16 purely on a sequencing argument: *"maker-mode
needs at least one measured theory live before its paired backtest has
anything to run on."* **That blocker is cleared.** There are 3,394 settled
`insider_judgment` rows (328 in the proven slice), 1,908 from the
`deadline_drift` walk, and 72,010 priced settled markets in the
series-bias corpus. Its stated hard part — an honest fill simulator —
also got easier than the spec assumed: `tools/kalshi/trades.py` did not
exist on 2026-08-24, and the per-trade aggressor feed lets a replay check
real crossing prints rather than inferring fills from a candle bid path.

**Four specs in this table spawned successors, and all four successors
have now closed — three of them dead.** The successor pattern is worth
naming because it worked: each one took a parent spec, stripped the
expensive part, and measured the cheapest decisive thing instead.

| successor | what it stripped from its parent | closed |
|---|---|---|
| `aggregation-gap` | `implication-graph` minus the LLM edge construction | **dead** — mid sum 274.25 vs a true ≤ 272, but the band [264.03, 284.47] straddles it; both riskless baskets fail at the ask |
| `accumulation-decay` | `settled-but-trading` category (a), made concrete | **dead** — the post-window bucket quotes 1.000; a *perfect* forecaster nets median +0.00 |
| `block-trade-whale-follow` | `whale-follow` minus the cross-venue matching | **dead on population** — 5 blocks in 498,918 trades, and 3 of the 5 are one decision |
| `kalshi-taker-flow-toxicity` | `maker-mode-execution`'s coin, other side | **built** — now the `taker_flow` theory |

Three of those four kills landed in **one session each**, and two of them
took their parent down with them (`implication-graph` and
`settled-but-trading` are both closed above, on their successors'
evidence). **Nothing obliges a spec to be measured before it is built** —
a theory proves itself when it is implemented — but those four are the
record of what an afternoon can be worth when a thesis is cheap to check
and expensive to build. Rule 0's dispersion check and rule 0f's
executable-price rule are the two that keep firing.

Paired designs: news-drift ↔ overreaction-fade share one joint
sign-measurement (each claims only the cells measured its way);
cross-venue-fair-value's pair store is reused by whale-follow and
insider-flow-radar; structural-arb's sibling grouping is reused by
smile-smoothing. (new-market-anchor was to ride calibration-harvest's
cell matrix; that theory is retired, so it needs its own population.)

## Considered and parked (with why)

- **Weekend/overnight staleness** — real phenomenon, but needs intraday
  precision at the staleness window and the user bets at human hours;
  revisit if candlestick granularity supports a Monday-open drift the
  user could catch.
- **Poll-gap models for political markets** — modeling-heavy,
  election-cyclical, sharp competition; revisit after the cheap
  structural ideas are exhausted. Keyless public polling data exists.
- **Order-book market making / continuous spread capture** — wrong shape
  for a manual bettor; the one-sided, theory-gated version is
  [maker-mode-execution](open/2026-08-24-maker-mode-execution.md).
- **Kalshi leaderboard copying** — Kalshi exposes no per-trader *identity*,
  which is why the wallet-based ideas
  ([whale-follow](open/2026-08-24-whale-follow.md),
  [insider-flow-radar](open/2026-08-24-insider-flow-radar.md)) route
  through Polymarket. **Partly overturned 2026-09-01:** "impossible by
  construction" was too strong. Kalshi publishes `taker_side` on every
  executed trade and an `is_block_trade` flag on negotiated size — not
  identity, but enough for a whale signal with no cross-venue matching
  at all. See the open tickets `kalshi-taker-flow-toxicity` (which
  became theory `taker_flow`) and `block-trade-whale-follow`.
- **LLM forecast-gap betting** — puts an introspected probability at the
  center of the procedure; the compliant reframing is `insider_judgment`
  (formerly `insider_bias`), which already exists. Parked as redundant, not wrong.
- **Settlement spillover** (round 3) — when market A settles, related
  markets (same entity, same series family) may reprice slowly; trade
  the lag. Parked because the related-market identification is either
  LLM-judgment (implication-graph's cost profile) or so conservative it
  rarely fires, and the clean mechanical subset — date ladders — is
  exactly calendar-arb.
  Revisit angle: mine candlestick history for *measured* co-movement
  pairs first, then trade only pairs with demonstrated propagation lag.
- **Same-game parlay correlation pricing** (round 3) — pricing
  correlated legs properly is a real modeling edge (an AMM-design
  literature exists), but it is the hard version of
  parlay-fade; parked until
  the cross-game version has evidence.

## Reference folder — for reviewers

`reference/` holds what a reviewing model needs to check the specs'
claims without redoing the research:

- [Evidence ledger](reference/2026-08-24-evidence-ledger.md) — **start
  here when reviewing**: every load-bearing quantitative claim across
  the 22 specs, mapped to its source and graded A (primary read in
  full, transcribed with locators) / B (primary located,
  summary-verified) / C (practitioner, directly read) / D (secondhand
  aggregation — treat as a lead, not evidence). The ledger names the
  claims that still need verification at implementation time.
- [Le 2026 reading notes](reference/2026-08-24-le-2026-calibration-notes.md) —
  full Table 4/5 transcriptions, isotonic checks, dataset description.
- [Angelini & De Angelis 2026 reading notes](reference/2026-08-24-angelini-deangelis-2026-notes.md) —
  impact coefficient, Table 6 drift matrix, the verbatim
  executable-returns negative.

## Shared sources

Papers marked **read in full** were extracted and read during the
2026-08-24 sessions; quoted numbers come from their text and are
transcribed with locators in `reference/`.

- [Le 2026 — Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics](https://arxiv.org/pdf/2602.19520) (**read in full**; [replication repo](https://github.com/namanhzz/prediction-market-calibration)) — 353M trades; Politics slopes 1.32–1.83 (compressed toward 50%), Weather 0.69–0.87 short-horizon (too extreme), Sports 1.74 / Crypto 1.36 at 1mo+; universal horizon component 0.99 → 1.32; price 0.75 → 0.886 realized (Politics), 0.691 (Weather); large political trades compress more (1.74 vs 1.19).
- [Angelini & De Angelis 2026 — When Do Markets Fully Process Public Information?](https://arxiv.org/pdf/2606.07811) (**read in full**) — Kalshi NBA in-play: 0.64-for-one impact adjustment, predictable drift, worse when illiquid+salient; **not profitable net of bid–ask at minute scale**.
- [Whelan — Makers and Takers](https://www.karlwhelan.com/Papers/Kalshi.pdf) ([CEPR](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)) — 300k+ contracts; favorite-longshot bias net of fees; taker losses.
- [Becker — The Microstructure of Wealth Transfer in Prediction Markets](https://www.jbecker.dev/research/prediction-market-microstructure) ([dataset](https://github.com/jon-becker/prediction-market-analysis)) — takers −1.12%/trade vs makers +1.12%; optimism tax (YES underperforms NO by up to 64pp at longshot prices); category inefficiency Finance 0.17pp → Entertainment 4.79–7.32pp.
- [Palumbo 2026 — A Microstructure Perspective on Prediction Markets](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6325658) — Kalshi NFL passive LPs profitable (~$29M/season aggregate) but directionally exposed; "underwriters, not market makers."
- [Clinton & Huang 2025 — Prediction Markets? $2.4B in the 2024 Election](https://ideas.repec.org/p/osf/socarx/d5yx2_v1.html) — negative daily autocorrelation, cross-exchange divergence, Kalshi 78% vs Polymarket 67% accuracy.
- [Reichenbach & Walther 2025 — Accuracy, Skill, and Bias on Polymarket](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5910522) — 478M trades; YES/default overtrading; no general longshot bias once side is accounted for.
- [Dalen 2025 — Toward Black-Scholes for Prediction Markets](https://arxiv.org/pdf/2510.15205) — event vega; pre-close uncertainty jitter.
- [Campbell & Sharpe (JFQA 2009)](https://www.federalreserve.gov/econres/steven-a-sharpe.htm) + [FEDS 2026 series](https://www.federalreserve.gov/econres/feds/2026.htm) — consensus anchoring; forecast errors predictable; re-confirmed 2012–2026.
- [Berg, Nelson & Rietz — Accuracy and Forecast Standard Error of Prediction Markets](https://www.biz.uiowa.edu/faculty/trietz/papers/forecasting.pdf) — Intrade horizon miscalibration.
- [Interest-bearing positions and the long-horizon problem](https://arxiv.org/pdf/2602.21091) — capital-lockup mechanism.
- [PredictionTalk 40-paper survey](https://predictiontalk.org/d/14-ai-parsed-40-papers-on-pm-inefficiencies-here-are-5-im-going-to-trade/) — practitioner aggregation: rebalancing-arb magnitudes, temporal-lag competition, wash-trading rates (Columbia SSRN 5714122: ~25% of PM volume; 45% sports), on-chain insider lead windows.
- Cross-venue gap documentation: [trevorlasn.com](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works), [predictionhunt](https://www.predictionhunt.com/blog/why-same-market-different-prices-kalshi-polymarket), [public arb bot](https://github.com/ImMike/polymarket-arbitrage).
- [arXiv 2607.14430 — Prices, Probabilities, and Parlays](https://arxiv.org/abs/2607.14430) — 23M Kalshi moneyline trades; legs essentially perfectly calibrated in mid-life TTE buckets; cross-game parlays systematically overpriced vs product of legs, growing with leg count. Combo mechanics: [Sportico RFQ explainer](https://www.sportico.com/business/sports-betting/2025/kalshi-parlay-combo-rfq-explainer-1234877038/), [Penny Parlay criticism](https://www.gamblinginsider.com/news/180114/kalshi-penny-parlay-worst-bet-in-america-smallest-bettors-buying-it).
- Weather practitioner documentation: [botforkalshi](https://www.botforkalshi.com/blog/kalshi-weather-trading-strategy), [PillarLab playbook](https://pillarlabai.com/blog/how-to-trade-temperature-markets-kalshi/) — per-station settlement, ~2°F fee cushion, 8pp entry floors, NWS bias patterns; keyless data at [api.weather.gov](https://api.weather.gov) and [Open-Meteo](https://open-meteo.com).
- [Mestyán, Yasseri & Kertész 2013](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0071226) — Wikipedia activity predicts opening box office ~a month ahead.
- Forecaster-aggregate evidence: [platform-comparison work](https://manifund.org/projects/comparing-forecasting-platform-accuracy), [Metaculus's own markets-vs-polls argument](https://www.metaculus.com/notebooks/17599/why-i-reject-the-comparison-of-metaculus-to-prediction-markets/).
- Polymarket wallet-copy ecosystem: [Polycopy](https://polycopy.app/best-polymarket-traders), [copy-score backtest](https://polyloly.com/blog/polymarket-insider-tail-backtest-46-percent-roi), [wallet-selection traps](https://medium.com/@0xmega/how-to-find-the-best-polymarket-wallets-to-copy-trade-without-getting-rekt-26dd65123324).
