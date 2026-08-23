# Insider Bias

## Hypothesis

Some Kalshi markets resolve on facts a specific, identifiable group of humans
already knows while the public does not — pre-taped reality TV, award votes
already cast, executive hires the board has already made, appointments
reporters already have sourced. When that private knowledge is real, the
public price still leaves room, and buying the favorite captures the gap.

Why it persists: the crowd cannot verify the private information, so it prices
on public uncertainty. The edge is not a smarter forecast — it is recognizing
which markets have an informed minority at all.

Ported from `kalshi_trader`, where it ran from May to July 2026 and produced
the imported track record.

## Data sources

Kalshi only (`tools/kalshi/markets.py`). No Polymarket dependency.

## Status

`active` — imported with real history from `kalshi_trader`.

## Version

1 — initial port. Stage 1 is a faithful port of the original deterministic
filter. Stage 2 replaces the OpenAI classify/pick calls with Claude/subagent
judgment.

## Stage 1 — mechanical screen

`python -c "from theories.insider_bias import screen"` — or call
`screen.screen(markets)` directly on the output of
`tools.kalshi.markets.list_open()`.

Filters, all overridable per run:

- Excluded ticker prefixes: sports, esports, multi-variate parlays. The
  thesis cannot apply where nobody can know the outcome in advance.
- Favorite price in [0.65, 0.97] at the **ask**. Below the band there is no
  favorite worth calling informed; above it there is no room left after fees.
- Spread ≤ 0.07 and volume ≥ 500. An edge inside the spread is not an edge.
- Closes within 14 days and has not already closed.

The screen deliberately produces **no probability estimate**. Nothing is
recorded to the ledger at this stage.

## Stage 2 — what needs judgment

The screen finds tradeable favorites. It cannot tell you whether anyone
actually knows the answer. That is the whole thesis, and it is judgment.

**The gating question.** Is there a specific, identifiable group of humans who
probably already know the outcome, while the public does not? Not "could
someone guess well" — *does a production crew, a board, a voting body, or a
reporter's source already know*.

Say yes for: pre-taped competition TV (finales, reunions, eliminations),
award winners after a small voting body has voted, product launches and
release dates known to supply chain and press, executive hires and firings,
M&A closings awaiting only a date, cabinet and judicial appointments,
pardons and executive orders with circulated drafts, coaching hires, and
anything resolving on a discretionary decision a small group has already made
but not announced.

Say no for: live sports and fights, any future price (stocks, crypto, FX,
commodities), weather, scheduled economic indicators computed later from data
not yet collected, live election-day outcomes, random draws, and anything
resolving on the aggregate behavior of many independent people.

**Reality TV is the strongest sub-case, and the screen cannot see it.** The
original classifier listed pre-taped competition TV as one item among twelve
equally-weighted YES examples. In practice it is not one among twelve — a
pre-taped show has a *known taping date*, a *large crew*, and an *active leak
community*, which is a far more concrete informed group than "reporters may
have sources." When a candidate is a pre-taped competition show, weight it
well above the flat prompt's treatment. This heuristic came from the user's
own trading, not from the pipeline. **If it keeps proving out in the endorsed
vs. rejected split, encode it in stage 1 as a ticker-family boost and bump the
version.**

**Do not estimate a probability.** Never answer "I think this is about 85%".
That number would be an anchor on the price you just read, not a belief.
Instead assign a **confidence bucket** from the scale below, and let
`tools/buckets.py` convert it using what that bucket has actually been worth.

**Judge blind to price.** Run the judgment on the market question and its
resolution rules *without* the price, mid, or spread in context. Reveal the
price afterwards and compute edge mechanically. Record `judged_blind=True`
when you do. The screen has already guaranteed the price is in a sane band,
so the judgment step does not need it.

**Warning signs that lower the bucket:** a vague insider story ("someone
probably knows"), resolution rules that differ from what the title implies, a
resolution source that may not publish before close, and — when you do look at
price data — momentum moving *away* from the favorite, which is informed flow
leaving.

**Recording.** Because edge depends on the bucket's measured rate, record after
judging:

```python
from tools import buckets, ledger, score
rates = score.bucket_rates(conn, "insider_bias", version)
edge, basis = buckets.edge_for(bucket, entry_price, rates, PRIORS)
opp_id, _ = ledger.record_opportunity(
    conn, ..., edge_pts_net=edge, edge_basis=basis,
    confidence=bucket, judged_blind=True,
)
ledger.interpret(conn, opp_id, "endorsed" if edge > 0 else "rejected", notes)
```

**Record the rejections too** — they are the control group that measures
whether this judgment is worth anything, and they are also what teaches the
`weak` bucket its rate. Candidates never reached within the scan budget are
reported as a count, not recorded.

## Confidence buckets

Priors are deliberately conservative and apply only until a bucket has 10+
settled results. After that the bucket's own realized win rate replaces them.

| bucket | meaning | prior edge (pts) |
|---|---|---|
| `strong` | A specific named group already knows — pre-taped show with a known taping date, a board that has voted, a signed deal awaiting announcement | 4.0 |
| `moderate` | A plausible informed group exists but is less specific — "reporters likely have sources" | 2.0 |
| `weak` | The thesis is a stretch; no concrete group identified | 0.0 |

**These priors are guesses and should be treated as placeholders.** The whole
point of the bucket mechanism is that they get replaced by measurement. If
`strong` turns out to be worth 9 points, the data will say so; if it turns out
to be worth nothing, the data will say that too — which is the outcome this
design most needs to be able to detect.

## How to backtest

**Tier B or C** — the decision path uses LLM judgment, so it is contaminated
on any market that resolved before the judging model's knowledge cutoff.

Prefer tier B: restrict replay to markets resolving after the cutoff, with
web search disabled. For tier C runs, use the contamination probe first — ask
a subagent the outcome with only the market question and no price data; if it
knows, discard that market.

The stage-1 screen alone is tier A and can be backtested over full history
using `tools/kalshi/history.py`. That measures whether the *filter* selects
markets that beat their price — useful on its own, and uncontaminated.

**This needs an adapter first — nothing built yet.**
`history.point_in_time()` returns a *candle*
(`end_ts/open/high/low/close/mean/yes_bid_close/yes_ask_close/volume/
open_interest`), but `screen.screen()` expects a *market* dict
(`ticker/is_open/mid/yes_ask/no_ask/spread/volume/close_time`). No
candle→market adapter exists. `no_ask` is not on a candle at all — derive it
as `1 - yes_bid_close` (NO ask ≈ 1 − YES bid) — and this matters here: 36 of
the 96 imported historical rows are NO-side. `tools.kalshi.markets.
list_settled()` provides a workable replay universe of "markets open on date
X". Write the adapter in this folder before attempting the backtest.

## Learnings

- 2026-08-23 — Ported from `kalshi_trader`. The reality-TV weighting is
  recorded here as a stage-2 heuristic rather than encoded, because it has not
  yet been measured against the endorsed/rejected split. Migrate it into
  stage 1 only once there is evidence.
- 2026-08-23 — The imported history's `edge_basis='prior'` rows are not "it
  felt about right" placeholders — every field on this repo's convention
  says a missing basis means that, but these rows are the exception. They
  are LLM-introspected `q` values from `kalshi_trader`'s OpenAI gpt-5
  classifier, kept because they are the only dataset that can answer whether
  introspected probabilities realize their claimed edge. See each row's
  `extra_json.model_prob_source` for the exact provenance.
