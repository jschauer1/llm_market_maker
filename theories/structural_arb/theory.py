"""Contract adapter for the fully mechanical structural-arb scanner.

`scan.py` decides; this module fetches. Since v4 only one fetch path
remains, and it is bounded:

- the event envelope's ``mutually_exclusive`` flag is **not fetched at
  all** any more. `list_open` used to pull Kalshi's event envelope on
  every board walk and discard it, so this theory re-fetched the flag one
  event at a time under a per-screen budget, spent on the largest
  violations first. The envelope has ridden on every market since
  2026-08-29 (tools ``09a66f7``), so the guard is free *and* complete:
  every candidate is checked, where the budget could only afford the 150
  largest. ``theory_facts`` still holds the 2,042 flags bought the old
  way and is read as the fallback for envelope-less snapshots; nothing
  writes new ones.
- fresh quotes for every leg of every finding, live runs only, batched
  ``QUOTE_CHUNK`` tickers per request (one request for thousands of
  tickers 414s). The board can be an hour old; the first live run proved
  every single board-priced "violation" (177 of them, mostly in-play
  sports with degenerate 1-cent books) evaporates at fresh quotes — a
  violation that cannot be re-verified is not recorded, full stop.

`run_mode == "backtest"` never re-quotes: a replay prices the snapshot,
and its output measures violation *existence* at snapshot time, not
fillability.

Every find is riskless net of (unrounded) fees when recorded:
`min_payout` covers cost + fees, so scoring routes it to the riskless
bucket (`riskless_n` / `riskless_roi`) and no calibration claim is ever
made. `edge_pts_net` is the guaranteed return on cost in percentage
points — the honest common currency for a position with no win rate.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace

from tools.domain import Candidate, Edge, Fetch, ScoredCandidate, ScreenResult
from tools.theory import Theory, TheoryContext

from theories.structural_arb import scan

EVENT_URL = "https://api.elections.kalshi.com/trade-api/v2/events/{}"

#: Tickers per quotes request. 3,438 in one GET returned HTTP 414.
QUOTE_CHUNK = 100

ORDERBOOK_URL = ("https://api.elections.kalshi.com/trade-api/v2"
                 "/markets/{}/orderbook")

#: Orderbook lookups per pricing pass, one per distinct finalist leg.
#: Finalists are a handful per board (v1 live evidence: 1-3 findings),
#: so this cap only guards a pathological board; capped-out legs record
#: as depth-UNVERIFIED, never silently.
MAX_ORDERBOOK_FETCHES = 20

#: A basket whose fillable riskless profit is below this is dust: real
#: at top-of-book, not actionable at any size worth the user's time.
#: Both v1 live finds died here (opp 9248: ~$0.30 fillable, opp 9309:
#: ~$0.02) — v2 makes the check mechanical and records such finds as
#: rejected, keeping the free control group.
MIN_FILLABLE_PROFIT_USD = 5.0

#: v3 stage-1 sterile-class screens. The 2026-08-29 snapshot study
#: (studies/2026-08-29-structural-arb-violation-liquidity/) replayed this
#: theory's geometry over 11 stored boards and found six violations in
#: five days, EVERY ONE of which the depth gate then rejected. They fall
#: into three classes identifiable from the board alone, so screening
#: them here stops the scan reporting finds it will always reject — and
#: stops it spending a rate-limited orderbook fetch per leg to discover
#: what the volume field already said.
#:
#: A violation whose thinner leg has never traded this much is either a
#: market maker's untested opening mark (study class 1: lifetime volume
#: 0.0–0.1, each seen in exactly one snapshot) or a frozen thin ladder
#: (class 2: KXNCAAMBWINS sat in 8 of 11 snapshots at unchanged prices on
#: 6- and 40-contract legs, worth $0.02 fillable).
MIN_LEG_VOLUME = 100.0

#: Class 3: long-dated ladders. USCLIMATE 2025/2030 was genuinely liquid
#: (11,596 contracts) and genuinely persistent, and paid 1.5%/yr over 4.3
#: years — a riskless return below cash is not an opportunity, and it is
#: the same conclusion the calendar-arb study reached independently.
#: 5%/yr is a deliberately loose cash floor: the point is to drop the
#: multi-year ladders, not to tune a hurdle rate.
MIN_ANNUALISED_RETURN = 0.05

#: Below this horizon the annualised figure is noise (a 15-day basket
#: annualises to four digits), so the return floor simply does not apply.
ANNUALISE_MIN_DAYS = 30.0

FACT_KIND = "event_me_flag"

#: Process-lifetime cache: event_ticker -> bool | None (None: fetch failed).
_flag_cache: dict[str, bool | None] = {}


def _me_flag_cached(conn, event_ticker: str) -> bool | None:
    """Session cache, then theory_facts. Raises KeyError when the flag
    is known nowhere — the caller decides whether budget allows a fetch
    (None is taken: it means 'fetch failed this session')."""
    if event_ticker in _flag_cache:
        return _flag_cache[event_ticker]
    if conn is not None:
        row = conn.execute(
            "SELECT value_json FROM theory_facts WHERE theory_id = ?"
            " AND kind = ? AND key = ?",
            (StructuralArbTheory.id, FACT_KIND, event_ticker),
        ).fetchone()
        if row is not None:
            flag = row["value_json"] == "true"
            _flag_cache[event_ticker] = flag
            return flag
    raise KeyError(event_ticker)


def _me_flag(conn, finding) -> bool | None:
    """Is this finding's event mutually exclusive? True / False / unknown.

    Reads Kalshi's own event envelope off the board -- `list_open` has
    carried it since 2026-08-29 (tools `09a66f7`), where before it fetched
    the envelope and threw it away.

    **Tri-state on purpose.** `{}` means no envelope was captured, which
    is emphatically not the same as an envelope saying False. The caller
    excludes a candidate on False and None alike — only True confirms —
    so the distinction never changes a decision; it changes the *record*.
    Reading absence as False would make a replay over a pre-2026-08-29
    snapshot report every candidate as "venue says not exclusive" when
    the venue said nothing, re-manufacturing the all-false illusion that
    nearly got this path cut (NOTES 2026-08-29). Unknown falls back to
    `theory_facts`, which still holds the 2,042 flags this theory paid for
    one fetch at a time, and is reported as `flag_unknown` if that misses
    too.

    No network path remains. There is nothing left to ration, which is
    why the caller checks every candidate rather than the 150 largest.
    """
    envelope = finding.legs[0].market.event or {}
    flag = envelope.get("mutually_exclusive")
    if flag is not None:
        return bool(flag)
    try:
        return _me_flag_cached(conn, finding.event_ticker)
    except KeyError:
        return None


def _drop_sterile(findings: list[scan.Finding], now=None,
                  ) -> tuple[list[scan.Finding], dict[str, int]]:
    """Remove the violation classes that are never actionable.

    Returns `(kept, removed_by_category)`. The categories are reported,
    never silently dropped — a gate that drops without saying what it
    dropped lets a scan claim coverage it never had (CLAUDE.md).

    Deliberately NOT a liquidity *proxy* for the depth gate: lifetime
    volume and fillable size are different questions, and the study's one
    genuinely interesting find (KXNASDAQ100MINY, 3,918 contracts) had
    plenty of the former and none of the latter. This only removes
    findings that lifetime volume alone already proves sterile; the
    orderbook walk still decides everything else.
    """
    kept: list[scan.Finding] = []
    removed: dict[str, int] = {}
    for f in findings:
        volumes = [leg.market.volume or 0.0 for leg in f.legs]
        if min(volumes, default=0.0) < MIN_LEG_VOLUME:
            removed["untraded or near-untraded leg"] = (
                removed.get("untraded or near-untraded leg", 0) + 1)
            continue
        days = [d for leg in f.legs
                if (d := scan.days_until(leg.market.close_time,
                                         now=now)) is not None]
        horizon = max(days) if days else 0.0
        if horizon >= ANNUALISE_MIN_DAYS and f.cost > 0:
            per_year = (f.profit_floor / f.cost) / (horizon / 365.25)
            if per_year < MIN_ANNUALISED_RETURN:
                removed["return below the cash floor"] = (
                    removed.get("return below the cash floor", 0) + 1)
                continue
        kept.append(f)
    return kept, removed


class StructuralArbTheory(Theory):
    id = "structural_arb"
    name = "Structural Arb"
    # v2: live pricing reads the orderbook for every finalist leg and
    # rejects baskets whose fillable riskless profit is dust (< $5).
    # v3: stage 1 drops the three sterile violation classes the
    # 2026-08-29 snapshot study measured -- untraded legs, frozen thin
    # ladders, and long-dated ladders below a cash floor -- before the
    # orderbook fetch, so the scan stops reporting finds it will always
    # reject. See MIN_LEG_VOLUME / MIN_ANNUALISED_RETURN above.
    # v4: the mutual-exclusivity guard reads Kalshi's event envelope
    # off the board instead of fetching it per event, so it costs
    # nothing and checks EVERY candidate rather than the 150 largest.
    version = 4
    uses_llm_judgment = False
    # Voluntary self-documentation: the deciding artifact is code.
    # finish() records it with model='none (deterministic)'.
    prompts = {"other": "theories/structural_arb/scan.py"}

    def __init__(self, fetch: Fetch | None = None):
        # Configuration, not per-run state: the transport used for flag
        # lookups and live re-quotes. None resolves to the default HTTP
        # client at call time, so tests can hand in a canned payload.
        self._fetch = fetch

    # ---- stage 1: the whole theory ----

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        from tools.http import get_json
        fetch = self._fetch or get_json

        events = scan.group_by_event(ctx.board)
        out = scan.scan_events(events)
        funnel = {"board_markets": len(ctx.board), **out.funnel}
        gate_removed: dict[str, int] = {}
        findings = list(out.findings)

        # Confirm the ME flag for arithmetic hits geometry couldn't prove.
        #
        # v4: read straight off the board. `list_open` used to fetch
        # Kalshi's event envelope and discard it, so this cost one network
        # call per event and had to ration itself to the 150 largest
        # candidates. The envelope is now on every market, so the guard is
        # free AND complete -- every candidate is checked, not a budgeted
        # slice. No ordering by profit is needed for the same reason.
        confirmed = 0
        for f in out.flag_candidates:
            flag = _me_flag(ctx.conn, f)
            if flag is True:
                findings.append(f)
                confirmed += 1
            elif flag is False:
                gate_removed["not_mutually_exclusive"] = (
                    gate_removed.get("not_mutually_exclusive", 0) + 1)
            else:
                gate_removed["flag_unknown"] = (
                    gate_removed.get("flag_unknown", 0) + 1)
        funnel["flag_confirmed"] = confirmed

        # v3: drop the three sterile classes before anything expensive.
        findings, sterile = _drop_sterile(findings, now=ctx.now)
        for label, n in sterile.items():
            gate_removed[label] = gate_removed.get(label, 0) + n

        # Live runs re-quote every leg and re-decide on fresh asks.
        if ctx.run_mode == "live" and findings:
            findings, removed = self._reverify(findings, fetch)
            gate_removed.update(removed)
        funnel["survivors"] = len(findings)

        cands = []
        for f in sorted(findings, key=lambda x: x.profit_floor,
                        reverse=True):
            days = [d for leg in f.legs
                    if (d := scan.days_until(leg.market.close_time,
                                             now=ctx.now)) is not None]
            cands.append(Candidate(
                legs=f.legs,
                # A basket resolves when its LAST leg does; capital is
                # locked until then.
                days_to_close=max(days) if days else 0.0,
                max_payout=f.max_payout,
                min_payout=f.min_payout,
            ))
        return ScreenResult(candidates=tuple(cands), funnel=funnel,
                            gate_removed=gate_removed)

    def _reverify(self, findings: list[scan.Finding], fetch: Fetch,
                  ) -> tuple[list[scan.Finding], dict[str, int]]:
        """Fresh-quote every finding's legs (batched) and re-decide each
        finding with `scan.refresh_finding` — the same arithmetic that
        found it. Fresh quotes are patched onto the board market so the
        strike raw fields survive into the recorded legs."""
        from tools.kalshi import markets as kmarkets

        by_ticker = {leg.market.ticker: leg.market
                     for f in findings for leg in f.legs}
        tickers = sorted(by_ticker)
        fresh: dict[str, object] = {}
        fetch_failed = False
        for i in range(0, len(tickers), QUOTE_CHUNK):
            chunk = tickers[i:i + QUOTE_CHUNK]
            try:
                fresh.update(kmarkets.quotes(chunk, fetch=fetch))
            except Exception:
                fetch_failed = True   # affected legs simply stay missing
        patched = {}
        for t, q in fresh.items():
            base = by_ticker.get(t)
            if base is None:
                continue
            patched[t] = dc_replace(
                base, yes_bid=q.yes_bid, yes_ask=q.yes_ask,
                no_bid=q.no_bid, no_ask=q.no_ask, mid=q.mid,
                spread=q.spread, volume=q.volume, status=q.status,
                is_open=q.is_open)
        survivors = []
        removed: dict[str, int] = {}
        for f in findings:
            nf = scan.refresh_finding(f, patched)
            if nf is not None:
                survivors.append(nf)
            elif fetch_failed and any(leg.market.ticker not in patched
                                      for leg in f.legs):
                removed["reverify_fetch_failed"] = (
                    removed.get("reverify_fetch_failed", 0) + 1)
            else:
                removed["stale_quote"] = removed.get("stale_quote", 0) + 1
        return survivors, removed

    # ---- pricing: arithmetic on the candidate itself ----

    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts=None) -> list[ScoredCandidate]:
        from tools.http import get_json
        fetch = self._fetch or get_json

        out = []
        books: dict[str, dict | None] = {}   # ticker -> fp (None: failed)
        budget = [MAX_ORDERBOOK_FETCHES]
        for c in cands:
            cost = c.cost
            fee = sum(scan._fee(leg.price) for leg in c.legs)
            profit = c.min_payout - cost - fee
            if profit <= 0:
                continue  # screen() filtered; belt and braces
            finding = scan.Finding(
                kind=("nested_pair" if len(c.legs) == 2
                      and {leg.side for leg in c.legs} == {"yes", "no"}
                      else "no_basket"),
                event_ticker=c.legs[0].market.event_ticker or "",
                legs=c.legs, min_payout=c.min_payout,
                max_payout=c.max_payout,
            )
            disposition = "screened"
            if ctx.run_mode == "live":
                # Backtests price the snapshot; only a live run can ask
                # the book how much of the floor is actually fillable.
                disposition, note = self._depth_verdict(
                    finding, fetch, books, budget)
                finding = dc_replace(finding, note=note)
            out.append(ScoredCandidate(
                candidate=c,
                edge=Edge(
                    pts_net=100.0 * profit / (cost + fee),
                    basis="model",
                    pts_gross=100.0 * (c.min_payout - cost) / cost,
                    fee_pts=100.0 * fee,
                ),
                rationale=scan.describe(finding),
                disposition=disposition,
            ))
        return out

    def _depth_verdict(self, finding: scan.Finding, fetch: Fetch,
                       books: dict[str, dict | None],
                       budget: list[int]) -> tuple[str, str]:
        """(disposition, note) from the legs' orderbooks.

        A leg whose book cannot be read (fetch failed, or budget spent)
        leaves the finding screened but explicitly UNVERIFIED — the v1
        behavior, never silently. A readable book either clears the
        actionability floor or records the finding as rejected, which
        keeps the dust finds as a settled control group.
        """
        ladders = []
        for leg in finding.legs:
            ticker = leg.market.ticker
            if ticker not in books:
                if budget[0] <= 0:
                    books[ticker] = None
                else:
                    budget[0] -= 1
                    try:
                        payload = fetch(ORDERBOOK_URL.format(ticker))
                        books[ticker] = payload.get("orderbook_fp") or {}
                    except Exception:
                        books[ticker] = None
            fp = books[ticker]
            if fp is None:
                return "screened", (
                    "Depth UNVERIFIED (orderbook unavailable this run):"
                    " top-of-book existence only — check fillable size"
                    " before entering")
            ladders.append(scan.implied_ask_ladder(fp, leg.side))
        baskets, dollars = scan.fillable_floor(ladders, finding.min_payout)
        note = (f"Depth: ~{baskets:.2f} baskets fillable at riskless"
                f" prices, ~${dollars:.2f} floor profit")
        if dollars < MIN_FILLABLE_PROFIT_USD:
            return "rejected", note + (
                f" — below the ${MIN_FILLABLE_PROFIT_USD:.0f}"
                " actionability floor (depth gate)")
        return "screened", note
