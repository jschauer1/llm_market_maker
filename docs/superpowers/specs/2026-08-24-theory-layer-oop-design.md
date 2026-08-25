# Theory-Layer OOP — Contracts and Value Types

Date: 2026-08-24
Status: implemented — see docs/superpowers/plans/2026-08-24-theory-layer-oop.md
Scope: `tools/domain.py` (new), `tools/theory.py` (new),
`tools/registry.py` (new), `theories/**`, both platform clients,
`tools/ledger.py` + `tools/score.py` (experiment-lane exclusion only),
`tools/README.md`, `CLAUDE.md`, `.claude/skills/**`
Behavior change: **none** — see section 3.1, non-regression is a hard
constraint · Theory version bumps: none intended
Depends on:
[multi-leg positions](2026-08-24-multi-leg-positions-design.md) — executed
first, because `Candidate`'s shape depends on it

**In one line:** every theory becomes an object a subagent can be handed and
run start-to-finish, returning one uniform result — with two required
methods, everything else optional, and nothing that exists today lost.

**And the constraint that outranks it:** the LLM is the researcher, not a
workflow executor. Every tool stays directly callable, ad-hoc work stays
first-class, and this contract is optional for running and mandatory only
for recording. See section 3.3 before reading the design as a procedure.

## 1. Problem

The repository has no object-oriented structure at all. Measured on
2026-08-24 across ~4,700 non-test lines in 30 modules:

| Construct | Count |
|---|---|
| Domain classes | 0 |
| `@dataclass` / `Protocol` / `ABC` / `TypedDict` / `NamedTuple` | 0 |
| Methods (`self.`) | 0 |
| Classes of any kind | 3 — all bare `Exception` subclasses |

This is documented policy, not drift. `tools/README.md` opens with "Not a
framework — there is no base class to learn and no plugin registry."

That rule was added in commit `6aef7c6` — the 47th of 95 — when the
repository contained exactly one theory. It was correct then, and it is
consistent with the promotion criterion stated forty lines below it in the
same file: *"generalizing early produces a shared layer full of
single-caller abstractions, which is worse than a little duplication."*

What has changed is that the promotion criterion has been met. There are
now two theories with unrelated entry points, and twenty-two more specced in
`docs/superpowers/specs/`. The rule that fired on "one caller" has not been
revisited since the second caller arrived.

Three concrete costs follow.

### 1.1 No theory contract

`.claude/skills/find-edge/SKILL.md:36` instructs the session to *"Open the
theory's `THEORY.md` and follow its Stage 1 — mechanical screen section."*
Running a theory therefore requires reading prose into context and
hand-writing the call. The two existing theories share nothing structurally:

```
# theories/insider_bias/insider_judgment/pipeline.py
run_mechanical_stages(board, now) -> dict
    # {"board_markets", "screened_markets", "events", "gate_counts",
    #  "gated_out", "survivors", "survivor_markets", "payload"}

# theories/insider_bias/mention_family/mention_bucket.py
find_candidates(board, now, max_days_ahead) -> list[dict]
rank(candidates, rates, top_n) -> list[dict]
record(conn, ranked, run_id, run_mode, confidence_suffix) -> list[int]
```

The per-session cost of this scales linearly with theory count — the one
quantity this project exists to grow.

### 1.2 Every domain value is an untyped `dict`

`tools/kalshi/markets.py:54` and `tools/polymarket/markets.py:50` each build
an undocumented dict shape, and the two disagree on every field name:

| Concept | Kalshi key | Polymarket key |
|---|---|---|
| identity | `ticker` | `market_id` |
| text | `title` | `question` |
| ask | `yes_ask` | `best_ask` |
| close | `close_time` | `end_date` |
| implied p | `mid` | `implied_prob_yes` |

There is no type to read, so field names are rediscovered by grepping
function bodies. 46 functions across 9 modules also take
`conn: sqlite3.Connection` as a threaded first argument.

### 1.3 Ledger and provenance boilerplate is re-written per theory

`tools/ledger.py:74` `record_opportunity` takes 24 keyword arguments.
`mention_bucket.record()` is 60 lines that are mostly one call to it, plus
its own `record_provenance` call. Theory #3 will write both again from
scratch.

This is the cost that matters most, and it is not a token cost. CLAUDE.md's
stated design philosophy is to make omissions *impossible rather than
discouraged* — which is why `record_opportunity` already refuses rows for a
theory with no provenance. Hand-assembly of a 24-argument call at every
theory defeats that principle one level up: a theory that passes the wrong
`edge_basis`, forgets `judged_blind`, or mis-derives `edge_pts_net` writes a
row the ledger accepts and the credibility math silently mis-ranks. With
twenty-four theories that is a matter of time, not of care.

## 2. The finding that justifies the design

The abstraction is not being invented. It already exists, simulated with
dict-spreading.

`theories/insider_bias/screen.py:133` — a candidate *is* a market plus three
fields:

```
candidate = dict(market)
candidate["fav_side"] = side
candidate["entry_price"] = entry_price
candidate["days_to_close"] = days
```

`theories/insider_bias/mention_family/mention_bucket.py:184` — a scored
candidate *is* a candidate plus three more:

```
scored.append({**c, "edge_pts_net": edge_pts_net,
               "edge_basis": edge_basis, "bucket": bucket})
```

A three-level layering — `Market` to `Candidate` to `ScoredCandidate` — is
present in the code and written down nowhere. Both theories share it
*exactly*, because `mention_family.find_candidates()` calls
`insider_bias.screen.screen()` unmodified and narrows the result.

This distinguishes a real abstraction from a fake one. The design below
names a structure that exists rather than imposing one that does not.

## 3. Constraints and non-goals

### 3.1 No functionality may regress

**This is a restructuring, not a rewrite. Every capability that exists today
exists afterwards, unchanged.** The refactor earns its place by making the
same behavior easier to reach — never by trading a feature for tidiness.

Concretely, none of the following may be lost, simplified away, or deferred
"until the port is done":

- Every `tools/cli.py` subcommand and flag keeps working, with identical
  JSON output.
- `run_mechanical_stages`'s full funnel — every count, `gate_counts`
  included — survives, because CLAUDE.md requires reporting what the gate
  removed by category.
- `mention_family`'s `rank` / `rank_preview` split survives *as two
  functions*. They exist separately on purpose: a wider horizon changes what
  `edge_basis` a caller may honestly attach, and collapsing them into one
  function with a flag is "easy to call the wrong way" (its own docstring).
  The contract must not force them into one `price()`.
- `confidence_suffix` and its bucket-pooling behavior survive; it is what
  keeps untested-horizon rows out of the validated bins' measured rates.
- Every validation in `ledger.py` survives, including the cents-vs-dollars
  and NaN guards.
- `assert_blind` and its `BANNED_KEYS` survive unchanged.
- Backtest paths, snapshot fidelity, and `board.get_board`'s cache
  semantics survive.
- Single-leg scoring is bit-for-bit unchanged. Once the multi-leg spec has
  landed, `compute_score` on a copy of the live database returns identical
  numbers before and after this migration — the `legs` shape must cost the
  single-leg majority nothing.

**Test rule:** the existing suite passes at every phase with no test
deleted, skipped, or weakened. A test that must change to accommodate the
refactor is a red flag to be examined, not edited. Tests may be *added*
freely.

If a capability genuinely cannot be carried across, that is a finding to
report to the user — not a decision to make inside the refactor.

### 3.2 Just enough structure, and no more

The architecture exists to remove repetition and make omissions impossible.
It must not become a cage that dictates what a theory is allowed to be. The
project's whole thesis is that theories are *instruments* — "one reads
resolution language, one reads order books, one reads whale flow, one reads
base rates" — and a contract that only fits the two theories written so far
would quietly narrow the search space the project exists to widen.

So the contract is deliberately thin: two required methods, `screen()` and
`price()`. Everything else has a default. And it keeps explicit escape
hatches:

- **A theory may add any method, attribute, or module it wants.** The base
  class is a floor, not a ceiling. `tools/README.md`'s rule that theory-local
  code lives in the theory folder until it earns promotion is unchanged.
- **A theory may ignore `TheoryContext` and reach further** if its thesis
  needs data no current theory needs — a weather model, a Metaculus feed,
  an on-chain query. `ctx` is what the harness *offers*, not a whitelist of
  what a theory may touch.
- **`screen()` may return an empty list** and that is a valid run, not an
  error. A theory whose board has no candidates today has still run.
- **`price()` may compute an edge any way it likes** — buckets, Poisson,
  monotonicity, cross-venue divergence — provided `edge_basis` is honest.
  The contract constrains the *reporting* of the edge, never its derivation.
