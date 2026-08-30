# Go session structure — consistent decisions from structural surfaces

Date: 2026-08-30. Status: **implemented 2026-08-30** (user approved same
day; §11 phases 1–4 shipped — key + evaluator + `cli promote`,
DB-discipline guards (`tests/test_db_discipline.py`, added by user
direction mid-review), runbooks standardized + two written, go rewritten,
find-edge/score-theories consistency edits, `score report --save`.
Phase 5, the peer `session_claims` table, stays deferred per §3.)

## 0. The principle this spec exists to serve

**Anything two `go` sessions should decide the same way must be decided by
a structural surface — a key, a runbook, an evaluator, a fixed report
shape — that the session cites, never by per-session judgment.** LLM
judgment stays where it is irreplaceable (stage-2 verdicts inside
interpretive theories, connecting dots across theories, choosing menu
work); it leaves every place where a written rule or a computation can
answer. This is the session-level application of the repo's existing
division of labour: a model categorizes against stated definitions;
measurement quantifies; structure decides what is reported.

The test for every change below: *would two competent sessions, handed the
same DB on the same day, produce the same floor, the same bets table, and
the same escalations?* Today the answer is no, for the reasons in §1.

## 1. Problem — the consistency inventory

Each row is a decision `go` sessions make today without a shared surface,
with the observed failure that motivates fixing it.

| decision | current surface | observed inconsistency |
|---|---|---|
| Is this bet reported to the user? | scattered rules (find-edge §7, go Rules, CLAUDE.md) + session judgment | The user cannot predict what a session will surface. The repo's best-evidenced result (insider_judgment v3 slice `strong-moderate-no`, READY OOS: 89 clusters, 43 days, +4.31/+8.06 net) is invisible by default while unproven claims get tabled; sessions decide ad hoc how to caveat. |
| How thoroughly is a theory run? | go §2 says "re-run each"; depth unstated | 4 of 6 theories have a RUNBOOK.md; 2 running theories (`no_side_premium`, `structural_arb`) have none, so "ran the theory" means whatever the session decided it meant. |
| Does a sub-theory's evidence drive the recommendation? | slices machinery exists; find-edge §6 mandates per-segment ranking, go never mentions it | A session running the go floor alone never consults slices; the proven-subset-inside-failing-parent case (the user's explicit requirement) is only handled if the session happens to invoke find-edge. |
| What happens when peer sessions exist? | nothing | 2026-08-30: four sessions collided on one board; a defective duplicate run (9,777 attempts, no categories) had to be quarantined; two coordinating peers stood down with nothing notifying the survivor. |
| When may a session stop or ask the user a question? | go §3 exits; otherwise ad hoc | Sessions block on questions the user has ruled they should not ask (memory: escalate only money, retirements, permission blocks — everything else is the session's call). |
| What shape does the report take? | prose guidance in go §5 | Every session invents its own format; the user re-learns how to read the report each day. |
| Which evidence row feeds a claim? | no-mixing rule in find-edge §6 | `state` EVIDENCE renders "scores never written" because `save_score` has no production caller — the orientation surface disagrees with what sessions compute by hand. |

## 2. The restructured session contract

`go` becomes six phases. §0–§3 are the **floor** — not a choice, same
every session, and **completed and reported before any phase-4 work
begins**: no autonomous menu item starts until every running theory has
been run in whole and every bet it produced has been recorded and
promoted (or explicitly held at a recording-only rung). §4 is the
existing value-menu loop, unchanged. Phase numbering below is what the
rewritten SKILL.md will carry.

**Scope principle (user, 2026-08-30): a skill edit is in scope exactly
when it makes sessions perform more consistently.** go is the primary
target — the floor ordering above is the spec's centerpiece — and other
skills are edited only where they would otherwise answer the same
question a different way: find-edge adopts the same promotion path (§6),
score-theories' settle step starts persisting the scores it computes
(§6). No skill is edited for any other reason.

| phase | name | consistency surface |
|---|---|---|
| 0 | Peers | peer protocol (§3) |
| 1 | Orient | existing (`get_board(force=True)`, `state`, queue) |
| 2 | The floor: settle, then run every theory | RUNBOOK.md, standardized (§4) |
| 3 | Promote | promotion key + `cli promote` (§5–§6) |
| 4 | Value menu loop | existing go §3, unchanged |
| 5 | Log & report | report contract (§7) |

Two session-wide rules bind throughout: **record everything** (§4) and
**never ask, always escalate** (§8).

## 3. Phase 0 — peer sessions

At session start, before the board pull:

1. `ListAgents`. No peers working this repo → say "no peers" in the floor
   report and continue.
2. Peers found → send each **one orientation message** in a fixed shape:
   this session's identity, that it is starting a go floor, and which
   floor items it intends to own (board pull, settle run, the per-theory
   list). Ask for their claims by return message.
3. Divide: floor items claimed by a peer are theirs — this session
   verifies completion (the freshness check, `state`) rather than
   redoing them. Unclaimed items belong to this session. No reply after a
   short continue-anyway interval → proceed with everything, say so in
   the report, and re-check before any expensive duplicate (the board
   force floor already makes the pull collision-safe).
4. The board is the worked precedent: on 2026-08-30 peer `ec` pulled at
   19:22Z and three sessions shared it because the 30-minute force floor
   made re-forcing impossible. The protocol extends that shape — one
   owner per floor item, everyone else reads the shared result — to
   settles and theory runs.

**Authorization note:** the standing memory rule "no unprompted peer
messaging" gets a recorded carve-out — the phase-0 orientation message is
user-directed (this spec, 2026-08-30), and it is the *only* unprompted
message the phase authorizes. Coordination beyond it follows the peer's
reply.

**Deliberately deferred:** a `session_claims` DB table (claim +
heartbeat, so ownership survives a dead session). The 2026-08-30
collision argues for it, but the message protocol plus the force floor
may be enough; build the table only if collisions recur under the
protocol — the log entry documenting a recurrence is the trigger.

## 4. Phase 2 — the floor: every theory, run to its runbook's depth

Phase 2 keeps go §2's two halves (settle & score first, then run) and its
per-version freshness check, and adds the missing structure:

**RUNBOOK.md becomes a required, standardized surface for every running
theory.** `insider_judgment`'s is the model: a stages table (who decides
— code or judgment — per stage), the exact run procedure, what gets
recorded, and what the report must say. Standardized required headings:

- `## Stages` — the stages table. "Run the theory" means *every stage in
  this table*, not stage 1. A session that runs the screen and skips the
  judgment stages has not run the theory; if a stage is genuinely blocked
  (no judge budget, API down), the floor report says which stage and why.
- `## Run` — the commands/calls, in order, with run_id conventions.
- `## Record` — what lands in the ledger, including rejections and
  gate counts by category (the always-report-what-the-gate-removed rule).
- `## Report` — the line(s) this theory's floor entry must contain
  (e.g. insider_judgment: gate_counts; structural_arb: violations found
  and removed-by-category).
- `## Skip` — the conditions under which today's run may be skipped
  (already-ran-today-at-current-version, plus any theory-specific ones).

Missing runbooks are written at implementation (`no_side_premium`,
`structural_arb` — both simple: their theory.py is mechanical), and a
conventions test holds the invariant from then on:
`test_every_running_theory_has_a_runbook` — every theory whose status is
in `theories.SCANNABLE_STATUSES` has a RUNBOOK.md containing the five
headings. A theory cannot enter `testing` without one.

**Record everything.** Every candidate a theory's procedure produces is
recorded regardless of the theory's standing — probation, `under_review`,
n=0, all of it. Recording and recommending are different acts wired to
different surfaces: the ledger takes everything (it is how unproven
theories accrue the evidence that would prove them, and how rejections
stay a control group); the *report* takes only what the promotion key
promotes. No session ever declines to record a bet because the theory
looks weak, and never surfaces one because it looks strong — both
directions of that judgment now belong to §5.

## 5. The promotion key

New file: `docs/promotion-key.md` — **the single surface that decides
what the user is told about**. It carries a version (`Key version: 1`),
named rungs, and a changelog. Every bet in every report cites its rung;
every bet withheld is withheld *by* a rung. A session that cannot name
the rung for a decision has found a gap in the key, and the gap — not an
improvised call — goes in the report.

