# Market Edge Finder

An agentic research harness for finding mispriced [Kalshi](https://kalshi.com)
prediction markets. Claude Code is the researcher: it invents trading
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
and weighting each by its demonstrated track record does. Theories live in
`theories/<slug>/`, each with a `THEORY.md` stating its hypothesis and decision
procedure. Any change to that procedure bumps the theory's version, so a track
record never silently merges two different strategies into one number.

**Pipelines propose, judgment disposes.** A theory has up to two stages: a
mechanical screen (code, cheap, scans the whole ~100k-market board) and an
interpretive judgment pass (an LLM, expensive, sees only what the screen kept).
Purely mechanical theories are preferred where possible — they cost nothing per
candidate, are fully reproducible, and backtest against all of history rather
than the thin post-knowledge-cutoff window an LLM judge is restricted to.

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
records which model judged and the exact prompt file, per stage, per run. An
edge you cannot reproduce is an anecdote.

## Layout

| Path | What it is |
|---|---|
| `CLAUDE.md` | The researcher's operating manual — the real spec for how this repo works |
| `theories/` | One folder per hypothesis: `THEORY.md`, screen code, prompts |
| `tools/` | Single-purpose scripts: Kalshi/Polymarket clients, ledger, scoring, ranking, sizing (see `tools/README.md`) |
| `db/` | SQLite source of truth (`schema.sql` is tracked; the database itself is not) |
| `docs/superpowers/specs/theories/` | Sketches of proposed theories not yet built |
| `RESEARCH_LOG.md` | Session-to-session continuity — what was tried, found, and killed |
| `tests/` | Pytest suite mirroring `tools/` |

## Using it

Open the repo in [Claude Code](https://claude.com/claude-code) and either say
`go` for an autonomous research session, or just ask — "what's the best bet
right now?", "how is insider_judgment holding up?".

The CLI underneath is plain Python:

```bash
pip install -r requirements.txt
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
  anywhere in the repo. LLM judgment runs on the Claude Code subscription.
- **Kalshi is where bets are placed; Polymarket is a research instrument**
  (it exposes wallet-level trade data Kalshi doesn't). Every recommendation
  must resolve to a specific Kalshi ticker.
- **Backtests are tiered by contamination risk**: tier A (no LLM in the
  decision path — full history is valid evidence), tier B (LLM judgment on
  post-cutoff markets only), tier C (pre-cutoff, contaminated, excluded from
  credibility).
- **Only the human retires a theory.** The model diagnoses and proposes;
  an underperforming theory is a research object, not trash.