- **A theory may decline the shared `finish()` path** by calling
  `finish(dry_run=True)` and recording nothing, when a run is exploratory.

The one thing a theory may **not** do is bypass the ledger and provenance
contract when it records. That is the constraint the structure exists to
impose; everything else is a convenience it offers.

**Litmus test for any future addition to `Theory`:** if a plausible theory
from the backlog in `docs/superpowers/specs/` could not be expressed under
the proposed rule, the rule is too tight. Section 9's stub-theory test is
the mechanical version of this check.

### 3.3 The LLM is the researcher; the platform serves it

The most important constraint, and the one most easily lost in an
architecture document: **this structure is scaffolding for an LLM
researcher, not a workflow the researcher must obey.**

CLAUDE.md opens by saying so — *"You are the researcher here. This repo
gives you tools to find Kalshi markets with the largest edge — and expects
you to come up with your own ideas about where that edge is, rather than
waiting to be told."* An architecture that turns that researcher into a
executor of `Theory` subclasses would defeat the project, however clean the
class diagram looked.

So the following are guarantees, not concessions:

- **Every tool remains directly callable, standalone, exactly as today.**
  Nothing becomes private, nothing is hidden behind the contract.
  `screen.screen(board)`, `markets.quotes(tickers)`,
  `score.bucket_rates(...)`, `ledger.list_opportunities(...)` all keep
  working as plain function calls. The contract adds a path; it never closes
  the existing one.
- **"Just asking" stays cheap.** CLAUDE.md documents two modes — `go` and
  simply asking a question — and calls both normal. Answering "how is
  insider_judgment holding up?" must never require constructing a
  `TheoryContext`, instantiating a `Theory`, or knowing this spec exists.
  `python -m tools.cli` stays the front door for questions.
- **Ad-hoc research is first-class.** Not every investigation is a theory.
  The researcher may write throwaway analysis, probe a hunch across the
  board, join two tools in a way nobody anticipated, or explore a dataset
  with no intention of recording anything. There is no requirement that
  exploration be expressed as a `Theory` subclass, and no penalty for
  never becoming one.
- **A theory may put the LLM wherever its thesis needs it.** The
  `screen()` / `judgment_payload()` / `price()` shape is the common case,
  not a mandate. A theory whose thesis requires judgment inside pricing, or
  three judgment passes, or none, may do that — provided `edge_basis`
  honestly reports what produced the number.
- **The researcher may change the platform.** This architecture is itself a
  hypothesis. If it obstructs real work, that is evidence against the
  architecture, and revising it is in scope for any session — the same
  standard a theory is held to.

**The single non-negotiable is the ledger boundary.** Explore however you
like; compose anything; ignore every class in this document. But when a
finding is *recorded as evidence* — a row in the opportunities ledger, a
claim that a theory found an edge — provenance, `edge_basis`, and the Kalshi
ticker requirement hold without exception. That is the whole purpose of the
structure and the only thing it insists on, because the track record is
what makes every other claim in this repo worth anything.

Put the other way: **the contract is optional for running and mandatory for
recording.** Everything upstream of `finish()` is the researcher's to
arrange.

### 3.3a Experimenting on a theory is built in

The versioning rule makes changing a theory's procedure deliberately
expensive — a bump orphans the accrued track record, which is the right
price for changing what a version number means. Left alone, that rule
would also tax the thing this project runs on: trying ideas. So the
counterweight is designed in rather than left to workarounds.

**The experiment lane.** A run whose `run_id` starts with `exp/` is an
experiment: a real forward test that records, settles, and scores like any
run — and that pooled scoring and pooled bucket rates **exclude**. The
production track record cannot see it, so there is nothing an experiment
can contaminate and no reason to hesitate before starting one.

- **Trying a variant is a subclass and a run id.** Override the one method
  under test on the existing theory class and run it with
  `run_id="exp/<slug>"`. No registration, no version bump, no new folder,
  no ceremony. Rows record under the parent theory's id, so the foreign
  key holds and the lineage stays visible.
- **An experiment is scored on demand, never by default:**
  `compute_score(..., run_id="exp/<slug>")` and
  `bucket_rates(..., run_id="exp/<slug>")` see exactly its rows.
- **Promotion is the existing lifecycle.** An experiment that earns
  evidence becomes a version bump on its parent (or a proposed sibling
  theory), citing the `exp/` run as the evidence that justified the
  change. One that fails gets an ideas-registry entry with a
  `revisit_angle`, like any other dead idea.
- **`dry_run=True` remains the tier below:** explore without recording
  anything at all.

**Glass box, not pipeline.** The contract's run state is plain,
inspectable attributes — `run.candidates`, `run.payload`, `run.verdicts` —
and every stage (`screen()`, `judgment_payload()`, `price()`) is an
ordinary method callable on its own. `TheoryRun` composes conveniences; it
gatekeeps nothing. The researcher can stop between any two stages, look,
and decide. The single wall remains the ledger (section 3.3).

### 3.4 Out of scope

Explicitly **out of scope**. These stay as plain functions:

- `tools/sizing.py`, `tools/buckets.py`, `tools/rank.py` — pure functions
  over numbers. A `KellyCalculator` class is a file to open in exchange for
  what a signature already says.
- `tools/http.py`, `tools/db.py` — thin I/O boundaries. `get_json` itself is
  unchanged; the section 4.8 `fetch` seam is a parameter added to the two
  client modules that call it, not a rewrite of the transport.
- `tools/cli.py` — argparse dispatch; JSON in, JSON out.
- Repository/gateway objects owning the sqlite connection. The `conn`
  threading is real friction but removing it touches every DB-backed module
  for modest gain. Deferred, not rejected; revisit if the theory layer
  proves the pattern.
- Any change to `theories/**` *decision logic*. Thresholds, price bands,
  gate categories, bucket boundaries, and screen predicates are frozen.

`tools/README.md`'s instinct — *"read one tool end to end and you know how
to write the next one"* — remains correct for leaf tools and is preserved.

## 4. Design

### 4.1 Value types — `tools/domain.py`

Frozen dataclasses, composition over inheritance, with delegating
properties so common access stays terse.

```python
@dataclass(frozen=True, slots=True)
class Market:
    platform: str                 # "kalshi" | "polymarket"
    ticker: str                   # Kalshi ticker or Polymarket conditionId
    title: str | None
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    mid: float | None
    spread: float | None
    volume: float | None
    open_interest: float | None
    status: str | None
    is_open: bool
    close_time: str | None
    open_time: str | None
    result: str | None
    rules_primary: str | None
    event_ticker: str | None = None
    series_ticker: str | None = None
    raw: dict = field(default_factory=dict, repr=False, compare=False)
```

`Market` is the *unified* shape. `normalize()` in each platform client maps
its own wire format onto it, which is where the Kalshi/Polymarket field
divergence in section 1.2 gets resolved rather than merely documented.

```python
@dataclass(frozen=True, slots=True)
class Leg:
    market: Market
    side: str                     # "yes" | "no"
    price: float                  # the ask actually payable, never the mid

@dataclass(frozen=True, slots=True)
class Candidate:
    legs: tuple[Leg, ...]
    days_to_close: float

    @property
    def is_basket(self) -> bool: return len(self.legs) > 1
    @property
    def cost(self) -> float: return sum(l.price for l in self.legs)

    @property
    def key(self) -> str:
        """Stable identity, valid for every shape: the event key
        (event_ticker, falling back to ticker) for a single leg; the
        sorted leg tickers joined with '+' for a basket. Verdicts are
        routed by this key (section 4.4), and siblings deduped into one
        judgment share it — which is how one verdict reaches them all."""

    # single-leg conveniences; each raises on a basket rather than
    # silently returning leg 0 and dropping the rest
    @property
    def ticker(self) -> str: ...
    @property
    def entry_price(self) -> float: ...
    @property
    def title(self) -> str | None: ...
    @property
    def event_key(self) -> str: ...
```

**The `legs` shape comes from the
[multi-leg positions spec](2026-08-24-multi-leg-positions-design.md), which
is executed before this migration.** Three backlog theories —
`structural-arb`, `calendar-arb`, `implication-graph` — bet on baskets whose
payoff is joint, and a single-market `Candidate` cannot express one. A
single position is the one-leg case, so the thirteen single-leg backlog
theories and both existing theories are unaffected in substance.

Designing `Candidate` around one market and retrofitting legs afterwards
would mean changing the type underneath two already-ported theories. That is
the expensive order, which is why the dependency runs this way.

