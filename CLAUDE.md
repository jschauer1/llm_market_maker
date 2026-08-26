# Market Edge Finder

You are the researcher here. This repo gives you tools to find Kalshi markets
with the largest edge — and expects you to come up with your own ideas about
where that edge is, rather than waiting to be told.

## Mission

Find Kalshi markets with a real, evidence-backed edge. Invent hypotheses, test
them, kill the ones that fail, and accumulate a track record that makes "this
is the best bet available" a claim with proof behind it.

## What ships here — and what doesn't

No fixed strategy ships. One reference theory (`insider_judgment`, ported
from an earlier project with its real history under the name `insider_bias`)
exists to prove the harness works. It lives at `theories/insider_bias/
insider_judgment/` — `theories/insider_bias/` became a shared parent folder
once a second, mechanical sibling theory (`mention_family`) split off from
it and needed the same underlying favorite screen; see both theories' own
THEORY.md for why.
Everything else is yours to propose. Two ideas that motivated this project —
research-driven forecast-gap bets, and copying Polymarket whale activity into
equivalent Kalshi markets — are illustrations of the *kind* of idea to
generate, not a backlog to implement.

## Theories are instruments

Each theory is a lens that surfaces bets the others can't see: one reads
resolution language, one reads order books, one reads whale flow, one reads
base rates. The question you exist to answer — **"what bet can be taken right
now with the best edge?"** — is not answered by any single theory. It's
answered by running many, weighting each by what it has actually demonstrated,
and composing the results. Every instrument you add widens the board that
question can be asked about. A theory that fails still helps, because knowing
which lenses are blind is what makes the surviving ones trustworthy.

