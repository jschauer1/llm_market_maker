# Theory-Layer OOP — Contracts and Value Types

Date: 2026-08-24
Status: design approved, implementation not started
Scope: `tools/domain.py` (new), `tools/theory.py` (new),
`tools/registry.py` (new), `theories/**`, both platform clients,
`tools/README.md`, `CLAUDE.md`, `.claude/skills/**`
Behavior change: **none** — see section 3.1, non-regression is a hard
constraint · Theory version bumps: none intended

**In one line:** every theory becomes an object a subagent can be handed and
run start-to-finish, returning one uniform result — with two required
methods, everything else optional, and nothing that exists today lost.

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

### 3.3 Out of scope

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
class Candidate:
    market: Market
    fav_side: str                 # "yes" | "no"
    entry_price: float            # the ask actually payable, never the mid
    days_to_close: float

    @property
    def ticker(self) -> str: return self.market.ticker
    @property
    def title(self) -> str | None: return self.market.title
    @property
    def event_key(self) -> str:
        return self.market.event_ticker or self.market.ticker
```

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
- `ScoredCandidate.disposition` in `("screened", "endorsed", "rejected")`.

The `ledger.py` validators are **retained**, not moved. The ledger is still
callable directly and must stay defensive; the dataclass check is an
earlier, additional line of defence.

### 4.2 Transitional mapping shim

`Market` and `Candidate` implement `__getitem__` and `.get()` for one
migration window, so existing `market["ticker"]` / `m.get("spread")` call
sites keep working while call sites convert incrementally.

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
    def screen(self, ctx: TheoryContext) -> list[Candidate]:
        """Stage 1. Mechanical, no model in the decision path."""

    @abstractmethod
    def price(self, ctx: TheoryContext,
              cands: list[Candidate]) -> list[ScoredCandidate]:
        """Attach an Edge. Must set edge.basis honestly."""

    # ---- optional stage 2 ----

    def judgment_payload(self, cands: list[Candidate]) -> list[dict] | None:
        """Stage 2 input, or None when the theory has no stage 2."""
        return None

    def apply_verdicts(self, cands: list[Candidate],
                       verdicts: dict[str, str]) -> list[Candidate]:
        """Attach bucket labels returned by an out-of-process judge."""
        raise NotImplementedError

    def funnel(self) -> dict[str, int]:
        """Theory-specific counts merged into ScanResult.funnel."""
        return {}

    def gate_removed(self) -> dict[str, int]:
        """Per-category gate counts. {} when the theory has no gate."""
        return {}

    # ---- the workflow, inherited and not overridden ----

    def start(self, ctx: TheoryContext) -> "TheoryRun":
        return TheoryRun(self, ctx, self.screen(ctx))
```

```python
class TheoryRun:
    """One execution of one theory. Holds all per-run state."""

    def __init__(self, theory, ctx, candidates): ...

    @property
    def needs_judgment(self) -> bool:
        return self.payload is not None

    @property
    def payload(self) -> list[dict] | None:
        """Stage 2 input; None for a mechanical theory."""

    def apply(self, verdicts: dict[str, str]) -> "TheoryRun":
        """Feed back out-of-process verdicts. Chainable."""

    def finish(self, *, dry_run: bool = False) -> ScanResult:
        """price -> provenance -> ledger -> ScanResult. Never overridden."""
```

Design notes:

- **Stage 2 is out-of-process by necessity.** The judging model is the
  session or a subagent, not a Python call. The contract therefore exposes
  a payload and accepts verdicts back, rather than pretending `judge()` can
  be executed inside a loop. This is why the pair `judgment_payload` /
  `apply_verdicts` exists instead of a single `judge()`.
- **`TheoryRun` exists to carry the state across that gap.** An earlier
  draft of this spec stashed the funnel on the theory instance
  (`self._last_funnel`). That is a latent bug: two theories run in one loop,
  or one theory run twice, would overwrite each other's state. `Theory`
  stays stateless; `TheoryRun` is the per-run object.
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