```python
@dataclass(frozen=True, slots=True)
class Edge:
    pts_net: float
    basis: str                    # "measured" | "model" | "prior"
    pts_gross: float | None = None
    fee_pts: float | None = None
    model_prob: float | None = None

    @classmethod
    def from_bucket(cls, bucket, entry_price, rates, priors) -> "Edge":
        """Wraps tools.buckets.edge_for; that function stays pure."""
```

```python
@dataclass(frozen=True, slots=True)
class Verdict:
    """What an out-of-process judge may say about a candidate."""
    bucket: str                   # a label from the theory's declared scale
    rationale: str | None = None
```

`Verdict` deliberately declares **no numeric field**, and a conventions
test keeps it that way. This is CLAUDE.md's "never state a probability you
introspected" rule expressed as a type rather than as prose: the judge
classifies against a stated definition and picks a bucket from the theory's
declared scale, and there is no channel through which it could hand back a
probability, a confidence percentage, or an edge instead. Numbers enter
downstream, mechanically — `Edge.from_bucket` converts the label using the
bucket's own realized win rate — and a mechanical theory never sees a
`Verdict` at all.

```python
@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: Candidate
    edge: Edge
    confidence: str | None = None      # the theory's own bucket label
    rationale: str | None = None
    judged_blind: bool | None = None
    disposition: str = "screened"      # screened | endorsed | rejected
```

`ScoredCandidate` being a distinct type makes "an unscored candidate cannot
reach the ledger" a fact the type system enforces, matching the repo's
existing preference for impossible over discouraged.

```python
@dataclass(frozen=True, slots=True)
class ScreenResult:
    """Everything screen() produced: candidates plus the counts that
    describe how it got them. A theory with nothing to count returns a
    bare list[Candidate] and start() wraps it."""
    candidates: tuple[Candidate, ...]
    funnel: dict[str, int] = field(default_factory=dict)
    gate_removed: dict[str, int] = field(default_factory=dict)
```

`ScreenResult` is the channel between `screen()` and the run. The funnel
counts are locals inside today's `run_mechanical_stages`, and a stateless
`Theory` (section 4.4) has nowhere to stash them — so they leave `screen()`
inside its return value, travel on the `TheoryRun`, and surface in
`ScanResult`. Nothing lives on `self`.

```python
@dataclass(frozen=True, slots=True)
class ScanResult:
    """What one theory produced in one run. Uniform across every theory."""
    theory_id: str
    theory_version: int
    status: str                        # the DB registry status
    scored: list[ScoredCandidate]
    opportunity_ids: list[int]
    funnel: dict[str, int]             # board -> screened -> ... -> recorded
    gate_removed: dict[str, int]       # by category; {} when no gate
    judged: bool                       # did stage 2 actually run
```

`ScanResult` is the answer to "return something we can easily understand."
It is uniform across theories, so a session composes results from four
theories without knowing what any of them does internally.

`gate_removed` is not cosmetic. CLAUDE.md requires a code gate to *"always
report what the gate removed, by category"*, because a gate that drops
silently inside a matched family is how a scan reports coverage it never
had. Today that is a per-theory prose obligation. As a field it is either
populated or visibly `{}`, and a theory with a gate that leaves it empty is
a test failure rather than an unnoticed omission.

`OpportunityRecord` — a dataclass mirroring `record_opportunity`'s 24
arguments — is assembled inside `TheoryRun.finish()` and is not part of any
theory's surface.

**Invariants enforced in `__post_init__`:**

- `Market.ticker` non-empty (currently a `ValueError` inside `normalize`).
- `Candidate.entry_price` in `[0, 1]`, rejecting `bool` and `NaN` — the
  logic now in `ledger._validate_entry_price`, moved to construction time
  so it cannot be bypassed by a theory that builds its own dict.
- `Edge.basis` in `("measured", "model", "prior")`.
- `Verdict.bucket` non-empty.
- `ScoredCandidate.disposition` in `("screened", "endorsed", "rejected")`.

The `ledger.py` validators are **retained**, not moved. The ledger is still
callable directly and must stay defensive; the dataclass check is an
earlier, additional line of defence.

### 4.2 Transitional mapping shim

`Market` and `Candidate` implement `__getitem__`, `.get()`, and `keys()`
for one migration window, so existing `market["ticker"]` / `m.get("spread")`
call sites keep working while call sites convert incrementally. `keys()` is
not optional: `screen.py:133` builds each candidate with `dict(market)`,
which requires the mapping protocol, not just item access — a shim without
`keys()` would break the exact call site it exists to carry.

This is a strangler seam, deliberately temporary. It carries a
`# TODO(oop-migration)` marker, a test asserting it is exercised only from
listed modules, and Phase 5 deletes it. Recorded here as a known wart so a
future reader does not mistake it for the intended design.

### 4.3 Injected dependencies — `TheoryContext`

A theory should not import `tools.db`, `tools.board`, or `tools.ledger`. It
receives what it may touch:

```python
@dataclass(frozen=True, slots=True)
class TheoryContext:
    conn: sqlite3.Connection
    board: list[Market]
    now: datetime
    run_id: str = "live"
    run_mode: str = "live"
    judge_model: str | None = None   # set by the dispatching parent; 4.9
```

This is dependency injection, not inheritance, and the distinction is
load-bearing here — see section 4.5 for why a "theory inherits its tools"
base class would be actively harmful in this repository.

A theory written against `ctx` is also testable with a fake context and a
ten-market board, with no live connection and no network.

### 4.4 The theory contract — `tools/theory.py`

`Theory` is **stateless**. All per-run state lives in `TheoryRun`, so the
same instance can be run twice, or interleaved with other theories, without
the runs corrupting each other.

```python
class Theory(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[int]
    uses_llm_judgment: ClassVar[bool] = False
    prompts: ClassVar[dict[str, str]] = {}   # stage -> path in theory folder

    # ---- the two methods a new theory must write ----

    @abstractmethod
    def screen(self, ctx: TheoryContext) -> list[Candidate] | ScreenResult:
        """Stage 1. Mechanical, no model in the decision path. Return a
        bare list, or a ScreenResult when there are funnel or gate
        counts to report; start() wraps a bare list."""

    @abstractmethod
    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts: dict[str, Verdict] | None = None
              ) -> list[ScoredCandidate]:
        """Attach an Edge. verdicts is None on a mechanical run; for a
        judgment theory it maps Candidate.key -> Verdict. Must set
        edge.basis honestly."""

    # ---- optional stage 2 ----

    def judgment_payload(self, cands: list[Candidate]) -> list[dict] | None:
        """Stage 2 input, or None when the theory has no stage 2."""
        return None

    # ---- the workflow, inherited and not overridden ----

    def start(self, ctx: TheoryContext) -> "TheoryRun":
        result = self.screen(ctx)
        if isinstance(result, list):
            result = ScreenResult(candidates=tuple(result))
        return TheoryRun(self, ctx, result)
```

```python
class TheoryRun:
    """One execution of one theory. Holds all per-run state: the
    ScreenResult, the stage-2 payload, and any verdicts applied."""

    def __init__(self, theory, ctx, screen_result): ...

    @property
    def needs_judgment(self) -> bool:
        return self.payload is not None

    @property
    def payload(self) -> list[dict] | None:
        """Stage 2 input; None for a mechanical theory."""

    def apply(self, verdicts: dict[str, Verdict]) -> "TheoryRun":
        """Store out-of-process verdicts on the run. Chainable. Raises
        on a verdict key that matches no candidate's .key."""

    def finish(self, *, dry_run: bool = False) -> ScanResult:
        """price(cands, verdicts) -> provenance -> ledger -> ScanResult.
        Never overridden."""
```

Design notes:

- **Stage 2 is out-of-process by necessity.** The judging model is the
  session or a subagent, not a Python call. The contract therefore exposes
  a payload and accepts verdicts back, rather than pretending `judge()` can
  be executed inside a loop. This is why the pair `judgment_payload` /
  `TheoryRun.apply` exists instead of a single `judge()`.
- **Verdicts travel on the run, never on the candidates.** An earlier
  draft had an `apply_verdicts()` returning candidates with labels
  "attached" — impossible by construction: `Candidate` is frozen with
  `slots=True` precisely to kill the `{**c, "bucket": ...}` pattern, so
  there is no field a label can ride on and no way to bolt one on. The run
  stores `dict[Candidate.key, Verdict]` and `finish()` hands it to
  `price()`, which is where a bucket label meets its measured rate and
  becomes an `Edge`. A candidate the judge did not rule on is the theory's
  call inside `price()` — drop it, or record it `disposition="rejected"` —
  but it is never silently priced as if it had been judged.
