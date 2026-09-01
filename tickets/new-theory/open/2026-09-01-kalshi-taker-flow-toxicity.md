---
title: Kalshi publishes per-trade taker side, and no theory here uses it: follow toxic one-sided flow
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found by reading outside literature (Stanford/Kalshi adverse-selection study) then probing Kalshi's public API for the data it implies; endpoint reachability tested live on 2026-09-01.
status: open
---
THE CAPABILITY FINDING COMES FIRST, because it is worth more than this
one thesis. **Kalshi's public trades endpoint is unauthenticated and
returns the AGGRESSOR SIDE of every trade.** The repo has no client for
it (tools/kalshi/ has markets.py, history.py, cache.py and nothing
else), and no theory reads it.

    GET https://api.elections.kalshi.com/trade-api/v2/markets/trades
    fields: ticker, created_time, count_fp, yes_price_dollars,
            no_price_dollars, taker_side, taker_outcome_side,
            taker_book_side, is_block_trade, trade_id

CLAUDE.md says "Polymarket is an equally first-class research tool -- it
exposes per-trade wallet identity and holder positions that Kalshi does
not." That is true about WALLET IDENTITY and it is easy to over-read:
Kalshi does expose per-trade direction and size, which is most of what
flow analysis needs. Nothing here requires a wallet.

VERIFIED LIVE, 2026-09-01, all four by direct call:
  - ticker filtering works; `min_ts` accepted; cursor paging works.
  - KXNFLWINS-27BAL-12: 219 trades spanning 2026-06-25..2026-09-01
    (i.e. back to market open), taker_side 137 yes / 82 no.
  - **12 of 12 ARCHIVED-SETTLED markets (close_time 2026-06-30) still
    return full trade history.** So this data survives settlement.
  - That 2026-06-25 span is 8 days OLDER than the ~60-day settled-market
    archive floor. UNTESTED AND HIGH VALUE: whether trades predate that
    floor generally. If they do, this is a route to history the repo
    currently treats as permanently lost (see collect_settled.py's
    ARCHIVE_DAYS=60 and every "perishable data" note in CLAUDE.md).
    Testing it needs a known pre-July ticker, which is awkward precisely
    because /markets no longer lists them -- try reconstructing tickers
    from a deterministic daily series (KXBTCD-style) rather than
    enumerating.

MECHANISM (the thesis). Dai/Jia/Yu-adjacent work on Kalshi -- "Adverse
Selection in Prediction Markets: Evidence from Kalshi", Stanford Law,
2026-04-21, over 41.6 MILLION trades, using adapted Kyle's lambda, a
Glosten-Harris decomposition and a VPIN-style toxicity metric -- reports
that ONE-SIDED ORDER FLOW PREDICTS MAKER LOSSES IN SINGLE-NAME MARKETS
(and NOT in broad-based ones). Maker losses are taker gains. So the
claim is: sustained one-sided aggressive flow in a single-name market
marks informed trading, and the edge is to trade WITH it, not fade it.

Who is on the other side and why they keep being wrong: the market
makers absorbing that flow, who cannot tell toxic from noise fast enough
in thin single-name books. Why it persists: the paper's own answer is a
cross-subsidy -- makers stay because behavioural flow ("traders
systematically overbet YES in markets that predominantly settle NO")
pays for the adverse selection they eat elsewhere. An equilibrium that
is profitable ON AVERAGE for makers can still be systematically
unprofitable in the toxic tail, and that tail is what this trades.

NOTE FOR no_side_premium: that same paper is an INDEPENDENT 41.6M-trade
confirmation of its thesis, arrived at from microstructure rather than
from behavioural priors. Worth citing in its THEORY.md; it is currently
resting on Becker and Reichenbach & Walther.

KALSHI POPULATION. Every traded market, which is the point -- this is a
board-wide mechanical signal, not a family screen. ~20,700 markets on
the 2026-09-01 board clear vol>=500 and spread<=0.07. Start with
single-name markets, since that is where the paper localises the effect
and it is a ticker/title-derivable property (one named entity vs an
index or aggregate).

WHAT WOULD KILL IT.
  - Flow imbalance does not predict settlement once you condition on
    PRICE. This is the primary risk and the primary confound: flow moves
    price, so a naive test rediscovers "the favourite wins more often."
    The test must be a RESIDUAL one -- does imbalance predict the
    outcome beyond what the contemporaneous price already implies? If
    not, dead.
  - The effect is real but intra-day, so it is gone by the time a
    session that runs once a day can act. Measure the horizon
    explicitly; a signal with a 20-minute half-life is not tradeable by
    this repo's operating rhythm and that is a legitimate kill.
  - It is a spread artifact: one-sided flow concentrates where books are
    thin, and thin books are the 0.980-0.995 placeholder-ask trap that
    ruined series-bias pass 3. Apply a real liquidity filter (spread AND
    open_interest), never a price cap.
  - Kalshi's `taker_side` is not the economic aggressor you think:
    CHECK THE SEMANTICS BEFORE BUILDING. `taker_side`,
    `taker_outcome_side` and `taker_book_side` are three different
    fields and the sample shows taker_book_side='ask' with
    taker_side='no'. Pin the convention with a fixture test against a
    market whose price moved in a known direction.

MECHANICAL, tier A. No model in the decision path: the signal is a
volume-weighted imbalance statistic over a trade window, the entry is a
threshold. Because trades survive settlement, it REPLAYS OVER HISTORY
FOR FREE -- which is unusually good for a microstructure thesis and is
the main reason to rank this highly.

RELATION TO EXISTING IDEAS, checked before filing:
  - idea 18 (insider-flow-radar): Polymarket WALLET-based, needs
    cross-venue matching before anything is actionable. This is
    Kalshi-native, needs no matching, and bets on the venue that
    produced the signal. Distinct, and strictly cheaper to test.
  - idea 17 (maker-mode-execution): the other side of the same coin --
    that idea COLLECTS the spread, this one pays it to trade with
    informed flow. Worth building the measurement once and reading it
    both ways; whichever sign wins tells you which idea is right.
  - idea 6 (news-drift): keys on PRICE moves. This keys on FLOW, which
    is observable before the price finishes moving. Related, testable
    on the same data, not the same signal.

TWO SPIN-OFFS worth their own tickets if this one is picked up:
  (a) `is_block_trade` is a published flag on negotiated size -- a
      whale-follow signal that needs no Polymarket wallet at all
      (compare idea 10). Zero block trades in the one market sampled, so
      measure the base rate before designing anything.
  (b) SINGLE-NAME vs BROAD-BASED is a structural, ticker-derivable
      property that the paper says predicts informed price impact. That
      is insider_judgment's central question -- "is there an informed
      group here?" -- answered by a free structural gate instead of a
      prompt. Filed separately as a ticket against that theory.

SOURCE: "Adverse Selection in Prediction Markets: Evidence from Kalshi",
Stanford Law School Legal Aggregate, 2026-04-21
(https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/);
endpoint behaviour verified by direct call, this session.
