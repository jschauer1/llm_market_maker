# Research Log

Append-only. Newest entries at the bottom. One entry per research session.

This is what gives sessions continuity — read the tail before starting work,
append before finishing. Without it every session starts cold and the system
repeats itself instead of accumulating.

Format:

## YYYY-MM-DD — one-line summary

**Did:** what actually happened.
**Learned:** what you now know that you didn't.
**Next:** what is worth picking up next session.

---

## 2026-08-23 — Repo built

**Did:** Built the harness — data layer, tools, theory format, skills. Ported
`insider_bias` from `kalshi_trader` with its real track record.

**Learned:** Kalshi candlesticks carry historical bid/ask and reach back ~12
months, so tier A backtests can use executable prices. Kalshi's field schema
has changed since `kalshi_trader` (decimal-dollar strings, `_fp` sizes).
Polymarket exposes per-trade wallet identity and server-side size filtering.

**Next:** Nothing has settled under the new system yet. The highest-value work
is a tier A backtest of the `insider_bias` stage-1 screen — it is
uncontaminated, has a year of history available, and would give the first real
evidence in the ledger. **Missing prerequisite:** no adapter exists from
`history.point_in_time()`'s candle shape to the market dict `screen.screen()`
expects, and `no_ask` isn't on a candle at all — derive it as
`1 - yes_bid_close`. Step one of this work is writing that candle→market
adapter in `theories/insider_bias/`; `tools.kalshi.markets.list_settled()`
gives a workable replay universe of "markets open on date X" in the meantime.

---

## 2026-08-23 — Correcting a wrong number: `list_open()` was truncating, not the 14-day filter

**Did:** Fixed a critical bug where `tools.kalshi.markets.list_open()`
defaulted to a 10-page cap. Kalshi's `/events` feed is **not** sorted by
close time, so that 10-page prefix was not a sample of the board — it was a
biased slice containing almost no near-term markets, which is exactly what
`insider_bias`'s 14-day horizon screens for. Changed the default to page to
exhaustion (`max_pages=None`), and made an explicit `max_pages` cap raise
`TruncatedFetchError` if it is hit while the cursor is still live, instead of
warning weakly.

**Learned:** An earlier measurement (uncorrected in this log until now) had
concluded the `insider_bias` screen's 14-day horizon was the bottleneck,
citing a ~0.05% pass rate (about 1 candidate out of ~14,500 markets fetched).
That number was itself an artifact of the truncation bug, not a property of
the filter. Measured against a complete board the same day, three ways:
`list_open()` with the old defaults returned 14,544 markets and 1
`insider_bias` candidate; `list_open(max_pages=60)` returned 95,779 markets
and 784 candidates (276 events); the predecessor system's raw dump of the
same board, same day, had 32,427 markets (31,561 within the 14-day horizon)
and 960 candidates kept by its filter. **The true figure is roughly 31.5k
markets inside the horizon and several hundred surviving candidates** — the
screen is not the bottleneck, and the "handful of candidates" framing that
had been written into `theories/insider_bias/THEORY.md` was wrong. Recording
this here so the ~0.05% figure is never re-cited as if it described the
filter.

**Next:** See the entry above — the candle→market adapter for a tier A
backtest is still the top prerequisite. Separately, `insider_bias` is past
its `n=20` review trigger with a negative net calibration edge; see the
Status section of its `THEORY.md` for the numbers.

---

## 2026-08-23 — `insider_bias` is `active` but already past its review trigger

**Did:** Documented, honestly, that `insider_bias`'s `active` status was set
by the one-time migration to prove the harness works end-to-end — it was
never a claim that the imported history clears the promotion bar. Measured
now: n=29, `calibration_edge_net = -0.75` points overall; restricted to rows
the predecessor actually bet (`extra_json.status` starting `BET`, i.e.
excluding declined-limit rows recorded at zero edge), `calibration_edge_net
= -1.87`. Both are negative, and n=29 is already past the `n=20` review
trigger in `CLAUDE.md`'s lifecycle rule.

**Learned:** `find-edge` defaults to `--status active`, so as things stand
today the first session that runs it will scan a theory whose own imported
track record says it currently loses after fees. That is not a reason to
silently change the status mid-branch (the migration's semantics should not
be rewritten after the fact) — it is a reason to flag it loudly here and in
`THEORY.md` so nobody mistakes `active` for "validated."

**Next:** Validating or retiring `insider_bias` is a first-order task for an
early session: either run the stage-2 backtest (tier B/C per its `THEORY.md`)
to see whether interpretation recovers the edge the raw screen does not show,
or apply the lifecycle rule and move it to `paused`/`retired` if it doesn't.

---

## 2026-08-23 — Theory status became an evidence level; retirement became the user's call

**Did:** Reworked the theory lifecycle. Status is now an evidence level —
`proposed` → `testing` → `active`, with `under_review` for a theory failing
its own bar and `paused` reserved for one blocked on a missing prerequisite.
`under_review` **keeps running**, which is the substantive change: the old
design paused a failing theory at `n=50`, freezing its sample at exactly the
size that made the verdict unreliable. `find-edge` now runs `testing`,
`active`, and `under_review`; credibility weighting, not a scan filter, is
what stops an unproven theory crowding out a proven one.

Added a diagnosis checklist (`score-theories` §5) that must be worked before
any opinion about a theory's future, and made retirement user-only:
`theories propose-retirement <id> --rationale "..."` records a standing
suggestion and leaves the theory running; `theories status <id> retired`
refuses without both `--authorized-by user` and a proposal on file.
`theories pending-retirement` surfaces unruled proposals in every orient.

Moved `insider_bias` from `active` to `under_review` and rewrote its Status
section from "flagged as questionable" to an actual diagnosis.

**Learned:** The `insider_bias` numbers do not support any verdict yet. At
n=29 the standard error on a win rate is roughly 9 points, so
`calibration_edge_net = -0.75` is well inside the noise — the theory has been
glanced at, not measured. The interesting failure modes (fees eating a real
edge, judgment inverted over a sound screen, one profitable slice, an
inverted sign, contaminated tier, mixed versions) are all indistinguishable
from death at a glance, which is why the checklist exists.

The `theories` table needed a rebuild to widen its status CHECK; SQLite
cannot alter one in place. `db.schema_statement()` extracts the DDL from
`schema.sql` so the migration cannot drift from the schema it recreates. The
live database migrated cleanly — 96 opportunities, 49 settlements, no FK
violations.

**Next:** Unchanged and now sharper: the candle→market adapter for a tier A
backtest of the `insider_bias` stage-1 screen. It is item 1 on that theory's
own diagnosis list because it separates the screen from the judgment, which
is the single most informative split available on it.
