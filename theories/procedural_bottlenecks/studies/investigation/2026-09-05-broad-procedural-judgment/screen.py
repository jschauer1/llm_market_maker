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


ACTION = re.compile(r'\b(approv\w*|confirm\w*|enact\w*|sign(?:ed|ing)?|veto\w*|acquir\w*|acquisition|merg\w*|launch\w*|releas\w*|resign\w*|appoint\w*|nomina\w*|impeach\w*|indict\w*|convict\w*|pardon\w*|ban(?:ned)?|legaliz\w*|ratif\w*|ceasefire|treaty|shutdown|reopen\w*|IPO|go public|file for|filing|traded|transfer\w*|drafted|coach|manager|award\w*|ballot|qualif\w*|declare\w*)\b', re.I)
NUMERIC = re.compile(r'\b(temperature|rainfall|snowfall|precipitation|wind speed|hurricane wind|earthquake magnitude|closing price|stock price|share price|market cap|exchange rate|inflation rate|unemployment rate|GDP growth|CPI|PPI|payrolls|views|streams|subscribers|downloads|box office|Rotten Tomatoes|Metacritic|Metascore|billboard|approval rating|polling average)\b', re.I)


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def mechanics(m):
    category = (m.get('event') or {}).get('category', '').lower()
    title = ' '.join(str(x or '') for x in (m.get('title'), (m.get('raw') or {}).get('subtitle'), (m.get('raw') or {}).get('yes_sub_title')))
    numeric = NUMERIC.search(title)
    if numeric:
        # Published quantities are not unfinished institutional prerequisites.
        if 'weather' in category or 'climate' in category:
            return 'weather'
        return 'numeric_measurement'
    if ACTION.search(title):
        return 'pass'
    if 'sport' in category:
        return 'live_sport'
    if 'weather' in category or 'climate' in category:
        return 'weather'
    if category in {'crypto', 'financials', 'financial markets'}:
        return 'market_price'
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
                rules_secondary=raw.get('rules_secondary'), scheduled_close=m.get('close_time'))


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
            elif label in {'live_sport', 'weather', 'market_price', 'numeric_measurement'}:
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