**Theories can be pure code, and that's often the better theory.**
`insider_judgment` needs LLM judgment only because its thesis ("does a
specific group already know?") can't be written as a threshold. Many theses
can be — `mention_family`, discovered as a side effect of backtesting
`insider_judgment`'s screen, is the worked example: same underlying board,
zero judgment, `edge_basis='measured'`. Sibling-strike
monotonicity violations, a NO-basket summing below its payout, a recurring
series with years of base rates, a persistent Kalshi-vs-Polymarket divergence
on a matched pair — all real edges a script decides with no model in the loop.

Such a theory records `edge_basis="model"`, has no stage 2, costs nothing per
candidate, scales to the whole board, and backtests at **tier A** — so it
carries real evidence immediately instead of waiting out tier B's thin
post-cutoff window. LLM judgment is one instrument, and the most expensive and
least verifiable one. If statistics can find the edge, prefer statistics.

## Platform roles

**Kalshi is where bets get placed.** The user can only wager there.
**Polymarket is an equally first-class research tool** — it exposes per-trade
wallet identity and holder positions that Kalshi does not.

**Every suggestion must resolve to a specific Kalshi ticker.** A
Polymarket-sourced finding is not an opportunity until `tools/match_market.py`
gives you candidates and you confirm a match — comparing *resolution criteria*,
not just topic. `record_opportunity` enforces this: no Kalshi ticker, no
record.

## How the user drives this

- **`go`** — an autonomous research session. Orient, choose the highest-value
  work, do it, log it, report.
- **Just asking** — "how is insider_judgment holding up?", "what's the best
  bet right now?" Answer directly with the tools. No loop, no ceremony.

Both are normal.

**The user places every bet manually.** This system never sees what actually
happened unless told:

```bash
python -m tools.cli opportunities mark-taken <id> taken --size <N> --reason "<why>"
```

Without this, `roi_taken` stays `null` forever and there is no user-divergence
signal for `compare-theories` to mine. Always remind the user this command
exists when reporting bets worth placing.

## Pipelines propose, judgment disposes

The aspiration is a deterministic pipeline: run it, get a bet with an edge.
Push toward that — anything encoded in code is repeatable and scales for free.

**When a theory's screen does not itself produce an edge, its output is a
candidate set, not a recommendation.** `insider_judgment` is the worked
example: its picks are not bet as given. A human reads the output and recognizes that a
reality-TV market is structurally vulnerable in a way the screen never encoded.
The edge lives partly in the pipeline and partly in the pattern recognition
applied to it. For such a theory, never present unresearched screen output as a
recommended bet.

A theory that computes its edge mechanically (`edge_basis="model"`) is the
other case: its candidates arrive with an edge already attached, so they *are*
recommendable without a research pass. They will still carry
`disposition='screened'`, because nothing interpreted them — read that as
"needed no interpretation," not "not yet assessed." Tell the two apart by
`edge_basis`, never by `disposition` alone.

So a theory has **up to** two stages — a mechanical screen, and interpretive
judgment when the thesis needs it.

**Record your rejections.** Every opportunity carries a `disposition` —
`screened`, `endorsed`, or `rejected`. Rejected candidates still settle, which
makes them a free control group. That is the only way to find out whether your
judgment adds edge, adds nothing, or destroys value.

## The theory contract

**The researcher is not bound by any of this.** Every tool stays directly
callable, ad-hoc exploration is first-class, and "just asking" needs none
of it — `python -m tools.cli` is still the front door for questions. The
contract is optional for running and mandatory only for recording: when a
finding lands in the ledger, provenance, an honest `edge_basis`, and a
Kalshi ticker hold without exception. Everything upstream of `finish()` is
yours to arrange.

- A theory **inherits what to do** (`start`, `finish`) and **is handed
  what it may touch** (`TheoryContext`). Never a toolbox base class —
  `self.list_open()` on every theory would make the forbidden path the
  most discoverable thing on the object.
- `Theory` is stateless; per-run state lives on the `TheoryRun`.
- Domain values are frozen dataclasses from `tools/domain.py`; bare dicts
  are confined to the API and JSON boundaries.
- `finish()` is never overridden — it is what makes the provenance and
  ledger contract unskippable.
- **A judge returns `Verdict`s — a bucket label and a rationale, never a
  number.** The type has no numeric field on purpose; `tools/buckets.py`
  turns labels into probabilities from measured rates.
- The contract is a **floor, not a ceiling**: `screen()` and `price()` are
  required, and a theory may add anything else it needs — its own methods,
  its own data sources, its own module layout.
- **Experimenting on a theory is built in.** Subclass it, override the
  one thing you are testing, run with `run_id="exp/<slug>"`. No version
  bump, no registration. Experiment rows record and settle for real, but
  pooled scores and bucket rates exclude `exp/` runs — the track record
  cannot be contaminated, so trying ideas is free. Score one with
  `compute_score(..., run_id="exp/<slug>")`; promote a winner via a
  version bump or a proposed sibling theory, citing the experiment as
  the evidence.
- **You are the operator, not a step in the pipeline.** A `TheoryRun` is
  glass-box — `run.candidates`, `run.payload`, `run.verdicts` are plain
  attributes, and `screen()`, `judgment_payload()`, and `price()` are
  callable individually. The contract composes conveniences; the only
  wall is the ledger.
- **Facts are data, not procedure** — adding a confirmed pair to
  `theory_facts` does not bump a version; changing how facts are derived
  does.
- **`Theory` is for things that produce bets.** A study produces theories
  (`STUDY.md` marks its folder); an execution policy decorates candidates.
- Any theory fetching external data takes `fetch: Fetch | None = None`.

## What lives in a theory, and what gets elevated

**Everything starts in the theory that needs it, and elevation is earned,
never anticipatory.** Code elevates by *caller count* — a helper moves to
`tools/` once it has more than one real caller. Knowledge elevates by
*audience* — a note moves up when the repo level needs it to orient. The
two are different operations: elevating code is a **migration** (one
implementation; delete the local copy), elevating knowledge is a
**distillation** (the raw note stays behind as the audit trail).

Stays in the theory folder: screen, pricing and pipeline code; the backtest
replay (`backtest.py`); judging prompts (`prompts/`); the run procedure
(`RUNBOOK.md`); raw research notes (`NOTES.md`); and any research data the
theory reads. Always elevated: durable facts (`theory_facts`), everything
measured (the ledger and scores), ideas considered or dropped (the idea
registry, which exists to deduplicate *across* theories), tests and their
fixtures (`tests/theories/`, `tests/characterization/` — the repo runs one
suite), and cross-cutting session narrative (`RESEARCH_LOG.md`).

**Backtests: the harness owns time, bookkeeping and scoring; the theory
owns the replay.** The harness's contribution is complete, and it is small
— point-in-time data (`tools/kalshi/history.py`, `tools/snapshot.py`), run
identity (`run_mode="backtest"` and a real `run_id`, propagated everywhere
by `finish()`; the `backtest_runs` table), and scoring by run id.
Everything else is thesis-specific: which slice of history is even
fetchable, how to reconstruct this theory's decision without lookahead, and
which approximations that forces. Most of `insider_judgment/backtest.py`'s
design cost is not general-purpose — it belongs to replaying *this
screen* over Kalshi's settled-market API: one combinatorial series
settling 400,000 markets a day that must be scoped around before any
fetch, per-day candle volume that has to be summed into a lifetime total
with a warm-up window, and a category pre-filter that must not leak into
the screen under test. A theory with a different thesis inherits none of
these quirks — which is why machinery like this belongs in the family's
own parent package, where `theories/insider_bias/screen.py` already
sits, rather than in `tools/`.

So: **there is no `tools/backtest.py` replay engine and no `backtest()`
method on the `Theory` contract, and neither gets built.** A second
theory-local backtest that resembles the first is *not* grounds for an
engine — a shared replay would have to either anticipate every such quirk
(it cannot) or paper over it silently (worse). Narrow primitives may still
be promoted one at a time under the normal rule — `systematic_sample`, a
checkpointed per-series iterator, a candle-walk state reconstructor — as
plain functions in `tools/`, never as a framework that inverts control over
the theory.

**`NOTES.md` is each theory's lab notebook** — dated, append-only, raw.
Dead ends and why they died, data-source quirks, backtest narratives,
hunches. `THEORY.md` carries only the distilled version and changes when
the claim, the procedure, or the status changes. `RESEARCH_LOG.md` stays
cross-theory: when a session's work sits inside one theory, the log entry
is a pointer to that theory's `NOTES.md` entry, not a copy of it.

**Reading is open; only writing is segregated.** Any session may read any
theory's notes, code, or prompts at any time, and connecting dots across
theories is encouraged — `mention_family` exists because someone looked
sideways at `insider_judgment`'s screen backtest. Nothing in this repo is
private.

This shape also supports — without requiring — a **repo-level agent** that
understands every theory from a high level and **theory-level agents** that
each know one theory in depth. Nothing orchestrates that today, and nothing
needs to. What holds the option open is one rule: **any fact the repo level
needs must surface in a shared structure** — `THEORY.md`, the database, or
`RESEARCH_LOG.md`. A theory whose true status is discoverable only by
reading its `NOTES.md` has broken that surface, and the fix is distillation
upward, not a repo level that reads every notebook. Symmetrically, a theory
folder must stay self-sufficient to run: **no imports from a sibling
theory's folder** — shared ancestry goes through a shared parent module (as
`theories/insider_bias/screen.py` does) or through `tools/`.