- **A verdict is a category, never a number.** The judge's entire output
  channel is `Verdict` — a bucket label and a rationale. It cannot return
  a probability, and `price()` cannot receive one from it. The probability
  is computed mechanically from the bucket's realized win rate
  (`Edge.from_bucket`), or by the theory's own model for a mechanical
  theory. This is the load-bearing reason `price()` and stage 2 are
  separate stages at all.
- **`TheoryRun` exists to carry the state across that gap.** An earlier
  draft of this spec stashed the funnel on the theory instance
  (`self._last_funnel`). That is a latent bug: two theories run in one loop,
  or one theory run twice, would overwrite each other's state. `Theory`
  stays stateless; `TheoryRun` is the per-run object, holding the
  `ScreenResult` (candidates, funnel, gate counts) and the verdicts.
- **`finish()` is concrete and shared.** It performs the provenance write
  (when `uses_llm_judgment`), assembles `OpportunityRecord`, calls
  `record_opportunity`, and returns a `ScanResult`. This is where the
  section 1.3 risk is eliminated. A test asserts no subclass overrides it,
  and `dry_run=True` gives a session the scored candidates without writing
  ledger rows.
- **`finish()` raises if `needs_judgment` and no verdicts were applied.**
  Silently recording a judgment theory's unjudged screen output as if it
  were assessed would misstate `edge_basis` and `judged_blind` on every row.
- **`prompts` is a ClassVar mapping stage to path**, so `finish()` can
  satisfy `provenance.require_provenance` without the session locating
  prompt files via `THEORY.md`.
- **Class-level `id`/`version`** mirror the DB registry row and are checked
  against it at discovery (section 4.6).

### 4.5 Inherit the workflow, inject the dependencies

The convention this design turns on, stated once so it can be cited:

> **A theory inherits *what to do*. It is handed *what it may touch*.**

`start()` and `finish()` are inherited — the Template Method pattern. A
theory gets the provenance write, the ledger assembly, and the `ScanResult`
shape for free, and cannot get them wrong.

Everything else arrives through `TheoryContext`. A `Theory` base class that
also carried the toolbox — `self.list_open()`, `self.record_opportunity()`,
`self.get_board()` — would be actively harmful here, for a repo-specific
reason rather than a stylistic one:

- CLAUDE.md states that **nothing should call `markets.list_open()`
  directly**; every theory goes through `board.get_board()` so one session
  makes one pull rather than four. A toolbox base class would publish
  `self.list_open()` as a method on every theory — making the forbidden
  path the most discoverable thing on the object.
- The same applies to the ledger. `self.record_opportunity()` sitting beside
  the inherited `finish()` gives two ways to write a row, one of which skips
  provenance — reintroducing exactly the failure section 1.3 removes.
- A god base class also has to be instantiated to test anything, and grows
  monotonically: every tool any theory ever needs becomes permanent surface
  on all of them.

Injection inverts all three. A theory can reach only what it was handed, the
context is trivially fakeable in tests, and adding a tool for one theory
does not widen the surface of the other twenty-three.

**The narrow exception:** if a specific helper proves genuinely common
across most theories (`sizing.fee_pts` is the likely first), a small focused
mixin is acceptable. Mixins for demonstrated shared behavior; never a base
class holding the whole toolbox. This mirrors `tools/README.md`'s existing
promotion rule — earn the abstraction with real callers.

### 4.5a Theory-local durable state — `theory_facts`

Five backlog theories keep facts established once and reused every run:
`cross-venue-fair-value` and `metaculus-gap` keep a **pair store** of
confirmed market pairings; `implication-graph` keeps confirmed implication
edges; `whale-follow` and `insider-flow-radar` keep per-wallet scores and
history.

`ctx.conn` alone would let five theories invent five schemas. One shared
table instead:

```sql
CREATE TABLE IF NOT EXISTS theory_facts (
    theory_id      TEXT NOT NULL REFERENCES theories(id),
    kind           TEXT NOT NULL,      -- 'market_pair', 'implication', ...
    key            TEXT NOT NULL,
    value_json     TEXT NOT NULL,
    evidence_json  TEXT,
    established_at TEXT NOT NULL,
    provenance_id  INTEGER REFERENCES judgment_runs(id),
    PRIMARY KEY (theory_id, kind, key)
);
```

**The versioning rule, stated explicitly because both readings are
defensible and a wrong guess is expensive:**

> **Facts are data, not procedure.** Adding a confirmed pair does **not**
> bump the theory's version. Changing how facts are *derived* — the matching
> prompt, the confirmation threshold, the scoring formula — **does**.

Without this written down, five theories each guess, and the pessimistic
guess orphans a track record every time a pair is added. The rule follows
from what versioning protects: the decision *procedure*, not the evidence
the procedure has accumulated.

### 4.5b Construction-time judgment and its provenance

The same pair-store theories declare *"LLM in decision path: match-time only
(per-trade mechanical)"*. An LLM proposes pairs once, a human confirms, and
every subsequent trading decision is pure arithmetic. That is what earns
them a tier A backtest despite having used a model at all.

Section 4.4's contract only models **per-run** judgment
(`judgment_payload` → `TheoryRun.apply`). These theories would set
`uses_llm_judgment=False` so `finish()` does not demand per-run provenance —
correctly, since the per-trade path has no model in it. But the
construction-time judgment still happened, and nothing so far records it.
That is a hole in exactly the guarantee section 1.3 exists to provide.

**Change:** add `"construction"` to `provenance.VALID_STAGES` (today
`("gate", "analysis", "final_review", "other")`), and hang `provenance_id`
off `theory_facts` as above.

A fact produced by a model then carries the model id and prompt that
produced it, keyed to the fact rather than to a run. No new concept — the
existing provenance machinery, pointed at the thing that was actually
judged.

### 4.5c What is not a `Theory`

Three backlog entries do not produce bets, and forcing them through
`screen() -> list[Candidate]` would distort both them and the contract.

**Studies are not theories.** `series-bias-mining` mines every recurring
series and "promotes the survivors into their own bucketed sub-theories";
`new-market-anchor`'s stage 0 is a study that becomes a theory only if a
bias emerges. Their output is bin tables and *theory proposals*, not
candidates.

> **`Theory` is for things that produce bets. A study produces theories.**

Studies stay plain scripts in `theories/<slug>/`, and the repo already has
the machinery for their output: the `proposed` status and the ideas
registry. This needs a line in the conventions, not a class. A study
declares itself with a `STUDY.md` in its folder; discovery skips any
folder carrying one, which is how the conventions test tells a study from
a theory package that forgot its singleton.

A study declares itself: its folder carries a `STUDY.md` where a theory
carries a `THEORY.md`. Discovery (section 4.6) skips study folders, and
the conventions test uses the same marker — so a study is distinguishable
from a theory package that forgot its `THEORY` singleton, rather than
failing the "every theory exposes `THEORY`" check it was never subject to.

**Execution policies are not theories.** `maker-mode-execution` is the
sharper case — it is a **decorator over every other theory**, not a sibling.
It says: rest a limit order at the bid instead of paying the ask, gaining
1–3 points on any candidate whose edge does not decay in minutes. That
contradicts `Leg.price`'s documented meaning ("the ask actually payable,
never the mid") for the entire backlog at once.

It is modelled as a function over a `ScoredCandidate`, never a `Theory`
subclass, and **the taker price remains the recorded baseline**. A maker
fill you did not get is not an edge you earned, so a maker variant is a
*reported alternative* carrying its own fill-rate tracking — never a silent
rewrite of what was paid. Which execution policy was assumed is recorded on
the row.

Its full design is deferred to its own spec: it is a pricing-semantics
question that touches every theory's numbers, and it does not belong inside
a structural refactor (section 8.4).

### 4.6 Discovery — `tools/registry.py`

Each theory package exposes a singleton in its `__init__.py`:

```python
# theories/insider_bias/mention_family/__init__.py
THEORY = MentionFamilyTheory()
```

```python
def discover() -> dict[str, Theory]      # walk theories/, import, collect
def running(conn) -> list[Theory]        # discovered, restricted to
                                         # theories.SCANNABLE_STATUSES
def check_drift(conn) -> list[str]       # mismatches, for a conventions test
```

`discover()` walks for folders carrying a `THEORY.md`; a folder carrying
`STUDY.md` instead is a study (section 4.5c) and is skipped, as is
`_TEMPLATE`. A shared parent like `theories/insider_bias/` — code but no
`THEORY.md` of its own — is traversed, not collected.