**Separation of authority, stated explicitly:** the database is the source
of truth for a theory's *status and version*; the Python class is the source
of truth for its *procedure*. `running()` joins them.

`check_drift` fails loudly on: a DB row with no matching class, a class with
no DB row, and a `Theory.version` disagreeing with the row's version. Silent
drift here would let a session run v3 code while recording v2 rows — exactly
the silent-merge failure CLAUDE.md's versioning rule exists to prevent.

### 4.7 Existing theories become adapters first

Phase 3 wraps, it does not rewrite:

```python
class InsiderJudgmentTheory(Theory):
    id = "insider_judgment"
    version = 3
    uses_llm_judgment = True
    prompts = {"analysis":
               "theories/insider_bias/insider_judgment/prompts/analysis.md"}

    def screen(self, ctx: TheoryContext) -> list[Candidate]:
        funnel = pipeline.run_mechanical_stages(ctx.board, ctx.now)
        return [to_candidate(m, funnel) for m in funnel["survivor_candidates"]]

    def judgment_payload(self, cands):
        # rebuilt from the candidates handed in -- no instance state
        return pipeline.build_blind_payload(dedupe(cands), cands)

    def gate_removed(self) -> dict[str, int]:
        ...   # from the funnel carried on the TheoryRun, not on self
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
reporting output, not candidate flow. It is preserved as a
theory-specific method — the contract does not absorb it, because
CLAUDE.md requires the gate to *"always report what the gate removed, by
category"* and only this theory has a gate.

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

**What `TheoryContext` carries, given section 3.3 forbids gateway objects.**
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
    bucket_rates: Callable[[str, int], dict] = ...   # bound to conn
```

`bucket_rates` is `score.bucket_rates` pre-bound to the connection, so
`price()` reads measured rates without importing `tools.score`. This is
functional injection: no new classes, no gateway layer, and `tools/score.py`
stays the pure module it is. A theory that needs something else still has
`ctx.conn` and section 3.2's escape hatch.

**Phase note.** The `fetch` seam lands in Phase 2 alongside the `Market`
return-type change, since both touch the same two client modules. It is the
only tools-layer change this design requires.

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
discriminator is already in the contract:

```python
mechanical = [t for t in registry.running(conn)
              if t.judgment_payload(t.screen(ctx)) is None]
judgment   = [t for t in registry.running(conn) if t not in mechanical]
```

Mechanical theories run inline, in-process, at zero model cost. This makes
CLAUDE.md's stated preference for mechanical theories show up as a
*mechanical* fact — the cheap ones are literally cheaper to run.

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
optional `judge_model: str | None`, which the parent sets when it dispatches.
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
ctx = TheoryContext(conn=conn, board=board, now=utcnow_dt(), run_id="live")

results: list[ScanResult] = []
for theory in registry.running(conn):
    run = theory.start(ctx)
    if run.needs_judgment:
        dispatch(theory, run.payload)              # subagent; section 4.9
    else:
        results.append(run.finish())               # mechanical, inline, free
```

**Inside a subagent**, handed nothing but a theory id:

```python
theory = registry.discover()["insider_judgment"]
ctx = TheoryContext(conn=db.connect(), board=board_tool.get_board(conn),
                    now=..., run_id="live", judge_model="claude-opus-5")
run = theory.start(ctx)                # cache hit: no second board pull
verdicts = judge(run.payload, theory.prompts["analysis"])
result = run.apply(verdicts).finish()  # provenance + ledger, inherited
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
| # | Phase | Touches | Behavior change |
|---|---|---|---|
| 0 | Characterization harness | `tests/characterization/` | none |
| 1 | `tools/domain.py` (+ `ScanResult`, `Fetch`) + shim | new file, `tests/` | none |
| 2 | `normalize()` returns `Market`; `fetch` seam | both clients, `board.py`, `snapshot.py` | none (additive default) |
| 3 | `Theory` / `TheoryRun` / `TheoryContext` + adapters + registry | new files, theory `__init__.py`, `pipeline.py` (one added key, section 4.7) | none |
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
  `finish()` raises when `needs_judgment` and no verdicts were applied.