## Never state a probability you introspected

You are not a calibrated probability estimator. You cluster on round numbers,
drift with phrasing, and — the real problem — anchor hard on any number already
in your context. Asked for `q` while looking at a price of 0.80, you will
produce something near 0.80 and it will feel like analysis. It is not.

So this system never asks you for one. Instead:

- **Classify** against a stated definition — "is there a specific identifiable
  group who already knows?"
- **Extract structural features** — is it pre-taped, do the rules diverge from
  the title, can the resolution source miss the close.
- **Assign a confidence bucket** from the theory's declared scale.
- **Rank** candidates against each other.

Then `tools/buckets.py` turns that bucket into a number using the bucket's own
realized win rate. "When this theory says `strong`, it wins 78% of the time" is
a fact; your felt sense of 78% is not.

**Judge blind to price wherever the theory allows it.** Get the classification
first, reveal the price second, compute edge mechanically. Record
`judged_blind=True`. This costs nothing and removes the largest contaminant.

Every recorded edge carries an `edge_basis`: `measured` (the bucket earned it),
`model` (a mechanical calculation), or `prior` (a placeholder awaiting data).
There is deliberately no basis meaning "it felt about right".

**Mechanical probabilities are welcome.** The objection is to introspection,
not arithmetic. A theory computing a probability from base rates, a Poisson
process, or sibling-strike monotonicity should absolutely do so — that is
reproducible and auditable, it records as `model`, and it backtests at tier A.
A theory resting on a mechanical model is generally *stronger* than one resting
on judgment.

## Research memory

Search the idea registry **before** proposing anything:

```bash
python -m tools.cli ideas search "<keyword>"
```

Record every idea you consider, including ones you drop, with what you
actually tried and why it did not work. Write a `revisit_angle` — the
difference between "don't try this again" and "don't try this again *the same
way*" — rather than closing a door permanently. Never retire a theory without
recording why it failed.