The rungs. Preconditions common to R1–R3: the candidate's market is
still open, the edge is recomputed at **today's ask** (`markets.quotes`,
never the recorded entry price), and for a judgment theory the candidate
is `endorsed` (stage 2 ran); mechanical theories (`uses_llm_judgment =
False`) promote from `screened`, per the existing edge_basis rule.

| rung | name | criteria (all mechanical, over recorded fields) | report treatment |
|---|---|---|---|
| R1 | RECOMMENDED | ranking segment (per `slices.ranking_segment`, chain pool) is past evidence gates (n_clusters ≥ 10, n_days ≥ 5 OOS) with `calibration_edge_net` > 0; claimed net edge at today's ask > 0; executability passes | Bets table. The strongest thing the system can say. |
| R2 | RISKLESS | basket with `cost ≤ min_payout` fees included (an arbitrage, not a forecast) | Bets table, own bucket; legs itemized with per-leg asks and the verify-all-legs warning; never averaged into forecast numbers. |
| R3 | PROVISIONAL | segment's OOS point estimate positive but below the gates, **and** spans ≥ 3 settlement days (ruling 14: fewer is not a measurement); claimed net edge at today's ask > 0; executability passes | Bets table, labeled with exactly what is missing ("n_clusters 7/10, n_days 4/5"). This is the user's "close to an edge — recommend accordingly" tier. |
| R4 | ACCRUING | recorded; none of R1–R3's evidence conditions met (probation with no settled OOS record, `prior` basis, positive estimate spanning < 3 days) | Activity section: counts per theory, top few by the theory's own stage-1 ordering where one exists. Never in the bets table. |
| R5 | MEASURED-AGAINST | segment past the gates with `calibration_edge_net` ≤ 0, or n ≥ PROBATION_N with realization 0 | Named warning in the Activity section — suppressed from bets *even when today's claimed edge is positive*, because the measured record outranks the claim. Feeds the diagnosis queue (score-theories §5), not the trash. |
| R6 | CONTROL | `rejected` rows; observation rows (ruling 13 — claimed edge ≤ 0 recorded so cells accrue); post-interpretation screened re-sights | Counts only. These are measurements of the board or the control group, not bets, and no session may present one as a bet. |

Structural notes, part of the key:

- **Segment precedence is the sub-theory rule.** `ranking_segment` already
  encodes it: a candidate matching a ready slice ranks on the slice's own
  OOS record — so a proven subset promotes to R1 while its parent's
  aggregate sits at R4/R5, and a failing subset drags exactly its own
  candidates to R5 while the complement stands. The key adds no new
  mechanism; it makes consulting the existing one non-optional.
- **Orphaned evidence.** A ready slice on a theory version that is not
  current (breaking bump, rule not adopted — insider_judgment v3's
  `strong-moderate-no` under v4 is the live case) promotes nothing by
  itself: v(current) rows are not entitled to v(prior) evidence unless a
  proven carry pools them (`chain_versions` present) or the bump adopted
  the rule (cite the prior segment explicitly, per the existing CLAUDE.md
  rule). The evaluator surfaces every such orphan as an **escalation**:
  "proven edge exists on a predecessor's rule; current version has not
  adopted it — adoption is a version-bump decision." That converts the
  strongest result in the repo from silently invisible to a standing item
  the user sees every session until ruled on.
- **Executability** (a judgment find-edge §3 names but leaves unstated —
  both paths now use these stated thresholds): takeable means current spread < claimed net edge, and ask-side depth ≥
  the theory's stated minimum (from its RUNBOOK; default 1 contract —
  i.e. a quote exists). Fails → demote to R4 with `not_takeable` noted.
  Thresholds live in the key, so tightening them is a key-version bump,
  not a session mood.
- **Dissent, not override.** When the session believes a rung's answer is
  wrong for a candidate, it reports the rung's verdict *and* the dissent
  as a proposed key amendment. It never moves the candidate itself. The
  key changes by edit + version bump + log entry, exactly like a theory
  procedure.

## 6. The evaluator — `tools/promotion.py`, `cli promote`

The key's rungs are all predicates over recorded fields, so code
evaluates them — the session never eyeballs n's and nets against the
table (eyeballing is where the documented row-mixing failures live).

