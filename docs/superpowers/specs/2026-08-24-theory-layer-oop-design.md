# Theory-Layer OOP — Contracts and Value Types

Date: 2026-08-24
Status: design approved, implementation not started
Scope: `tools/domain.py` (new), `tools/theory.py` (new),
`tools/registry.py` (new), `theories/**`, `tools/README.md`, `CLAUDE.md`,
`.claude/skills/find-edge/SKILL.md`
Behavior change: none intended · Theory version bumps: none intended

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

## 3. Non-goals

Explicitly **out of scope**. These stay as plain functions:

- `tools/sizing.py`, `tools/buckets.py`, `tools/rank.py` — pure functions
  over numbers. A `KellyCalculator` class is a file to open in exchange for
  what a signature already says.
- `tools/http.py`, `tools/db.py` — thin I/O boundaries.
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

`OpportunityRecord` — a dataclass mirroring `record_opportunity`'s 24
arguments — is assembled inside `Theory.record()` and is not part of any
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

### 4.3 The theory contract — `tools/theory.py`

```python
class Theory(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[int]
    uses_llm_judgment: ClassVar[bool] = False
    prompts: ClassVar[dict[str, str]] = {}   # stage -> path in theory folder

    @abstractmethod
    def screen(self, board: list[Market],
               now: datetime | None = None) -> list[Candidate]:
        """Stage 1. Mechanical, no model in the path."""

    def judgment_payload(self, cands: list[Candidate]) -> list[dict] | None:
        """Stage 2 input, or None when the theory has no stage 2.

        Returning None is the machine-readable answer to the question
        find-edge/SKILL.md:74 currently poses in prose ("First check whether
        this theory has a stage 2 at all").
        """
        return None

    def apply_verdicts(self, cands: list[Candidate],
                       verdicts: dict[str, str]) -> list[Candidate]:
        """Attach bucket labels returned by an out-of-process judge."""
        raise NotImplementedError

    @abstractmethod
    def price(self, cands: list[Candidate],
              conn: sqlite3.Connection) -> list[ScoredCandidate]:
        """Attach an Edge. Must set edge.basis honestly."""

    def record(self, conn, scored: list[ScoredCandidate], *,
               run_id: str, run_mode: str = "live") -> list[int]:
        """Shared and effectively final. Do not override."""
```

Design notes:

- **Stage 2 is out-of-process by necessity.** The judging model is the
  session or a subagent, not a Python call. The contract therefore exposes
  a payload and accepts verdicts back, rather than pretending `judge()` can
  be executed. This is why the pair `judgment_payload` / `apply_verdicts`
  exists instead of a single method.
- **`record()` is concrete and shared.** It performs the provenance write
  (when `uses_llm_judgment`) and the `record_opportunity` call for every
  theory. This is where the section 1.3 risk is eliminated. A test asserts
  no subclass overrides it.
- **`prompts` is a ClassVar mapping stage to path**, so `record()` can
  satisfy `provenance.require_provenance` without the session locating
  prompt files via `THEORY.md`.
- **Class-level `id`/`version`** mirror the DB registry row and are checked
  against it at discovery (section 4.4).

### 4.4 Discovery — `tools/registry.py`

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

### 4.5 Existing theories become adapters first

Phase 3 wraps, it does not rewrite:

```python
class InsiderJudgmentTheory(Theory):
    id = "insider_judgment"
    version = 3
    uses_llm_judgment = True
    prompts = {"analysis":
               "theories/insider_bias/insider_judgment/prompts/analysis.md"}

    def screen(self, board, now=None):
        funnel = pipeline.run_mechanical_stages(board, now)
        self._last_funnel = funnel                     # for report_funnel()
        return [to_candidate(m) for m in funnel["survivor_candidates"]]

    def judgment_payload(self, cands):
        return self._last_funnel["payload"]
```

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

## 5. What this changes for a session

`find-edge` step 2 today: open each `THEORY.md`, read Stage 1 prose, write
the call. After:

```python
from tools import board as board_tool, db, registry
conn = db.connect()
board = board_tool.get_board(conn)

for theory in registry.running(conn):
    cands = theory.screen(board)
    payload = theory.judgment_payload(cands)
    if payload is None:                       # mechanical theory
        theory.record(conn, theory.price(cands, conn), run_id="live")
    else:
        ...                                   # dispatch subagents, then
                                              # apply_verdicts, price, record
```

Stage-1 prose reads drop to zero. **Stage-2 prose reads do not** — a
judgment prompt is genuine instruction, and it already lives in
`theories/<slug>/prompts/`; the contract only makes it directly addressable
via `theory.prompts` instead of findable via `THEORY.md`.

## 6. Migration plan

Six phases, each independently green, each its own commit.

| # | Phase | Touches | Behavior change |
|---|---|---|---|
| 0 | Characterization harness | `tests/characterization/` | none |
| 1 | `tools/domain.py` + shim | new file, `tests/` | none |
| 2 | `normalize()` returns `Market` | both clients, `board.py`, `snapshot.py` | none |
| 3 | `Theory` ABC + adapters + registry | new files, theory `__init__.py`, `pipeline.py` (one added key, section 4.5) | none |
| 4 | Docs and skill rewrite | `tools/README.md`, `CLAUDE.md`, `find-edge` | none |
| 5 | Port theory internals; delete shim | `theories/**` | none |

**Phase 0 gates everything.** No production code changes until the golden
files exist and pass.

**Phase 4 before Phase 5 is deliberate.** The conventions must be written
down before the largest code change lands, or a session interrupted between
them reads `tools/README.md`'s current "no base class" text and reverts the
work.

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
  keys only**, per section 4.5; every other golden below is whole-value
  equality
- `mention_bucket.find_candidates(...)`, `rank(..., frozen_rates)`
- `kalshi.markets.normalize(raw)` for every fixture row, **`raw` included**

Every golden is generated with a frozen `now` and frozen bucket rates, so
nothing depends on wall clock or DB state.

**The pass condition is equality against the golden, unchanged, at every
phase.** A diff is not a signal to update the golden; it is a signal that
the phase changed behavior and must either be fixed or escalated to a
version bump (section 8.2).

**Additional tests introduced by this work:**

- `tests/test_domain.py` — invariants, delegating properties, frozen-ness,
  `raw` passthrough identity.
- `tests/test_theory.py` — ABC cannot be instantiated; a subclass missing
  `screen`/`price` fails; `record()` is not overridden by any subclass.
- `tests/test_registry.py` — discovery finds both theories;
  `check_drift` detects each of its three mismatch kinds.
- `tests/test_conventions.py` — every theory package exposes `THEORY`
  subclassing `Theory`; the section 4.2 shim is imported only from
  allowlisted modules.

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

## 9. Success criteria

1. Every characterization golden passes unchanged at every phase.
2. Both theories run end to end through `Theory` with no version bump.
3. `find-edge` runs both theories without opening either `THEORY.md`.
4. `registry.check_drift(conn)` returns empty; a conventions test enforces
   it.
5. `tools/README.md` and `CLAUDE.md` no longer contradict the code.
6. No new class in `tools/sizing.py`, `buckets.py`, `rank.py`, `http.py`,
   `db.py`, or `cli.py`.
7. Adding a hypothetical theory #3 requires writing `screen()` and
   `price()` and nothing else — demonstrated by a test-only stub theory.

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

**`CLAUDE.md`** — a short conventions section: theories subclass `Theory`;
domain values are frozen dataclasses from `tools/domain.py`; bare dicts are
confined to the API and JSON boundaries; `record()` is never overridden.

**`.claude/skills/find-edge/SKILL.md`** — step 2 replaced with the section 5
loop. The prose at line 74, "check whether this theory has a stage 2",
becomes `judgment_payload() is None`.

**`.claude/skills/propose-theory/SKILL.md`** — scaffold a `Theory` subclass
rather than a free-function module.
