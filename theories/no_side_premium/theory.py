"""no_side_premium — pre-registered forward test of the optimism tax.

This theory is a measurement instrument first and a bet source second.
Two full-coverage tier-A backtests (mention fullcov n=3,441; insider
fullcov non-mention n=3,181) measured a side-level asymmetry — NO
favorites at or above YES favorites at equal price, YES mid-band
favorites overpriced — whose *band-specific* cells did not replicate
across populations. The pairing discipline (CLAUDE.md) says a post-hoc
pattern is a hypothesis to pre-register, never an edge to bet on the
data that suggested it. So v1 records exactly the two cells
pre-registered in idea `no-side-premium`'s revisit angle, on live
boards, and waits for settlements:

- **Cell A** (disposition=`screened`, outcome=no): mention-family
  series, NO is the favorite, no-ask >= 0.85. Claimed prior +2.0 net.
- **Cell B** (disposition=`rejected`, outcome=yes): everything else,
  YES is the favorite, yes-ask in [0.80, 0.90]. The claim is that these
  LOSE (~-3.9 net measured); a rejected row settles as a free control,
  which is precisely what an avoid-list is.

Every edge here is `edge_basis="prior"` — the originating measurement
is real but out-of-population, and nothing this theory emits is a bet
until its own forward settlements measure the cells. Scoring separates
the cells for free: `disposition='screened'` scores cell A,
`'rejected'` scores cell B.

The population is drawn by `theories.insider_bias.screen.screen()` —
deliberately imported, not copied, because the backtests that motivated
these cells drew from exactly that screen, and a forward test on a
subtly different population tests nothing. The parameter values are
pinned by a test in this folder; if the insider_bias screen ever moves,
that test fails loudly and this theory's version must decide whether to
follow.
"""

from __future__ import annotations

from tools.domain import Candidate, Edge, Fetch, ScoredCandidate, ScreenResult
from tools.theory import Theory, TheoryContext

from theories.insider_bias import screen as ib_screen
from theories.insider_bias.families import is_mention_family

#: Cell A: mention-family NO favorites at or above this ask.
CELL_A_MIN_NO_ASK = 0.85
#: Claimed prior for cell A, net points. Point estimate from the
#: originating sample's NO>=0.90 cell (+2.25) widened down because the
#: 0.85-0.90 extension carries weaker evidence.
CELL_A_PRIOR_NET = 2.0

#: Cell B: non-mention YES favorites inside this ask band.
CELL_B_BAND = (0.80, 0.90)
#: Claimed prior for cell B, net points (negative: the claim is "avoid").
#: Measured -3.89 net on the non-mention fullcov population.
CELL_B_PRIOR_NET = -3.9


def _cell(candidate: Candidate) -> str | None:
    """Which pre-registered cell a population candidate falls in."""
    leg = candidate.legs[0]
    series = leg.market.series_ticker or leg.market.ticker
    if is_mention_family(series):
        if leg.side == "no" and leg.price >= CELL_A_MIN_NO_ASK:
            return "A"
        return None
    lo, hi = CELL_B_BAND
    if leg.side == "yes" and lo <= leg.price <= hi:
        return "B"
    return None


class NoSidePremiumTheory(Theory):
    id = "no_side_premium"
    name = "No-Side Premium"
    version = 1
    uses_llm_judgment = False
    # Voluntary self-documentation: the deciding artifact is code.
    prompts = {"other": "theories/no_side_premium/theory.py"}

    def __init__(self, fetch: Fetch | None = None):
        self._fetch = fetch    # live re-quote transport; tests fake it

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        population = ib_screen.screen(ctx.board, now=ctx.now)
        cells = {"A": [], "B": []}
        for c in population:
            cell = _cell(c)
            if cell:
                cells[cell].append(c)
        cands = cells["A"] + cells["B"]
        dropped = 0
        if ctx.run_mode == "live" and cands:
            cands, dropped = self._reprice(cands, ctx)
        return ScreenResult(
            candidates=tuple(cands),
            funnel={
                "board_markets": len(ctx.board),
                "population": len(population),
                "cell_a": len(cells["A"]),
                "cell_b": len(cells["B"]),
                "recorded_at_fresh_ask": len(cands),
            },
            gate_removed=(
                {"reprice_moved_out_of_cell": dropped} if dropped else {}),
        )

    def _reprice(self, cands: list[Candidate],
                 ctx: TheoryContext) -> tuple[list[Candidate], int]:
        """Refresh entry asks so rows record the ask at scan time, not
        the board pull's. A row whose fresh ask leaves its cell is
        dropped this session — the cell definition is the
        pre-registration and does not stretch. Population filters
        (volume, spread, horizon) stay as the board screen applied them;
        they select the sample, the ask is the entry."""
        from dataclasses import replace as dc_replace

        from tools.kalshi import markets as kmarkets
        from tools.http import get_json

        fetch = self._fetch or get_json
        tickers = sorted({c.ticker for c in cands})
        fresh = {}
        for i in range(0, len(tickers), 100):
            try:
                fresh.update(kmarkets.quotes(tickers[i:i + 100],
                                             fetch=fetch))
            except Exception:
                pass   # missing tickers are dropped below
        out, dropped = [], 0
        for c in cands:
            leg = c.legs[0]
            q = fresh.get(leg.market.ticker)
            ask = None
            if q is not None and q.is_open:
                ask = q.no_ask if leg.side == "no" else q.yes_ask
            if ask is None or not 0.0 < ask < 1.0:
                dropped += 1
                continue
            candidate = Candidate(
                legs=(dc_replace(leg, price=ask,
                                 market=dc_replace(
                                     leg.market, yes_bid=q.yes_bid,
                                     yes_ask=q.yes_ask, no_bid=q.no_bid,
                                     no_ask=q.no_ask, spread=q.spread,
                                     volume=q.volume)),),
                days_to_close=c.days_to_close,
            )
            if _cell(candidate) is None:
                dropped += 1
                continue
            out.append(candidate)
        return out, dropped

    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts=None) -> list[ScoredCandidate]:
        out = []
        for c in cands:
            cell = _cell(c)
            if cell == "A":
                out.append(ScoredCandidate(
                    candidate=c,
                    edge=Edge(pts_net=CELL_A_PRIOR_NET, basis="prior"),
                    confidence="no_fav_mention_85",
                    disposition="screened",
                    rationale=(
                        "Forward-test row, cell A (pre-registered "
                        "2026-08-26): mention-family NO favorite at ask "
                        f"{c.entry_price:.2f} >= {CELL_A_MIN_NO_ASK}. "
                        "Prior +2.0 net from the originating sample's "
                        "NO>=0.90 cell (+2.25, mention fullcov n=3,441); "
                        "did not replicate on the non-mention population "
                        "(+1.04, p=0.09), hence prior, not measured. NOT "
                        "a bet until this cell's own forward settlements "
                        "measure it."),
                ))
            elif cell == "B":
                out.append(ScoredCandidate(
                    candidate=c,
                    edge=Edge(pts_net=CELL_B_PRIOR_NET, basis="prior"),
                    confidence="yes_fav_8090_avoid",
                    disposition="rejected",
                    rationale=(
                        "Forward-test row, cell B (pre-registered "
                        "2026-08-26): non-mention YES favorite at ask "
                        f"{c.entry_price:.2f} in [0.80, 0.90] — the "
                        "AVOID cell. Measured -3.89 net on the "
                        "non-mention fullcov population (n=3,181), -5.80 "
                        "in its gate-plausible slice. Recorded rejected "
                        "so settlements test the avoid claim for free."),
                ))
        return out
