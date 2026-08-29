# The raise lane: `BETS.md`, the bets the user should be taking

Designed with the user, 2026-08-29. Companion to
`2026-08-29-enforcing-surfaces-design.md` — its §4 names the dead loop this
spec closes from the human side — but deliberately a separate spec: the
enforcing-surfaces work makes existing rules bind, while this adds a new
surface with its own schema, command, and document.

## 1. The problem

### 1.1 There is no surface that tells the user to bet

The ledger holds 32,607 opportunity rows. `user_action='taken'` on **2**.
Every theory's `roi_taken` is `null`, and the user-divergence signal
`compare-theories` was built to mine has never had an input.

The enforcing-surfaces spec's §4 diagnosed the friction on the *recording*
side (`mark-taken` ergonomics) — but recording presupposes a bet was placed,
and nothing in the repo tells the user a bet is worth placing. Findings live
in session reports that scroll away, and in a QUEUE line of the proposed
`state` command that is built for sessions, not for a person deciding
whether to open their Kalshi app. The user's own framing of the gap: *"any
time I should be taking a bet, that gets updated so I know to take it."*

### 1.2 The inclusion bar is a judgment act, ruled by the user

Asked what earns a bet a place on the document, the user ruled:

> whenever an LLM is convinced it should raise the bet to me is how I would
> view it.

So the bar is **not** a mechanical threshold over `ranked_edge` — it is the
session's own judgment that this bet is worth the user's attention, exactly
the "final selection: you, this session" step the subagent-tiering table
already assigns to the operator. The design consequence: presence on the
document is created by one deliberate act (**raising**), and everything
around that act — rendering, quoting, dropping — is code.

### 1.3 Decisions recorded

- **Inclusion**: a session raises a bet when convinced; no mechanical bar
  (§1.2).
- **Freshness**: file only — no notification plumbing. Staleness is handled
  by as-of timestamps and drop rules (§6).
- **Standalone spec**, not a section of enforcing-surfaces (user call).
- **No retroactive raises**: the 8 endorsed rows that predate this lane
  stay unraised; the next session that reviews them decides.

## 2. The principle: raising is judgment, everything else is mechanical

A raise references an existing opportunity row. That single constraint does
most of the work:

- The ledger contract is never bypassed — a raised bet already carries
  provenance, an honest `edge_basis`, claimed and ranked edge, and a Kalshi
  ticker, because `record_opportunity` enforced all of that when the row
  was written. The raise adds one sentence of *why the user should care*,
  not a parallel bookkeeping path.
- The renderer never decides what belongs on the document. It re-quotes,
  applies drop rules, formats, and writes. **No auto-raising, ever** — a
  mechanical theory whose candidates arrive recommendable still reaches the
  document through a session choosing to raise them.
- `BETS.md` is a render; the DB is the source of truth, as it is for
  everything else structured. The file is gitignored for the same reason
  the enforcing-surfaces spec gitignores `STATE.md`: a tracked generated
  file drifts the moment someone edits it.

Raise history is data worth keeping past settlement. Raised-and-taken
versus raised-and-ignored is precisely the divergence population §4 of the
enforcing-surfaces spec wants and has never had; dropping a raise therefore
*closes* it (timestamp + reason), never deletes it.

## 3. Schema

```sql
CREATE TABLE raises (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    raised_at      TEXT NOT NULL,      -- UTC ISO-8601
    raised_by      TEXT NOT NULL,      -- session identity
    note           TEXT NOT NULL,      -- the one-sentence human case
    ask_at_raise   REAL,               -- the ask when raised; entry_price
                                       -- on the row is the ask when recorded,
                                       -- and the two legitimately differ
    dropped_at     TEXT,
    drop_reason    TEXT                -- 'settled' | 'closed' | 'taken'
                                       -- | 'withdrawn: <why>'
);
CREATE UNIQUE INDEX one_open_raise_per_opportunity
    ON raises(opportunity_id) WHERE dropped_at IS NULL;
```

`note` is mandatory and human-facing — it is the sentence the user reads on
their phone, not a research rationale (that already lives on the
opportunity row). `raised_by` follows the session-identity convention the
log already uses.

### 3.1 One refusal, in the house idiom

`bets raise` **refuses** a row whose theory declares `uses_llm_judgment`
and whose `disposition` is still `'screened'`. `CLAUDE.md` already forbids
presenting a judgment theory's unresearched screen output as a
recommendation; the raise command is where that rule can be made
unskippable instead of hortatory, exactly as `record_opportunity` made
provenance unskippable. The fix is never an override flag — it is doing the
stage-3 research and endorsing the row, after which the raise goes through.
Mechanical rows (`edge_basis` `'model'`/`'measured'`) raise directly from
`'screened'`, because for them screened means "needed no interpretation."

## 4. CLI