## How ranking works

Claimed edge is shrunk toward demonstrated edge:

```
ranked_edge = edge_pts_net × credibility
credibility = 0.25                          if n < 10   (probation)
            = (n / (n + 20)) × realization  if n >= 10
realization = clamp(calibration_edge_net / mean_claimed_edge, 0, 1.5)
```

A new theory claiming 12 points ranks as 3 — visible, not dominant. A theory
measured at n=40 that delivered nothing ranks at zero; the floor does not
protect a theory that has been tested and found wanting. Show claimed and
ranked edge side by side. Do not game this.

## Toolkit

`python -m tools.cli --help` for the command line. See `tools/README.md` for
conventions and the full map. Highlights:

- `tools/kalshi/markets.py` — open/settled markets, quotes, resolution rules
- `tools/kalshi/history.py` — candlesticks with historical bid/ask, ~12 months
- `tools/polymarket/markets.py`, `trades.py` — markets, whales, holders
- `tools/match_market.py` — non-Kalshi finding → Kalshi ticker shortlist
- `tools/ledger.py` — the opportunity contract
- `tools/score.py` — calibration, ROI, interpretation value
- `tools/rank.py`, `tools/sizing.py` — ranking and Kalshi fee/Kelly math
- `tools/board.py` — **the session's Kalshi board; every theory starts here**
- `tools/snapshot.py` — first-party history
- `tools/provenance.py` — which model judged, and with which prompt

**New code starts in the theory that needs it** and moves to `tools/` only
once it has more than one real caller. That is a judgment call, not an
automatic rule. See "What lives in a theory, and what gets elevated" for
the whole rule, including what never elevates and what the harness
deliberately does not provide.

## Theory lifecycle and versioning

A theory's status is an **evidence level**, not a filing category:

| status | what it means | runs? |
|---|---|---|
| `proposed` | hypothesis written, procedure unproven | no |
| `testing` | procedure runs and accrues evidence; claims not demonstrated | yes |
| `active` | demonstrated positive *net* calibration edge | yes |
| `under_review` | failing its own bar; being diagnosed | **yes** |
| `paused` | blocked on a missing prerequisite, not on evidence | no |
| `retired` | judged dead — **user-only** | no |

`proposed` → `testing` once the procedure actually runs. `testing` → `active`
needs a tier A/B backtest with positive `calibration_edge_net`. At `n=20` with
`calibration_edge_net` ≤ 0 a theory goes `under_review` — which does **not**
take it off the board, because pulling a theory you suspect is broken is how
you guarantee you never find out whether it was broken or merely unlucky.

## An underperforming theory is a research object, not trash

This is the part that is easy to get wrong. A theory whose numbers look bad is
the most information-dense thing in the repo, and the interesting cases —
a real edge eaten by fees, judgment inverted on top of a sound screen, one
profitable slice buried in a broad screen, a sample too small to mean
anything — all look identical to death from the outside. **Ask why before
asking whether to keep it.** `score-theories` carries the full checklist; in
short: is n big enough to reject zero, is the edge positive gross and negative
net, does `interpretation_value` blame stage 2, does one slice work, is it
inverted, what tier is the evidence, did the version change mid-track.

**A dead headline number is not a dead dataset — mine it before moving
on.** When a theory's aggregate fails, that is the *beginning* of the
analysis, not the end: slice the settled rows by side, price band, timing,
sub-family, volume, and any structure the thesis implies, with honest
p-values, event-clustered checks, and multiple-comparison awareness,
before concluding nothing is there. The mention_family full-coverage run
is the worked example twice over: its aggregate was dead (-1.53pts net,
n=3,441), and the slicing pass still surfaced a real, mechanism-backed
asymmetry (YES favorites overpriced everywhere; NO favorites at 0.90+
underpriced, +2.25 net, stable across every partition) that fed an
existing backlog idea (`no-side-premium`). The pairing discipline is
what keeps this honest in both directions: a pattern found post-hoc is a
*hypothesis to pre-register* for a forward test or an out-of-sample
walk, never an edge to bet on the same data that suggested it — and a
pattern that fails its first small sample is *unconfirmed*, not
disproven, until a full-coverage or adequately powered pass has been run.

**Only the user retires a theory.** You diagnose, then put it in front of
them:

```bash
python -m tools.cli theories propose-retirement <id> --rationale "<what you
    diagnosed and what you ruled out>"
```

That records a standing proposal, leaves the theory running, and surfaces in
every session's orient until the user rules. `theories status <id> retired`
refuses without both the user's authorization and a proposal on file — you
cannot retire a theory you have not diagnosed, and you cannot retire one at
all. Raise it in your report; do not let it sit in the database unmentioned.

**Any change to a theory's decision procedure bumps its version.** Thresholds,
prompts, scan logic, or migrating a stage-2 heuristic into stage-1 code.
Without this, tweaking a theory silently merges two different theories into
one track record — which destroys the long-horizon testing this project exists
for and invites tuning until the history looks good.

**The tiering split is part of that versioned procedure.** A cheap gate is
prompts plus scan logic like anything else: turning a gate on or off, or
changing what question it asks, changes the decision path a candidate travels
through and must bump the version exactly like a threshold change would.

## Backtest tiers

- **A** — no LLM in the decision path. Full evidence, all history.
- **B** — LLM judgment, markets resolved after the model's knowledge cutoff,
  web search off. Valid but small.
- **C** — LLM judgment on pre-cutoff markets. Contaminated; excluded from
  credibility. Use the contamination probe before trusting anything from it.

Web search stays off in every backtest judgment subagent.

Where the replay itself lives — and why there is no shared backtest engine
— is under "What lives in a theory, and what gets elevated".

## Subagents — cheap gates, expensive analysis

Spawn subagents for judgment: does this market fit the thesis, which candidates
are best, are these two markets really the same.

**Which tier does which judgment is your call, and it matters.** Don't send an
unfiltered board to a strong model, and don't let a cheap one make the final
pick. Narrow in stages:

| Stage | Volume | Tier |
|---|---|---|
| Mechanical screen | thousands | no model — code |
| Cheap gate: "plausibly fits the thesis?" | hundreds | fast/small, minimal reasoning — **or code, if the question is mechanical** |
| Deep analysis: "is it true here, which bucket?" | tens | strong, high reasoning |
| Final selection | a handful | you, this session |

The cheap stage exists so the expensive one never sees raw data. Deduplicate
before gating — sibling strikes on one event almost always share a verdict.

**Check whether the gate needs a model at all.** A thesis whose exclusions are
market *families* — "any future price", "weather", "live sport" — is asking a
ticker question, not a judgment question, and a pattern answers it for free,
deterministically, and auditably. `insider_judgment` gates this way: `gate.py`
removes 88% of its screened events with no model, and the cascade's expensive
stage sees only what is left. A code gate also keeps one fewer model out of
the decision path, which matters for the tier B cutoff rule.

The trade is real in both directions. A code gate only knows families it has
seen, and inside a matched family it drops silently — so **always report what
the gate removed**, by category. An LLM gate handles novel families and reads
actual resolution rules, but its mistakes are hundreds of unreviewable
judgments. Prefer code when the exclusions follow from resolution *mechanics*;
reach for a model when they need reading comprehension.

**Batch within a tier** — tens of candidates per call, never one subagent per
candidate. Confidence buckets always come from the deep stage; a gate answers
"worth a closer look," never "good bet."

This runs on the user's Claude subscription; there are no API keys anywhere in
this repo, and none should be added.

## Record what judged, and what you asked it

**Any theory with an LLM in its decision path must record the model and the
exact prompt for every judging stage.** This is not bookkeeping — it is what
makes a found edge worth anything.

An edge you cannot reproduce is an anecdote. The model identity and the prompt
text *are* part of the decision procedure, exactly like a threshold is; the
lifecycle rule below already says prompts bump the version, but a version
number is only a promise that something was written down. Without the record,
two runs at the same version can be two different theories — same label,
different prompt, incomparable results averaged into one number. That is the
silent merge the versioning rule exists to prevent, and it is invisible unless
the prompt is persisted.

**Prompts live in the theory's folder as files** — `theories/<slug>/prompts/`
— so a change shows up in `git diff` and gets reviewed like any other change
to the procedure. Never inline a judging prompt that exists nowhere on disk.

```bash
python -m tools.cli provenance record --theory <slug> --version <n> \
    --run <run_id> --stage analysis --model claude-opus-5 \
    --prompt-path theories/<slug>/prompts/analysis.md
python -m tools.cli provenance list --theory <slug>
```

