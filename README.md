# Market Edge Finder

An agentic research harness for finding mispriced [Kalshi](https://kalshi.com)
prediction markets. Codex or Claude Code is the researcher: it invents trading
hypotheses ("theories"), backtests them against historical markets, records
every recommendation in a ledger, and accumulates a calibration track record
that separates theories with a real edge from theories that only sound good.

The human places every bet by hand. The system's job is to answer one
question with evidence behind it: **what bet can be taken right now with the
best edge?**

## How it works

**Theories are instruments.** Each theory is a lens that surfaces bets the
others can't — one reads resolution language, one reads base rates, one reads
cross-platform divergence. No single theory answers the question; running many
and weighting each by its demonstrated track record does. Each theory lives at
its registered path under `theories/`, with a `THEORY.md` stating its hypothesis
and decision procedure. Procedure changes bump the version; explicit evidence
chains record whether earlier measurements still apply.

**Pipelines propose, judgment disposes.** A theory has up to two stages: a
mechanical screen (code, cheap, scans the whole ~100k-market board) and an
interpretive judgment pass (an LLM, expensive, sees only what the screen kept).
Mechanical questions belong in code: they are reproducible and can replay all
reachable history. Interpretive theses use judgment and accrue evidence within
the judge's verified post-cutoff window. Both earn credibility from measurement.

**No introspected probabilities.** The model never states a probability it
"feels." It classifies against stated definitions, extracts structural
features, and assigns a confidence bucket — then `tools/buckets.py` converts
the bucket to a number using that bucket's *realized* win rate. Every recorded
edge carries an `edge_basis`: `measured` (the bucket earned it), `model` (a
mechanical calculation), or `prior` (a placeholder awaiting data). There is
deliberately no basis meaning "it felt about right."

**Rejections are data.** Every candidate gets a disposition — `screened`,
`endorsed`, or `rejected` — and rejected candidates still settle, giving a free
control group that measures whether the judgment stage adds edge or destroys
it.

**Claimed edge is shrunk toward demonstrated edge.** Ranking multiplies a
theory's claimed edge by a credibility factor built from its sample size and
realized calibration, so a new theory claiming 12 points ranks as 3 — visible,
not dominant — and a theory tested and found wanting ranks at zero.

**Provenance is mandatory.** Any theory with an LLM in its decision path
records the actual judging model, supplied effort, search status, and exact
rendered prompt for each stage and batch. An edge you cannot reproduce is an
anecdote.

Judged runs can resume from saved screens and completed batch receipts using
the procedure in `docs/agents/judgment-batches.md`. Valid A/B backtests count
fully toward production probabilities and evidence gates, including when no
live track record exists. Shared eligibility also reports excluded replay
rows and their reasons.

## Layout

| Path | What it is |
|---|---|
| `AGENTS.md` | Shared startup instructions; `CLAUDE.md` imports this entrypoint |
| `docs/RESEARCH_GUIDE.md` | The complete research policy for both applications |
| `docs/agents/` | Runtime adapters for dispatch, model identity, and shell differences |
| `.agents/skills/` | Canonical research workflows; `.claude/skills/` contains generated discovery entrypoints |
| `theories/` | One folder per hypothesis: `THEORY.md`, screen code, prompts |
| `tools/` | Single-purpose scripts: Kalshi/Polymarket clients, ledger, scoring, ranking, sizing (see `tools/README.md`) |
| `db/` | SQLite source of truth (`schema.sql` is tracked; the database itself is not) |
| `tickets/new-theory/` | The backlog: one spec per proposed theory, plus the shared contracts every spec inherits |
| [`knowledge/README.md`](knowledge/README.md) | Browse question summaries, scoped lessons, and original evidence |
| `RESEARCH_LOG.md` | Bounded recent changes; historical narrative is linked from the archive map |
| `tests/` | Pytest suite mirroring `tools/` |

## Using it

For accumulated findings, begin with [the knowledge map](knowledge/README.md).
Choose a relevant branch rather than reading whole notebooks. New research
context follows [the memory policy](docs/agents/research-memory.md).

Open this repository in Codex or Claude Code and say `go` for an autonomous
research session, or just ask — "what's the best bet right now?", "how is
insider_judgment holding up?". Explicit coding requests stay focused on the
requested code change. The app reads its entrypoint and then the shared
research policy through a task-to-section map; no global plugins, filesystem
links, or API keys are required. Universal constraints load at startup, while
the complete guide remains available for reference and broad policy work.

Use Python 3.11 or later. From the repository root:

```bash
python -m pip install -r requirements.txt
python -m tools.agent_setup --check
python -m pytest tests/ -q
```

Codex discovers the canonical skills directly. Claude discovers the checked-in
entrypoints and reads the same canonical files. After editing skill metadata
or adding a skill, run `python -m tools.agent_setup` and commit the source and
generated entrypoints together. Editing a procedure's body needs no copy step.
Personal Claude skills with different names are preserved.

The adapters describe the native tools available in each app. Use the actual
tool inventory and supported model identifiers in your session. `supervise`
caps managed research workers at three and derives the active target from the
host's advertised concurrency after reserving one global slot for required
worker-created judgment and counting other active agents. Mixed Codex/Claude
workers launched by an external supervisor are outside this integration.

Switching the model that judges a theory is a research change. Record its
actual model, effort, and prompt, and evaluate it in an isolated experiment
before deciding whether existing calibration applies. Never rename historical
Claude results as Codex results or borrow a different model's knowledge cutoff.

The CLI underneath is plain Python:

```bash
python -m tools.cli --help
python -m tools.cli ideas search "<keyword>"      # research memory
python -m tools.cli opportunities mark-taken <id> taken --theory <slug> --size <N> --reason "<why>"
```

That last command is how the system learns what you actually bet — without it
there is no realized-ROI signal to score against.

A few more worth knowing: `python -m tools.cli db backup` gzips every table
except `market_snapshots` into a non-synced local directory, so the track
record survives a lost or corrupted working database. `python -m tools.cli
state` renders the session's orientation surface (running theories, standing
rulings, evidence, the endorsed-but-untaken queue, data freshness) straight
from the DB — pass `--write` to also drop it to `STATE.md` for humans.
`python -m tools.cli rulings record|list|status` keeps binding rulings as
queryable rows instead of prose buried in `RESEARCH_LOG.md`'s tail.

## Design constraints

- **No credentials.** Every endpoint used is public; there are no API keys
  anywhere in the repo. LLM judgment runs through the user's Codex or Claude
  Code subscription.
- **Kalshi is where bets are placed; Polymarket is a research instrument**
  (it exposes wallet-level trade data Kalshi doesn't). Every recommendation
  must resolve to a specific Kalshi ticker.
- **Backtests are tiered by contamination risk**: tier A (no LLM in the
  decision path — full history is valid evidence), tier B (LLM judgment on
  post-cutoff markets only), tier C (pre-cutoff, contaminated, excluded from
  credibility).
- **Only the human retires a theory.** The model diagnoses and proposes;
  an underperforming theory is a research object, not trash.