**Separation of authority, stated explicitly:** the database is the source
of truth for a theory's *status and version*; the Python class is the source
of truth for its *procedure*. `running()` joins them.

`check_drift` fails loudly on four mismatches: a *scannable* DB row with no
matching class (a `proposed` or `paused` row legitimately has no code yet),
a class with no DB row, a `Theory.version` disagreeing with the
row's version, and a `uses_llm_judgment` ClassVar disagreeing with the DB
flag. The first three prevent the silent-merge failure CLAUDE.md's
versioning rule exists to prevent — a session running v3 code while
recording v2 rows. The fourth matters because that flag routes dispatch
(section 4.9) and gates `finish()`'s provenance demand; drift in it would
misroute a theory or skip a provenance write silently.

Experiments never enter this check: a variant subclass exposes no `THEORY`
singleton, so it is not discovered, and it needs no registry row of its
own because it records under its parent's id (section 3.3a). Drift
policing applies to the production procedure, never to trying things.

### 4.7 Existing theories become adapters first

Phase 3 wraps, it does not rewrite:

```python
class InsiderJudgmentTheory(Theory):
    id = "insider_judgment"
    version = 3
    uses_llm_judgment = True
    prompts = {"analysis":
               "theories/insider_bias/insider_judgment/prompts/analysis.md"}

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        funnel = pipeline.run_mechanical_stages(ctx.board, ctx.now)
        return ScreenResult(
            candidates=tuple(to_candidate(m)
                             for m in funnel["survivor_candidates"]),
            funnel={k: funnel[k] for k in COUNT_KEYS},
            gate_removed=funnel["gate_counts"],
        )

    def judgment_payload(self, cands):
        # rebuilt from the candidates handed in -- no instance state
        return pipeline.build_blind_payload(dedupe(cands), cands)

    def price(self, ctx, cands, verdicts=None):
        ...   # Verdict.bucket -> Edge.from_bucket via ctx.bucket_rates
```

Note what is **not** here: no `self._last_funnel`. An earlier draft stashed
the funnel on the instance so `judgment_payload()` could reach it, which
would have made the theory non-reentrant and unusable in the section 4.9
parallel model. The funnel travels on the `TheoryRun`; the theory stays
stateless. This is the concrete reason `TheoryRun` exists.

The internals of `screen.py`, `gate.py`, and `mention_bucket.py` are
untouched in Phase 3. The contract is proven against two real theories
before any decision logic moves, so a contract that turns out to fit badly
is discovered while the diff is still small.

**One exception, and it is load-bearing.** `run_mechanical_stages` today
computes the surviving candidates as a local (`kept`, `pipeline.py:124`) and
returns only its *length* — every other value in the returned dict is a
count, and the candidate objects are discarded:

```python
kept = [c for c in candidates
        if (c.get("event_ticker") or c.get("ticker")) in survivor_keys]
return {..., "survivor_markets": len(kept),
        "payload": build_blind_payload(survivors, kept)}
```

So `screen()` has nothing to delegate to. Two ways out:

1. **Adapter re-runs the chain** — `screen.screen()`, `dedupe_by_event()`,
   `gate.partition()` in the adapter. Rejected: the same sequence would then
   exist in two places and could drift, which is precisely the failure the
   contract exists to prevent.
2. **Add `"survivor_candidates": kept` to the returned dict.** Chosen. It
   adds a key, changes no computation, and leaves one code path.

This makes Phase 3 the only phase that edits a theory module, so it needs an
explicit golden-test rule: **adding a key to the funnel dict is permitted;
changing any existing key's value is not.** The Phase 0 golden for
`run_mechanical_stages` is asserted as a subset match on the pre-existing
keys rather than whole-dict equality, so a new key passes and a changed
count fails. Every other golden in section 7 stays whole-value equality.

`pipeline.run_mechanical_stages()`'s funnel-counts dict
(`board_markets`, `screened_markets`, `gate_counts`, `gated_out`, ...) is
reporting output, not candidate flow. It leaves `screen()` inside the
`ScreenResult` — the contract does not flatten it into the candidate list,
because CLAUDE.md requires the gate to *"always report what the gate
removed, by category"* and only this theory has a gate.

### 4.8 Making the tools support injection

Injection only works if the tools can actually be handed their dependencies.
Audited on 2026-08-24, the repository is **most of the way there already**,
with one real gap.

**Already injection-ready — no change needed:**

- **No mutable module state anywhere in `tools/`.** Every module-level name
  is a frozen constant (`FEE_RATE`, `PROBATION_N`, `STOPWORDS`, `_INSERT`,
  `RETRYABLE_STATUS`). Nothing caches, nothing memoizes, no singletons, no
  import-time I/O. This is the property that makes everything below cheap.
- **`conn` is always a parameter**, never a global — all 46 DB-touching
  functions take it explicitly.
- **`now` is injectable by documented convention** — `tools/README.md`
  already mandates `now: str | None = None` on anything that reads a clock,
  precisely so tests never assert against a wall clock.

The repo was written injection-friendly without naming the pattern. The
`TheoryContext` in section 4.3 is mostly formalizing what the tools already
permit.

**The gap: the network clients have no seam.** `kalshi.markets.list_open()`
calls the module-global `get_json` directly, so the only way to substitute a
fake is to reach into the module and reassign it —
`monkeypatch.setattr(markets, "get_json", fake_get)`, which is what all of
`tests/kalshi/test_markets.py` does today. That is patching, not injection:
it works in pytest and is unavailable to a `TheoryContext`, a backtest
harness, or a replay.

**Change:** give each fetching function an optional transport parameter
defaulting to the current behavior.

```python
def list_open(limit: int = 200, *, fetch: Fetch = get_json) -> list[Market]:
```

`Fetch` is a `Protocol` in `tools/domain.py` (`(url, params, timeout) ->
dict | list`) — the one place a `Protocol` earns its keep, because it names
a seam two client modules and every test share. The default keeps every
existing call site working unchanged, so this is additive and cannot
regress anything per section 3.1. Existing `monkeypatch` tests keep passing;
new tests pass a fake instead.

**What `TheoryContext` carries, given section 3.4 forbids gateway objects.**
Rather than build a repository layer, the context holds the raw connection
plus *narrowly bound callables* for the one thing theories legitimately read
from the DB:

```python
@dataclass(frozen=True, slots=True)
class TheoryContext:
    conn: sqlite3.Connection
    board: list[Market]
    now: datetime
    run_id: str = "live"
    run_mode: str = "live"
    judge_model: str | None = None
    bucket_rates: Callable[[str, int], dict] | None = None
```

`bucket_rates` is `score.bucket_rates` pre-bound to the connection, so
`price()` reads measured rates without importing `tools.score`. A
per-instance binding cannot be a dataclass default, so the context is
built by a small factory — `TheoryContext.build(conn, board, now, ...)` —
which is where the binding happens; constructing the dataclass directly
with a fake `bucket_rates` remains the test path. This is
functional injection: no new classes, no gateway layer, and `tools/score.py`
stays the pure module it is. A theory that needs something else still has
`ctx.conn` and section 3.2's escape hatch.

**Extend the convention to external sources.** Six backlog theories fetch
from outside Kalshi and Polymarket entirely: Coinbase candles
(`vol-crossing`), NWS/NOAA (`settled-but-trading`, `weather-model-gap`),
BLS/FRED (`econ-anchoring`), Wikipedia pageviews (`attention-model`), and
Polymarket trade flow (`whale-follow`, `insider-flow-radar`). None of them
gets a seam from the two client modules above.

No code is required — only that the convention generalize:

> **Any theory that fetches external data takes `fetch: Fetch = get_json`.**

One sentence in `tools/README.md`, and six theories become testable against
a canned payload with no network and no `monkeypatch`. This is the same
"injectable `now`" discipline the repo already applies to clocks, applied to
transports.

**Phase note.** The `fetch` seam lands in Phase 2 alongside the `Market`
return-type change, since both touch the same two client modules. It is the
only tools-layer *code* change this design requires; the external-source
convention is documentation.

### 4.9 Execution model: one subagent per judgment theory

The intended mental model: **a theory is a self-contained unit of work that
one subagent can be handed and can work through cleanly, start to finish.**
The parent session enumerates theories, dispatches, and composes results;
each agent owns one theory and needs to know nothing about the others.

The contract in section 4.4 is what makes this possible — a subagent given
a theory id can run `start()`, judge, `finish()` without reading prose,
and every agent returns the same `ScanResult` shape regardless of which
theory it drew.

Four refinements, three of which are constraints the parent must honour.