- `promotion.promote(conn, opportunity_id, *, ask=None) -> Promotion` —
  frozen dataclass: `rung`, `rung_name`, `segment` (from
  `ranking_segment`, chain pool, with `chain_versions` passed through),
  `rank_inputs`, `ranked_edge` (via `rank.ranked_edge`), `claimed_edge_at_ask`,
  `reasons` (every criterion checked, pass/fail — the citation the report
  prints), `escalations` (orphaned evidence, key gaps), `key_version`.
- `promotion.promote_run(conn, run_id)` / `cli promote --run <run_id>` —
  batch over a run's rows, one `segment_report` per (theory, version),
  quotes fetched once per ticker batch. `cli promote <opportunity_id>`
  for the single-row case.
- `KEY_VERSION` constant mirrors the doc header;
  `test_promotion_key_version_matches_doc` fails at the commit that bumps
  one without the other (same pattern as the moved-rule manifest test).
- **No new table.** A promotion is re-derivable: DB state + key version →
  same output. The report cites the key version; auditability comes from
  determinism, not storage.

Two consistency edits ride on the evaluator, both passing the §2 scope
principle:

- **find-edge §6–§7 switch to the same evaluator and rung vocabulary** —
  one promotion path however the question arrives ("go" or "what's the
  best bet right now"). Without this, the two entry points would rank
  and report the same candidate differently, which is the exact
  inconsistency this spec removes. find-edge's marked rule blocks
  (`judge-blind`, `batch-and-dedupe`, `buckets-from-deep-stage`) stay
  intact.
- **The settle step persists its computed score rows via the existing
  `save_score`** (one-line touch in score-theories), closing the carried
  "nothing writes `scores`" gap so `state` EVIDENCE stops rendering
  empty against what sessions compute by hand — the orientation surface
  and the computed reality become the same number.

## 7. The report contract

Fixed sections, fixed order, every session. A reader who learns the shape
once can find anything in any future report.

1. **Floor** — peers found and division of labor; per-theory line in a
   fixed shape: `<id> v<n> — ran per RUNBOOK (<stages>), <candidates>
   recorded, gate removed <counts by category>` or `blocked at <stage>:
   <why>` or `skipped: <skip-condition>`; settlements landed and score
   movements. "Ran clean, 0 candidates" is stated per theory (the ledger
   cannot say it).
2. **Bets** — one table: rung, ticker, side, today's ask, claimed net
   edge, ranked edge, segment, n/n_days behind it, basis, theory,
   bucket + interpretation (judgment theories), suggested size. Grouped
   R1, R2, R3; a header line cites the key version. Empty is a valid and
   honest table.
3. **Activity** — R4 counts per theory (top few each), R5 warnings by
   name, R6 counts. This is where "the bets exist and are recorded, just
   not recommended" lives — visible without being endorsed.
4. **For your ruling** — everything escalated instead of asked (§8):
   pending retirements, orphaned evidence, key gaps and dissents,
   permission-blocked actions. Carried every session until ruled.
5. **Queue** — endorsed-untouched-unsettled positions re-quoted (same
   position standing / closed out as stale, per existing go rules), and
   mark-taken asks **by id**.

## 8. Never ask — escalate and continue

An autonomous session **does not stop to ask the user anything.** Three
routes, in order:

1. **A structural surface answers it** (key, runbook, skill, ruling) →
   take that answer and cite it.
2. **Reversible, in scope, no surface answers it** → decide, act, record
   the decision and reasoning in the log. If the gap will recur, propose
   the amendment in §7.4.
3. **User-only** — money movements, retirements, destructive/irreversible
   operations, permission-layer blocks (the standing supervisor-authority
   ruling's list) → write it to §7.4 **and keep working** on everything
   the blocked item does not gate.

A session may end only at go's two existing exits (nothing
decision-changing left, or *everything remaining* is user-blocked). "I
have a question" is never an exit; the question goes in §7.4 and the
session takes the next menu item.

## 9. What stays judgment — explicitly

So the spec cannot be read as "mechanize everything": stage-2 verdicts
inside interpretive theories (bucket + rationale, as ever); endorse/reject
on judgment-theory candidates; choosing §4 menu work and how much to
delegate; diagnosis of R5s; reading a novel situation the key has no rung
for (which produces an escalation and a proposed amendment, and the
session's own best-judgment *label* pending the ruling). The promotion
key does not judge candidates; it decides what the *user is told* about
candidates already judged.

## 10. Components

- `docs/promotion-key.md` — new; the key (§5), version 1.
- `tools/promotion.py` — new; evaluator (§6).
- `tools/cli.py` — `promote <opp_id> | --run <run_id>`.
- `tools/score.py` settle-step call site — persist via `save_score`.
- `.claude/skills/go/SKILL.md` — rewritten to the §2 phase structure;
  §0 peers, floor rewritten onto runbooks, phase 3 promote, report
  contract, never-ask rule. The `notes-theory-log-split` marked rule
  block moves intact.
- `.claude/skills/find-edge/SKILL.md` — §3 executability and §6–§7
  ranking/report switch to the evaluator and rung vocabulary (§6's
  consistency rationale); marked rule blocks intact.
- `.claude/skills/score-theories/SKILL.md` — settle step persists
  scores; no other change.
- `theories/no_side_premium/RUNBOOK.md`,
  `theories/structural_arb/RUNBOOK.md` — new, to the §4 template;
  existing runbooks get the five headings (content is already there).
- `tests/` — `test_promotion.py` (rung criteria incl. every precedence
  and precondition; orphan escalation; executability demotion);
  conventions: runbook presence + headings, key-version match.
- Memory file `feedback_no_unprompted_peer_messaging.md` — record the
  phase-0 carve-out.
- CLAUDE.md — one pointer line to the key under "How ranking works"; no
  rule bodies (single-home ruling).

## 11. Rollout

1. **Key + evaluator + tests** (`docs/promotion-key.md`,
   `tools/promotion.py`, CLI) — usable standalone the day it lands.
2. **Runbooks** — write the two missing, retrofit headings, conventions
   test.
3. **Skill rewrites** — go first, then the two consistency adoptions
   (find-edge onto the evaluator; score-theories' persist line),
   against the shipped surfaces.
4. **Score persistence** repair (`save_score` call site + its test).
5. Peer `session_claims` table — deferred; trigger per §3.

Each phase is independently landable; a session interrupted mid-rollout
leaves working surfaces, not a half-wired contract.

## 12. Alternatives considered

- **Pure-code promotion, no key document** — rejected by the user and
  rightly: interpretive stage-2 and novel situations need a citable text
  the LLM applies; code alone would either block on them or push the
  judgment back underground.
- **Pure-text key, LLM applies it by reading** — rejected: eyeballing
  numeric predicates against a table reinstates the row-mixing and
  anchoring failures the repo already documents; every mechanical rung
  is evaluated by code, the text is the authority the code implements.
- **Promotion thresholds inside each theory** — rejected: promotion is a
  cross-theory reporting policy; per-theory bars would drift apart and
  re-create the inconsistency this spec removes. Theories own *evidence*;
  the key owns *what evidence suffices to tell the user*.
- **A `promotions` table** — rejected for now: deterministic and
  re-derivable from durable inputs; storage adds a sync burden with no
  audit gain. Revisit only if key versions churn enough that
  reconstructing "what did the user see" needs pinning.
- **Blocking peer-claims table first** — deferred (§3): protocol before
  machinery; the force floor precedent suggests light structure may
  suffice.

## 13. Defaults awaiting your veto (not questions)

Per §8, these ship as stated unless overruled on review:

1. **R3 has no minimum-edge threshold** — every positive-estimate,
   below-gates candidate that passes executability is reported with its
   numbers. Rationale: the shrinkage display and the "what's missing"
   label do the discounting; a threshold would hide exactly the
   near-edges you asked to see.
2. **Executability defaults**: spread < claimed net edge; depth ≥ 1
   contract at the ask unless a runbook states more.
3. **`session_claims` deferred** until a collision happens under the
   phase-0 protocol.
4. **R1/R3 recompute at today's ask** even for same-day rows (quotes are
   cheap; a stale ask is the documented queue-decay failure).