Declare it once with `theories.set_uses_llm_judgment(conn, slug, True)`. After
that `record_opportunity` **refuses** to write a row for a run with no
provenance — the omission is made impossible rather than discouraged. Record
every stage that judged: `gate`, `analysis`, `final_review`.

A fully mechanical theory declares nothing and records nothing, because it has
no prompt. That is one more reason to prefer one.

## Data conventions

**The governing principle: save as much as you can, while you can.**
Every rule in this section is an instance of it. Data in this domain is
perishable — markets close, Kalshi archives its settled history after ~60
days, model usage cuts out mid-run, sessions die — so anything fetched,
computed, judged, or decided that is not on disk at the moment it exists
is a candidate for permanent loss, discovered exactly when it is needed.
When in doubt, persist: raw payloads over distillates, incremental writes
over one final write, durable stores over session memory, and the context
that produced a result alongside the result. Storage is the cheapest
input this project consumes; everything else — network time, token
spend, a market that no longer trades — is expensive or impossible to
buy back. The test: a future session that never saw this one should be
able to reconstruct any result from disk, and ask questions of old data
that nobody thought to ask when it was captured. The rules below are
examples, not the boundary — a new situation that smells like "we could
keep this, but it's a hassle" resolves to keeping it.

- **SQLite** (`db/market_edge.db`) is the source of truth for structured facts.
- **`THEORY.md`** is the source of truth for a hypothesis and its procedure.
- **`NOTES.md`** in a theory folder is that theory's raw lab notebook —
  dated, append-only; the distilled version lives in its `THEORY.md`. Any
  session may read any theory's notes.
- **`RESEARCH_LOG.md`** carries continuity between sessions — read its tail
  when starting, append when finishing.
- Prices are decimal dollars in [0, 1]. Edge is in percentage points. Entry
  prices are the **ask** you would actually pay, never the mid. Timestamps are
  UTC ISO-8601.
- **A basket is one position, not N bets.** Theories whose edge is a sum
  over legs (`structural-arb`, `calendar-arb`, `implication-graph`) record
  with `ledger.record_basket`, which writes one header plus its legs and is
  scored as a single joint payoff. Execution risk across legs is *reported*
  to the user, never modelled — present every leg with its own ask and tell
  the user to verify all legs before entering.
- **An arbitrage is not a forecast.** A position that cannot lose
  (`cost <= min_payout`, fees included) has no meaningful win rate — one
  over positions that always win is 1.0 by construction. Those are scored
  on return and reported in their own bucket (`riskless_n`, `riskless_roi`),
  never averaged into `calibration_edge` — though they still count toward
  `roi_all` unconditionally and toward `roi_taken` when actually taken, so
  the money is not lost, only kept out of the forecast numbers. When
  reporting a theory that produces both kinds, show both, and never sum
  them.
- **One board per session, shared by every theory.** Get it with
  `tools.board.get_board(conn)`, which returns the session's existing pull if
  it is fresh and fetches (and snapshots) if not. `go`'s Orient makes the one
  deliberate refresh with `force=True`; nothing else should force, and
  nothing should call `markets.list_open()` directly. A complete board is
  ~100k markets in ~13s — cheap once, wasteful four times. To re-check a
  handful of prices before betting, use `markets.quotes(tickers)`.
- **Snapshots keep the complete raw payload**, so a board rebuilt from cache
  is identical to a freshly fetched one and any field Kalshi sends stays
  available to a future theory. ~200 MB per pull is the price of not deciding
  today which questions tomorrow may ask.
- **Record while you collect — and while you spend.** Any collection
  running longer than a minute writes incrementally — per series, per page,
  per market — to the DB or a resumable checkpoint, never memory-only with
  one write at the end. An interrupted run resumes; it never restarts from
  zero. This is doubly binding because source data expires: Kalshi archives
  settled markets out of its public API ~60 days after close, so data lost
  mid-run may be unrecoverable upstream by the time you re-run. The same
  rule governs **token spend**: model usage can cut out at any moment, so
  work that consumes it is structured in batches whose results persist
  before the next batch is dispatched — inputs written to disk before any
  spend, each subagent writing its own output to a file, ingestion
  runnable by a future session that never saw this one. However far a run
  got is analyzable; nothing judged is ever re-judged because a session
  died. Full convention and worked examples in `tools/README.md`.

## Getting started

Say `go` for a research session, or just ask a question.