**1. Only judgment theories get a subagent.** A mechanical theory has no
model in its decision path *by definition* — that is what earns it
`edge_basis="model"` and a tier A backtest. Spawning an agent for it spends
tokens and puts an LLM next to a path that must stay model-free. The
discriminator is the declared `uses_llm_judgment` ClassVar:

```python
mechanical = [t for t in registry.running(conn) if not t.uses_llm_judgment]
judgment   = [t for t in registry.running(conn) if t.uses_llm_judgment]
```

The declaration is drift-checked against the DB flag by `check_drift`
(section 4.6), so a stale ClassVar is a failing test rather than a silent
misroute. (An earlier draft probed `t.judgment_payload(t.screen(ctx))`,
which ran every screen twice and would misread a judgment theory whose
screen happened to survive nothing as mechanical.) A judgment theory with
an empty board day still ends cleanly — `finish()` demands verdicts only
when a payload actually exists.

**The unit dispatched is a theory id, not a payload.** The subagent runs
`start()` itself; because the board comes from the session cache, its
screen sees identical input to anything the parent would have computed,
and the parent never screens a judgment theory at all. Mechanical theories
run inline, in-process, at zero model cost. This makes CLAUDE.md's stated
preference for mechanical theories show up as a *mechanical* fact — the
cheap ones are literally cheaper to run.

**2. The board is pulled once, by the parent, before any spawn.** CLAUDE.md
mandates one board per session shared by every theory; a complete board is
~100k markets, ~13s, ~200MB. Twenty-four agents each calling
`get_board(force=True)` would be a catastrophe. The parent makes the single
deliberate refresh; subagents call `get_board()` without `force` and hit the
snapshot cache. **Subagent instructions must state this explicitly**, since
a fresh agent has no way to know the pull already happened.

**3. Final cross-theory selection stays with the parent.** CLAUDE.md's
cascade puts final selection at "a handful → you, this session," and the
reason is structural rather than stylistic: ranking is
`edge_pts_net × credibility`, which compares theories against each other. A
per-theory agent sees exactly one theory and cannot perform that comparison.
Subagents produce candidates and buckets; the parent ranks and selects.

**4. Provenance records the subagent's model, not the parent's.** If the
judging happens inside a spawned agent, the model id written by
`finish()` must be that agent's. `TheoryContext` therefore carries an
optional `judge_model: str | None` (section 4.3), which the parent names
in its dispatch instructions and the subagent sets when it builds its own
context.
Recording the parent's model for a judgment it did not make would corrupt
exactly the reproducibility record CLAUDE.md's provenance rule exists to
protect.

**Concurrency is already supported — verified, not assumed.**
`tools/db.py:39` opens connections with `timeout=30.0` and enables
`PRAGMA journal_mode = WAL` (line 43); the function's own docstring says WAL
"lets a reader run concurrently with a writer" and the busy timeout "covers
the brief moments when two writers do collide." Parallel agents each writing
their own ledger rows is the case this was built for. Two notes:

- Each subagent opens **its own connection**. A `sqlite3.Connection` is not
  safe to share across processes, and `TheoryContext` is constructed per
  agent, not passed across the boundary.
- No agent writes another theory's rows, so the writes are disjoint and
  contention is limited to the brief commit window.

**What a subagent returns.** A subagent returns text, not a Python object.
So the deliverable is: ledger rows written via `finish()` (durable, the real
output) plus a compact JSON `ScanResult` summary in its final message. The
parent does not need to trust the summary — it can read the rows back with
`list_opportunities(run_id=...)`. The summary is for narration; the database
is the source of truth, exactly as the data conventions require.

**Backtest note.** Web search stays off in every backtest judgment subagent,
per CLAUDE.md. `TheoryContext.run_mode == "backtest"` is what the dispatch
instructions key on.

## 5. What this changes for a session

`find-edge` step 2 today: open each `THEORY.md`, read Stage 1 prose, write
the call, per theory.

**Parent session** — one board pull, then fan out:

```python
from tools import board as board_tool, db, registry
from tools.theory import TheoryContext

conn = db.connect()
board = board_tool.get_board(conn, force=True)     # the one deliberate pull
ctx = TheoryContext.build(conn=conn, board=board, now=utcnow_dt(),
                          run_id="live")

results: list[ScanResult] = []
for theory in registry.running(conn):
    if theory.uses_llm_judgment:
        dispatch(theory.id)                        # subagent; section 4.9
    else:
        results.append(theory.start(ctx).finish()) # mechanical, inline, free
```

**Inside a subagent**, handed nothing but a theory id:

```python
theory = registry.discover()["insider_judgment"]
ctx = TheoryContext.build(conn=db.connect(),
                          board=board_tool.get_board(conn),
                          now=..., run_id="live",
                          judge_model="claude-opus-5")
run = theory.start(ctx)                # cache hit: no second board pull
verdicts = judge(run.payload, theory.prompts["analysis"])
                                       # {Candidate.key: Verdict} — labels
                                       # and rationale, never a number
result = run.apply(verdicts).finish()  # price + provenance + ledger
```

Then the parent ranks across every `ScanResult` and selects — the one step
that cannot be delegated, because credibility weighting compares theories to
each other.

Stage-1 prose reads drop to zero. **Stage-2 prose reads do not** — a
judgment prompt is genuine instruction, and it already lives in
`theories/<slug>/prompts/`; the contract only makes it directly addressable
via `theory.prompts` instead of findable via `THEORY.md`. What changes is
*who* reads it: a subagent scoped to one theory, not the parent session
carrying all twenty-four.

## 6. Migration plan

Six phases, each independently green, each its own commit.

| # | Phase | Touches | Behavior change |
|---|---|---|---|
| 0 | Characterization harness | `tests/characterization/` | none |
| 1 | `tools/domain.py` (+ `Leg`, `Verdict`, `ScreenResult`, `ScanResult`, `Fetch`) + shim; `theory_facts` table; `construction` provenance stage | new file, `schema.sql`, `provenance.py`, `tests/` | none (additive) |
| 2 | `normalize()` returns `Market`; `fetch` seam | both clients, `board.py`, `snapshot.py` | none (additive default) |
| 3 | `Theory` / `TheoryRun` / `TheoryContext` + adapters + registry; experiment-lane exclusion | new files, theory `__init__.py`, `pipeline.py` (one added key, section 4.7), `ledger.py` + `score.py` (`exp/` exclusion, section 3.3a) | none for existing rows (no run_id starts with `exp/`) |
| 4 | Docs and skill rewrite | `tools/README.md`, `CLAUDE.md`, `find-edge`, `propose-theory` | none |
| 5 | Port theory internals; delete shim | `theories/**` | none |

**Phase 0 gates everything.** No production code changes until the golden
files exist and pass.

**Phase 4 before Phase 5 is deliberate.** The conventions must be written
down before the largest code change lands, or a session interrupted between
them reads `tools/README.md`'s current "no base class" text and reverts the
work.

**Every phase is independently revertible**, which is the operational form
of section 3.1: if any phase cannot keep the suite green without weakening a
test, it is reverted and re-scoped rather than pushed through.

## 7. Characterization testing

The refactor's correctness claim is *byte-identical output*, so the tests
must be able to prove that.

**Fixture** — `tests/fixtures/board_sample.json`, built once by a committed
script, deterministic and regenerable:

1. Pull a full board via `board.get_board(conn, force=True)`.
2. Take **every** market that survives `screen.screen()` — guarantees the
   golden covers every candidate the current code produces.
3. Add a systematic sample of 2,000 non-survivors (reusing
   `backtest.systematic_sample`, which is already deterministic) — covers
   the reject paths and every `gate.classify` category.
4. Dedupe, sort by ticker, write with `sort_keys=True`.

**Golden files** — current output of, at minimum:

- `screen.screen(fixture)` — full candidate list
- `gate.partition(...)` — survivors **and** the per-category counts dict
- `pipeline.dedupe_by_event(...)`, `build_blind_payload(...)`
- `pipeline.run_mechanical_stages(...)` — **subset match on pre-existing
  keys only**, per section 4.7; every other golden below is whole-value
  equality
- `mention_bucket.find_candidates(...)`, `rank(..., frozen_rates)`
- `kalshi.markets.normalize(raw)` for every fixture row, **`raw` included**

Every golden is generated with a frozen `now` and frozen bucket rates, so
nothing depends on wall clock or DB state.

**Goldens are recorded and compared through a canonical projection.**
Phase 2 changes `normalize()`'s return *type* from dict to `Market`, so
literal equality across that phase is impossible by definition — the
change the phase exists to make would fail it. Each golden is therefore
stored as canonical JSON, and the live value is projected to the same JSON
before comparison: a dict projects as itself, a `Market` as
`asdict(market)` with `raw` included. The projection lives in the test
harness, not in the code under test, and field-level equality through it
is the pass condition at every phase.

