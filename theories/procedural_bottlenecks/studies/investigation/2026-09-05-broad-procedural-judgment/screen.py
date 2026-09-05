"""Broad study screen. Unknown mechanics pass; the ledger is never touched."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

from tools.atomic_write import write_json


ACTION = re.compile(
    r'\b(approv\w*|confirm\w*|enact\w*|sign(?:ed|ing)?|veto\w*|'
    r'acquir\w*|acquisition|merg\w*|launch\w*|releas\w*|resign\w*|'
    r'appoint\w*|nomina\w*|impeach\w*|indict\w*|convict\w*|charg\w*|'
    r'arrest\w*|pardon\w*|ban(?:ned)?|legaliz\w*|ratif\w*|ceasefire|'
    r'treaty|shutdown|reopen\w*|IPO|go public|take\w*.{0,30}\bpublic\b|'
    r'file for|filing|traded|transfer\w*|ballot|candidate list|declare\w*|'
    r'decision|decide\w*|complete\w*)\b',
    re.I,
)
SPORT_ACTION = re.compile(
    r'\b(trad(?:e|ed|ing)|transfer\w*|sign(?:ed|ing)? with|waiv\w*|'
    r'resign\w*|appoint\w*|hir(?:e|ed|ing)|fir(?:e|ed|ing)|approv\w*|'
    r'ban(?:ned)?|suspend\w*)\b',
    re.I,
)
VENDOR_PANEL = re.compile(r'\bCarbon Arc\b', re.I)
FIRST_COMPLETION = re.compile(
    r'\breport\w*\s+(?:that\s+)?(?:above|more than|at least)\s+'
    r'\$?0(?:\.0+)?\b.{0,100}\b(produc\w*|manufactur\w*|deliver\w*|'
    r'launch\w*|ship(?:ped|ment\w*)?)\b',
    re.I,
)
MARKET_PRICE = re.compile(
    r'\b(?:closing|close|settlement|settle|spot|ticket|get-in|stock|share|'
    r'gas|oil|gold|silver|copper|commodity|bitcoin|crypto)\s+price\b|'
    r'\bprice of\b|\bmarket cap(?:italization)?\b|\bexchange rate\b|'
    r'\bnet worth\b|\btreasury yield\b|\bcompute per hour price\b|'
    r'\bBTC price\b|\b(?:Nasdaq-?100|S&P 500|Dow Jones|Russell 2000)\b'
    r'.{0,80}\b(?:above|below|between|at|end)\b',
    re.I,
)
NUMERIC = re.compile(
    r'\b(temperature|rainfall|snowfall|precipitation|wind speed|'
    r'hurricane wind|earthquake magnitude|nominal GDP|real GDP|GDP growth|'
    r'consumer price index|producer price index|CPI|PPI|payrolls?|'
    r'jobs? (?:be )?(?:added|lost)|employment (?:change|growth|level|rate)|'
    r'unemployment|inflation|interest rate|federal funds rate|revenue growth|'
    r'sales growth|pure album sales|receipts|total fundraising|headcount|'
    r'(?:customer|user|transaction) count|active users?|transaction volume|'
    r'number of trips|ridership|trading volume|(?:profit|operating) margin|market share|'
    r'views?|streams?|subscribers?|downloads?|album equivalent units|'
    r'box office|Rotten Tomatoes|Metacritic|Metascore|Billboard|'
    r'approval rating|polling average|data centers?|disease cases?|'
    r'case count|number of|how many|seats|margin of victory|vote share|'
    r'top[- ]ranked|top \d+|rank(?:ed|ing)?|score|win\w*.{0,30}\baward)\b|'
    r'#\d+\b|'
    r'\breport\w*\s+(?:that\s+)?(?:above|below|over|under|more than|'
    r'less than|at least|at most)\s+[$+\-]?\d',
    re.I,
)


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def mechanics(m):
    category = (m.get('event') or {}).get('category', '').lower()
    raw = m.get('raw') or {}
    headline = ' '.join(str(x or '') for x in (
        m.get('title'), raw.get('subtitle'), raw.get('yes_sub_title'),
        raw.get('no_sub_title'),
    ))
    rules = ' '.join(str(x or '') for x in (
        m.get('rules_primary'), raw.get('rules_secondary'),
    ))
    if category == 'mentions':
        return 'mention'
    if VENDOR_PANEL.search(headline) or VENDOR_PANEL.search(rules):
        return 'vendor_panel_metric'
    if FIRST_COMPLETION.search(headline):
        # A threshold of zero can encode whether production or delivery
        # happened at all. The judge should read that ambiguous action.
        return 'pass'
    if MARKET_PRICE.search(headline):
        return 'market_price'
    if NUMERIC.search(headline):
        if 'sport' in category:
            return 'live_sport'
        if 'weather' in category or 'climate' in category:
            return 'weather'
        return 'numeric_measurement'
    if 'sport' in category:
        if SPORT_ACTION.search(headline):
            return 'pass'
        return 'live_sport'
    if 'weather' in category or 'climate' in category:
        if ACTION.search(headline):
            return 'pass'
        return 'weather'
    if ACTION.search(headline):
        return 'pass'
    return 'pass'


def reason(m, at):
    if not m.get('is_open'):
        return 'closed'
    prices = (m.get('yes_ask'), m.get('no_ask'))
    if any(p is None or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 < p < 1 for p in prices):
        return 'invalid_quotes'
    spread = sum(prices) - 1
    if spread < -1e-8 or spread > .12 + 1e-8:
        return 'spread'
    oi = m.get('open_interest')
    if oi is None or not math.isfinite(oi) or oi < 100:
        return 'open_interest'
    try:
        hours = (instant(m['close_time']) - instant(at)).total_seconds() / 3600
    except (KeyError, ValueError, TypeError):
        return 'missing_close'
    if not 6 <= hours <= 365 * 24:
        return 'horizon'
    return mechanics(m)


def blind(m):
    raw = m.get('raw') or {}
    return dict(key=m['ticker'], event_key=m.get('event_ticker') or m['ticker'],
                series=m.get('series_ticker') or m['ticker'].split('-')[0],
                category=(m.get('event') or {}).get('category'), title=m.get('title'),
                subtitle=raw.get('subtitle'), yes_sub_title=raw.get('yes_sub_title'),
                no_sub_title=raw.get('no_sub_title'), rules_primary=m.get('rules_primary'),
                rules_secondary=raw.get('rules_secondary'), scheduled_close=m.get('close_time'),
                open_time=raw.get('open_time') or m.get('open_time'),
                created_time=raw.get('created_time') or m.get('created_time'))


def stable_key(value):
    return hashlib.sha256(value.encode()).hexdigest()


def group_events(rows):
    events = defaultdict(list)
    for row in rows:
        events[row['event_key']].append(row)
    return [dict(event_key=k, markets=sorted(events[k], key=lambda r:r['key']))
            for k in sorted(events, key=stable_key)]


def run(board_path, at, out):
    counts, categories, survivors = Counter(), defaultdict(Counter), []
    audit = defaultdict(list)
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'screen-decisions.jsonl').open('x', encoding='utf-8') as decisions:
        for line in board_path.open(encoding='utf-8'):
            m = json.loads(line)
            label = reason(m, at)
            counts[label] += 1
            category = (m.get('event') or {}).get('category') or 'unknown'
            categories[category][label] += 1
            decisions.write(json.dumps(dict(key=m['ticker'], reason=label, category=category))+'\n')
            if label == 'pass':
                survivors.append(blind(m))
            elif label in {
                'live_sport', 'weather', 'market_price', 'numeric_measurement',
                'mention', 'vendor_panel_metric',
            }:
                audit[label].append(blind(m))
    events = group_events(survivors)
    for label in audit:
        audit[label] = sorted(audit[label], key=lambda r: stable_key(r['key']))[:10]
    write_json(out / 'survivors-blind.json', dict(as_of=at, events=events))
    write_json(out / 'gate-audit-blind.json', audit)
    summary = dict(board_markets=sum(counts.values()), counts=counts,
                   surviving_events=len(events), surviving_markets=len(survivors),
                   surviving_series=len({r['series'] for r in survivors}),
                   categories=categories, snapshot_at=at)
    write_json(out / 'census.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--board', type=Path, required=True)
    p.add_argument('--at', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    run(args.board, args.at, args.out)