```bash
python -m tools.cli bets raise <opportunity_id> --note "<one sentence>"
python -m tools.cli bets drop <opportunity_id|ticker> --reason "<why>"
python -m tools.cli bets render
python -m tools.cli bets list
```

- **`raise`** — writes the row (capturing the current ask as
  `ask_at_raise`), then renders.
- **`drop`** — closes the raise with `withdrawn: <why>`, then renders.
  Ticker form refuses on ambiguity (two theories can hold open raises on
  one ticker), printing the matches — the enforcing-surfaces §4.2
  precedent. For mechanical deaths (settled, closed, taken) no one runs
  `drop`; the renderer notices (§5).
- **`render`** — re-quotes every open raise's ticker via
  `markets.quotes(tickers)` (never a board pull), auto-closes raises whose
  market settled or closed or whose opportunity was marked taken (each
  with its reason), and writes `BETS.md`. A raise whose *edge* has decayed
  — the ask moved until net edge ≤ 0 at current price — is **flagged, not
  auto-dropped**: the ask can come back, and withdrawing a judgment is the
  judge's call, so the flag is a prompt for the next session to re-decide.
- **`list`** — the same content in the terminal.

## 5. The rendered document

`BETS.md`, repo root, gitignored. Ordered by ranked edge, computed per
slice segment as the ranking rules require. Three sections:

**Open bets** — one block per raise:

- ticker, side, market title, close time
- ask **now** (with its as-of time) next to ask at raise and ask at record
- claimed edge and ranked edge side by side, the slice segment feeding the
  rank, and the evidence behind it (n, tier)
- suggested size, from the sizing math already on the row
- the raise note — the one sentence
- a copy-paste `mark-taken` command, pre-filled with this row's identifiers
  (adopting the `--ticker` form when enforcing-surfaces §4.2 lands)
- the `EDGE DECAYED` flag when §4's render check fires

**Riskless baskets** — separate section, never mixed with forecasts: every
leg with its own current ask, the cost-versus-minimum-payout arithmetic,
and the standing warning that the user must verify **all** legs before
entering any, because execution risk across legs is reported, not modelled.

**Recently dropped** — the last handful of closed raises with their reasons,
so a bet that vanishes from the document is explained rather than
mysterious.

Footer: rendered-at timestamp, and one line of standing instruction — asks
move; verify the price before entering; after betting, run `mark-taken`
(the command the ledger needs for `roi_taken` to ever be real).

## 6. Freshness

File-only, by the user's ruling — so honesty about staleness substitutes
for push:

- **Any session that raises, drops, settles, or marks-taken re-renders
  before finishing.** The find-edge and go skills each gain one line saying
  so; the raise and drop commands render as a side effect, so the rule
  costs a session nothing in the common case.
- Every price on the document carries its as-of time; the footer carries
  the render time. A stale document *says* it is stale.
- The enforcing-surfaces `state` command's FRESHNESS block gains a
  last-render age (amendment recorded there), so every orient sees a
  decaying document without anyone thinking to check.

## 7. What this deliberately does not change

- **Betting stays manual.** The lane produces no orders and touches no
  execution path.
- **Scoring is untouched.** `raises` feeds nothing in `score.py`; raising
  affects no credibility, no calibration number, no bucket rate. A raise
  is not a disposition and does not modify the opportunity row.
- **`mark-taken` remains the only realized-ROI input.** The document
  reminds; it never records.
- **No notifications** (declined), no auto-raising, no tracked `BETS.md`.

## 8. Data conventions

Quotes fetched by `render` are persisted through the existing snapshot
path before the file is written — the render's numbers stay reconstructible
after the market moves, per "save as much as you can, while you can."
Render is otherwise deterministic given the DB and those quotes.

## 9. Testing

Fixture-DB tests in the repo's one suite:

- raise → row appears in render with claimed and ranked edge side by side
- settle / close / mark-taken → auto-close with the right reason, row moves
  to Recently dropped
- ask decay → `EDGE DECAYED` flag, raise stays open
- basket → renders in the riskless section with per-leg asks and warning
- judgment-theory `'screened'` row → raise refused; endorsed sibling raises
- mechanical `'screened'` row → raise accepted
- one-open-raise index → second raise on an open raise refused
- CLI round-trip: raise → list → drop → list

## 10. Sequencing and cross-spec touchpoints

Implementable standalone, before or after the enforcing-surfaces work.
Two soft couplings, both degrade gracefully: the rendered `mark-taken`
command uses the id form until §4.2's `--ticker` form exists, and the
FRESHNESS line lands whenever `state` does. The enforcing-surfaces spec §4
gains a one-line pointer here so the two halves of the loop cite each
other.

## 11. Out of scope

Push or any notification channel; auto-raising on any threshold; order
placement; a tracked or hand-edited `BETS.md`; retroactive raising of
pre-lane endorsed rows; any change to ranking, scoring, or slice
machinery.