**The pass condition is equality against the golden, unchanged, at every
phase.** A diff is not a signal to update the golden; it is a signal that
the phase changed behavior and must either be fixed or escalated to a
version bump (section 8.2).

**The existing suite is itself the primary non-regression test** (section
3.1). It passes at every phase with nothing deleted, skipped, or weakened.
The `monkeypatch`-based network tests in `tests/kalshi/test_markets.py` keep
passing unchanged, because the section 4.8 `fetch` seam is an additive
parameter with the current default.

**Additional tests introduced by this work:**

- `tests/test_domain.py` — invariants, delegating properties, frozen-ness,
  `raw` passthrough identity.
- `tests/test_theory.py` — ABC cannot be instantiated; a subclass missing
  `screen`/`price` fails; `finish()` is not overridden by any subclass;
  `finish()` raises when `needs_judgment` and no verdicts were applied;
  `TheoryRun.apply` rejects a verdict key matching no candidate's `.key`.
- `tests/test_theory_run.py` — **statelessness**: the same `Theory`
  instance started twice yields two independent `TheoryRun`s whose
  `ScreenResult`s and verdicts do not alias; two theories interleaved in
  one loop do not corrupt each other. This is the regression test for the
  `_last_funnel` bug section 4.4 describes.
- `tests/test_context.py` — a theory runs against a fake `TheoryContext`
  with a ten-market board, no live connection and no network; `fetch`
  injection substitutes a canned payload without `monkeypatch`.
- `tests/test_registry.py` — discovery finds both theories and skips a
  fixture study folder; `check_drift` detects each of its four mismatch
  kinds.
- `tests/test_conventions.py` — every folder carrying a `THEORY.md`
  exposes `THEORY` subclassing `Theory`, and a folder carrying `STUDY.md`
  is exempt (section 4.5c); `Verdict` declares no numeric field, so the
  no-introspected-probabilities rule stays enforced by the type; the
  section 4.2 shim is imported only from allowlisted modules.
- `tests/test_stub_theory.py` — the section 3.2 litmus test, mechanised: a
  stub theory implementing only `screen()` and `price()` runs end to end.
  A second stub that ignores `ctx` and reaches for its own data source also
  runs, proving the contract is a floor and not a cage.
- `tests/test_parallel_writes.py` — N concurrent connections each recording
  opportunities for a different theory all commit, verifying the section 4.9
  claim about WAL and the busy timeout rather than assuming it.
- `tests/test_theory_facts.py` — a fact round-trips; adding one does **not**
  change the theory's version (section 4.5a); a fact established by a model
  carries a `construction`-stage provenance row.
- `tests/test_backlog_fit.py` — the section 3.2 litmus test widened: a stub
  per *shape* found in the backlog, each running end to end. A basket
  producer (`structural-arb`-like), an external-source theory taking
  `fetch` (`vol-crossing`-like), a pair-store theory reading
  `theory_facts` with `uses_llm_judgment=False` (`metaculus-gap`-like), and
  a non-board theory that ignores `ctx.board` entirely
  (`whale-follow`-like). These are the four shapes the backlog review found
  the first draft could not express; a test is how they stay expressible.
- `tests/test_experiment_lane.py` — a subclass variant with one overridden
  method records real rows under an `exp/` run_id with **no version bump
  and no registration**; pooled `compute_score` and `bucket_rates` are
  provably blind to `exp/` rows, while an explicit `run_id=` sees exactly
  them (section 3.3a).

## 8. Risks

### 8.1 `raw` payload fidelity — highest severity

`tools/board.py`'s docstring is explicit that a cached board and a fetched
board must be identical *including* `market["raw"]`, because a thinner `raw`
would make a theory work on a forced pull and silently return `None` on a
cached one.

`Market.raw` is therefore `compare=False, repr=False` and passed through
untouched. `_rebuild()` (cache path) and `list_open()` (fetch path) must
produce equal `Market` objects **and** equal `raw` dicts. A dedicated test
asserts this on the fixture, both directions, in Phase 2.

### 8.2 Accidental version bump — highest consequence

CLAUDE.md: any change to a theory's decision procedure bumps its version,
and a bump orphans the accrued track record. `insider_judgment` is at
version 3 with live history; `mention_family` carries measured rates keyed
to `backtest-2026-08-24-stage1-90d`.

Mitigation is section 7's golden files. **Escalation rule:** if a golden
diff cannot be eliminated, the phase stops and the discrepancy is reported
to the user as a version-bump decision. It is never resolved by regenerating
the golden.

### 8.3 Blind-payload leak

`pipeline.build_blind_payload` whitelists fields; `assert_blind` scans the
serialized blob for `BANNED_KEYS` including `entry_price` and `fav_side`.

A `Candidate` carries `entry_price` as an attribute and composes a `Market`
holding every price field plus `raw`. Naively serializing a `Candidate` into
a payload would leak price and make every `judged_blind=True` record false.

Mitigations: `build_blind_payload` keeps building plain dicts from its
explicit whitelist and never serializes a `Candidate`; `assert_blind` is
unchanged and still runs; a Phase 3 test asserts that
`json.dumps(asdict(candidate))` **does** trip `assert_blind`, proving the
guard still catches the mistake this refactor makes easier to commit.

### 8.4 Scope creep into a rewrite

The `conn`-threading and 24-argument-call problems are visible throughout
and tempting to fix in passing. Section 3 excludes them. Any phase whose
diff extends beyond its table row in section 6 stops and re-scopes.

### 8.5 `slots=True` and the shim

`slots=True` forbids attribute injection, which is the point — it prevents
the `{**c, "new_key": ...}` pattern from surviving as `object.__setattr__`.
It also means the section 4.2 `__getitem__`/`keys()` shim cannot fall back
to a mutable `__dict__`; it must expose declared fields only. Phase 1
tests cover this, including that `dict(market)` round-trips through the
shim's `keys()`.

### 8.6 The contract becomes a cage

The failure mode section 3.2 exists to prevent, restated as a risk because
it will not announce itself. A contract fitted to the two theories that
exist today can silently exclude theories that do not yet — and the project's
value comes from instruments that see what the others cannot.

The tell is a backlog spec that "doesn't fit the harness." That is evidence
about the harness, not the theory. **Mitigation:** the section 3.2 litmus
test, the two stub-theory tests in section 7, and a standing rule that
widening `Theory` to admit a legitimate theory is always preferred to
turning that theory away.

**The subtler form: the researcher cages itself.** Nothing in the code will
stop a future session from reading this document as a procedure and
concluding that investigation must happen through `Theory`, that a question
needs a `TheoryContext`, or that a hunch is not worth pursuing because it is
not yet a theory. That would cost more than any technical defect here — it
would trade a researcher for a task-runner, which is the one thing CLAUDE.md
opens by warning against.

There is no test for this. The mitigations are placement and repetition:
section 3.3 is stated as a constraint rather than a footnote, the header
says it above the design summary, and the `CLAUDE.md` conventions list leads
with it so it cannot be read without that framing. If a future session finds
this architecture is getting in the way of real research, **the architecture
is what is wrong**, and revising it is in scope for that session.

### 8.7 Parallel subagents amplify a bad contract

Section 4.9's model multiplies whatever the contract gets wrong by the
number of theories. A stateful `Theory` corrupts silently under interleaving
(section 4.4); a subagent that pulls its own board costs 13s and ~200MB
each; a provenance row stamped with the parent's model instead of the
judging agent's is wrong in a way no test catches after the fact.

**Mitigation:** statelessness is enforced by test, not convention
(`tests/test_theory_run.py`); the board rule is stated in the dispatch
instructions themselves rather than left to inference; `judge_model` is a
`TheoryContext` field so it travels with the run. Phase 3 also runs the two
existing theories **sequentially in-process first**, and only then in
parallel — parallelism is the last thing switched on, not the first.

## 9. Success criteria

**Non-regression (section 3.1) — the gating criteria:**

1. The existing test suite passes at every phase with no test deleted,
   skipped, or weakened.
2. Every characterization golden passes unchanged at every phase.
3. Every `tools/cli.py` subcommand emits identical JSON to before.
4. Both theories run end to end with **no version bump** and no lost
   capability — `rank`/`rank_preview` still separate, `confidence_suffix`
   still honoured, the full funnel including `gate_counts` still reported.

**Structure — the value delivered:**