- `tests/test_theory_run.py` — **statelessness**: the same `Theory`
  instance started twice yields two independent `TheoryRun`s whose funnels
  do not alias; two theories interleaved in one loop do not corrupt each
  other. This is the regression test for the `_last_funnel` bug section 4.4
  describes.
- `tests/test_context.py` — a theory runs against a fake `TheoryContext`
  with a ten-market board, no live connection and no network; `fetch`
  injection substitutes a canned payload without `monkeypatch`.
- `tests/test_registry.py` — discovery finds both theories;
  `check_drift` detects each of its three mismatch kinds.
- `tests/test_conventions.py` — every theory package exposes `THEORY`
  subclassing `Theory`; the section 4.2 shim is imported only from
  allowlisted modules.
- `tests/test_stub_theory.py` — the section 3.2 litmus test, mechanised: a
  stub theory implementing only `screen()` and `price()` runs end to end.
  A second stub that ignores `ctx` and reaches for its own data source also
  runs, proving the contract is a floor and not a cage.
- `tests/test_parallel_writes.py` — N concurrent connections each recording
  opportunities for a different theory all commit, verifying the section 4.9
  claim about WAL and the busy timeout rather than assuming it.

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
It also means the section 4.2 `__getitem__` shim cannot fall back to a
mutable `__dict__`; it must read declared fields only. Phase 1 tests cover
this.

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
7. Mechanical theories run inline with no model spawned; `judgment_payload()
   is None` is the only discriminator needed.
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

## 10. Open questions

1. **`no`-side candidates.** `Candidate.fav_side` is `"yes"|"no"` and
   `entry_price` is that side's ask. `Market.mid` is yes-denominated. Should
   `Candidate` expose a side-aware `implied_prob`? Deferred to Phase 5;
   neither current theory needs it.
2. **Polymarket `Market`.** Section 4.1 unifies both platforms, but no
   theory currently screens Polymarket. Phase 2 maps `polymarket.normalize`
   onto `Market` for consistency; if the fit is poor, a separate
   `PolymarketMarket` type is acceptable and better than a lossy union.
3. **Backtest path.** `backtest.py` reconstructs point-in-time markets from
   candlesticks and does not call `normalize()`. Phase 2 must confirm it
   produces `Market` objects too, or backtests and live scans diverge in
   type. Assessed at Phase 0 and reported before Phase 2 begins.

## 11. Documentation changes

**`tools/README.md`** — the opening section is rewritten, not deleted. It
keeps "one responsibility per file", "read one tool end to end", and the
promotion path, and adds: leaf tools stay functions; the theory layer has a
base class because the file's own promotion criterion — more than one real
caller — was met; the boundary between the two is stated.

**`CLAUDE.md`** — a short conventions section stating, in order of
importance:

- A theory **inherits what to do** (`start`, `finish`) and **is handed what
  it may touch** (`TheoryContext`). Never a toolbox base class — section 4.5
  gives the repo-specific reason.
- `Theory` is stateless; per-run state lives in `TheoryRun`.
- Domain values are frozen dataclasses from `tools/domain.py`; bare dicts
  are confined to the API and JSON boundaries.
- `finish()` is never overridden — it is what makes the provenance and
  ledger contract unskippable.
- The contract is a **floor, not a ceiling**: two required methods, and a
  theory may add anything else it needs (section 3.2).

**`.claude/skills/find-edge/SKILL.md`** — step 2 replaced with the section 5
loop. The prose at line 74, "check whether this theory has a stage 2",
becomes `judgment_payload() is None`. A new subsection covers the section
4.9 dispatch model, and must state explicitly that the parent pulls the
board once before spawning and that subagents call `get_board()` without
`force`.

**`.claude/skills/propose-theory/SKILL.md`** — scaffold a `Theory` subclass
rather than a free-function module, and say plainly that only `screen()` and
`price()` are required.

**`.claude/skills/go/SKILL.md` and `backtest-theory/SKILL.md`** — audited
for stale per-theory invocation prose and updated where they describe how a
theory is run. Listed here so the doc pass is not silently scoped to
`find-edge` alone.