5. `find-edge` runs both theories without opening either `THEORY.md`.
6. A subagent handed only a theory id can run that theory start to finish
   and return a `ScanResult` (section 4.9).
7. Mechanical theories run inline with no model spawned; the declared
   `uses_llm_judgment` ClassVar — drift-checked against the DB flag — is
   the only dispatch discriminator needed.
8. `registry.check_drift(conn)` returns empty; a conventions test enforces
   it.
9. `tools/README.md` and `CLAUDE.md` no longer contradict the code.

**Restraint — evidence the structure did not overreach:**

10. No new class in `tools/sizing.py`, `buckets.py`, `rank.py`, `db.py`, or
    `cli.py`. (`http.py` gains the `Fetch` Protocol only — no class.)
11. Adding a hypothetical theory #3 requires writing `screen()` and
    `price()` and nothing else — demonstrated by a test-only stub theory.
12. A stub theory that ignores `TheoryContext` entirely and reaches for its
    own data source still runs, proving the contract is a floor rather than
    a cage (section 3.2).
13. `Verdict` carries a bucket label and an optional rationale, and
    declares no numeric field — an out-of-process judge has no channel
    through which to hand back a probability or an edge. CLAUDE.md's
    "never state a probability you introspected" holds as a property of
    the type system, enforced by a conventions test.

**Researcher freedom — evidence the platform still serves the LLM
(section 3.3):**

14. Every tool remains callable standalone. `screen.screen(board)`,
    `markets.quotes(...)`, `score.bucket_rates(...)` and
    `ledger.list_opportunities(...)` all work as plain functions, with no
    `Theory`, `TheoryRun`, or `TheoryContext` constructed.
15. Answering a "just asking" question — "how is insider_judgment holding
    up?" — requires only `python -m tools.cli`, with no knowledge that this
    spec exists.
16. An ad-hoc exploration that never becomes a theory is possible and
    unpenalised: no code path requires an investigation to be expressed as a
    `Theory` subclass.
17. The ledger boundary still holds under all of the above — a recorded
    opportunity carries provenance, an honest `edge_basis`, and a Kalshi
    ticker no matter which path produced it.
18. **Experimenting is free by construction** (section 3.3a): a subclass
    variant runs under an `exp/` run_id with no version bump and no
    registration, its rows record and settle for real, and pooled scores
    and bucket rates are provably unchanged by them. The cheapest path
    for a new idea is trying it.
19. The contract is glass-box: `run.candidates`, `run.payload`, and
    `run.verdicts` are plain attributes, and every stage is individually
    callable — the researcher can stop, inspect, and steer between any
    two stages (section 3.3a).

**Backlog fit — the check that drove these amendments:**

20. All four shapes the backlog review surfaced run end to end as stubs:
    basket producer, external-source fetcher, pair-store theory, and
    non-board theory (`tests/test_backlog_fit.py`).
21. A theory can establish and reuse durable facts without bumping its
    version, and a model-established fact carries `construction` provenance.
22. Nothing in the design requires `series-bias-mining`,
    `new-market-anchor`'s stage 0, or `maker-mode-execution` to become a
    `Theory` — section 4.5c says plainly that they are not one.

## 10. Open questions

1. **`no`-side candidates.** `Leg.side` is `"yes"|"no"` and `Leg.price` is
   that side's ask, while `Market.mid` is yes-denominated. Should `Leg` (or
   single-leg `Candidate`) expose a side-aware `implied_prob`? Deferred to
   Phase 5; neither current theory needs it.
2. **Polymarket `Market`.** Section 4.1 unifies both platforms, but no
   theory currently screens Polymarket. Phase 2 maps `polymarket.normalize`
   onto `Market` for consistency; if the fit is poor, a separate
   `PolymarketMarket` type is acceptable and better than a lossy union.
3. **Backtest path.** `backtest.py` reconstructs point-in-time markets from
   candlesticks and does not call `normalize()`. Phase 2 must confirm it
   produces `Market` objects too, or backtests and live scans diverge in
   type. Assessed at Phase 0 and reported before Phase 2 begins.
4. **`maker-mode-execution` needs its own spec.** Section 4.5c settles that
   it is not a `Theory` and that the taker price stays the recorded
   baseline. What it does *not* settle: whether a maker variant is a second
   ledger row, a field on the existing row, or report-only output; and how
   fill rate gets measured when the system never sees the order book after
   the fact. Deliberately out of scope here — it changes what every
   theory's `entry_price` means, which is too broad to decide inside a
   structural refactor.
5. **Continuous detectors.** `insider-flow-radar` is described as "code,
   continuous-ish" — a detector watching Polymarket flow rather than a
   batch screen over a board. `screen(ctx)` fits it awkwardly: it would run
   per session and re-derive alerts each time. Workable for v1, but if more
   streaming theories appear, a scheduled-detector shape may be needed
   alongside `Theory`. Not designed now; recorded so the second instance is
   recognised as a pattern rather than handled ad hoc.

## 11. Documentation changes

**`tools/README.md`** — the opening section is rewritten, not deleted. It
keeps "one responsibility per file", "read one tool end to end", and the
promotion path, and adds: leaf tools stay functions; the theory layer has a
base class because the file's own promotion criterion — more than one real
caller — was met; the boundary between the two is stated.

**`CLAUDE.md`** — a short conventions section stating, in order of
importance:

- **The researcher is not bound by any of this.** Every tool stays directly
  callable, ad-hoc exploration is first-class, and "just asking" needs none
  of it. The contract is optional for running and mandatory only for
  recording (section 3.3). This point goes **first**, because a conventions
  list read without it reads as a workflow to obey.
- A theory **inherits what to do** (`start`, `finish`) and **is handed what
  it may touch** (`TheoryContext`). Never a toolbox base class — section 4.5
  gives the repo-specific reason.
- `Theory` is stateless; per-run state lives in `TheoryRun`.
- Domain values are frozen dataclasses from `tools/domain.py`; bare dicts
  are confined to the API and JSON boundaries.
- `finish()` is never overridden — it is what makes the provenance and
  ledger contract unskippable.
- **A judge returns `Verdict`s — labels and rationale, never numbers.**
  The type declares no numeric field; probabilities come from measured
  bucket rates or a mechanical model, downstream in `price()`
  (section 4.4). An LLM cannot predict an edge; it can classify.
- The contract is a **floor, not a ceiling**: two required methods, and a
  theory may add anything else it needs (section 3.2).
- **Experimenting on a theory is built in.** Subclass it, override the one
  thing under test, run with `run_id="exp/<slug>"`. No version bump, no
  registration. Experiment rows record and settle for real, but pooled
  scores and bucket rates exclude `exp/` runs — trying ideas costs the
  track record nothing. Score one with
  `compute_score(..., run_id="exp/<slug>")`; promote a winner via a
  version bump or a proposed sibling theory, citing the experiment as the
  evidence (section 3.3a).
- **You are the operator, not a step in the pipeline.** A `TheoryRun` is
  glass-box — `run.candidates`, `run.payload`, `run.verdicts` are plain
  attributes, and `screen()`, `judgment_payload()`, `price()` are callable
  individually. The contract composes conveniences; the only wall is the
  ledger (section 3.3a).
- **Facts are data, not procedure** — adding a confirmed pair does not bump
  a version; changing how facts are derived does (section 4.5a).
- **`Theory` is for things that produce bets.** A study produces theories;
  an execution policy decorates candidates. Neither is a `Theory`
  (section 4.5c).
- Any theory fetching external data takes `fetch: Fetch = get_json`
  (section 4.8).

**`.claude/skills/find-edge/SKILL.md`** — step 2 replaced with the section 5
loop. The prose at line 74, "check whether this theory has a stage 2",
becomes a check of the theory's declared `uses_llm_judgment`. A new
subsection covers the section 4.9 dispatch model, and must state
explicitly that the parent pulls the board once before spawning, that
subagents call `get_board()` without `force`, and that a judge returns
`Verdict`s (bucket labels), never probabilities.

**`.claude/skills/propose-theory/SKILL.md`** — scaffold a `Theory` subclass
rather than a free-function module, and say plainly that only `screen()` and
`price()` are required — and that an idea which is a *tweak* of an existing
theory should usually start life as an `exp/` variant run on a subclass
(section 3.3a) rather than a new theory: it produces evidence with zero
ceremony, and the evidence travels with the promotion.

**`.claude/skills/go/SKILL.md` and `backtest-theory/SKILL.md`** — audited
for stale per-theory invocation prose and updated where they describe how a
theory is run. Listed here so the doc pass is not silently scoped to
`find-edge` alone.
