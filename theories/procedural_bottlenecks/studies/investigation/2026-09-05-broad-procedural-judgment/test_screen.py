import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('broad_screen', Path(__file__).with_name('screen.py'))
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


def market(**changes):
    row = dict(ticker='KXNOVEL-26-X', event_ticker='KXNOVEL-26', title='Will a new product launch?',
               is_open=True, yes_ask=.44, no_ask=.60, open_interest=300,
               close_time='2026-10-01T00:00:00Z', rules_primary='If the product launches before October, Yes.',
               raw={}, event={'category': 'Science and Technology'})
    return dict(row, **changes)


def test_unknown_institutional_family_passes_without_allowlist():
    assert screen.reason(market(), '2026-09-05T15:45:16Z') == 'pass'


@pytest.mark.parametrize('category,title,expected', [
    ('Sports', 'Will Arsenal win the next match?', 'live_sport'),
    ('Sports', 'Will Smith be traded before October?', 'pass'),
    ('Climate and Weather', 'Highest temperature in New York tomorrow?', 'weather'),
    ('Crypto', 'Will Bitcoin price be above $100,000?', 'market_price'),
    ('Crypto', 'Will the SEC approve the new token ETF?', 'pass'),
    ('Politics', 'Will the senate confirm the nominee?', 'pass'),
    ('Entertainment', 'Will GTA 6 release this year?', 'pass'),
])
def test_mechanics_preserve_actions_inside_other_categories(category, title, expected):
    assert screen.reason(market(title=title, event={'category': category}), '2026-09-05T15:45:16Z') == expected


def test_symmetric_quotes_and_missingness():
    base = market(yes_ask=.96, no_ask=.07)
    assert screen.reason(base, '2026-09-05T15:45:16Z') == 'pass'
    assert screen.reason(dict(base, yes_ask=.07, no_ask=.96), '2026-09-05T15:45:16Z') == 'pass'
    assert screen.reason(dict(base, no_ask=None), '2026-09-05T15:45:16Z') == 'invalid_quotes'
    assert screen.reason(dict(base, no_ask=.30), '2026-09-05T15:45:16Z') == 'spread'


def test_blind_whitelist_strips_nested_prices_and_outcomes():
    row = market(raw={'result': 'yes', 'rules_secondary': 'Actual extra terms', 'yes_ask': 44},
                 result='yes', event={'category': 'Politics', 'markets': [{'result': 'no'}]})
    payload = screen.blind(row)
    assert set(payload) == {'key', 'event_key', 'series', 'category', 'title', 'subtitle', 'yes_sub_title', 'no_sub_title', 'rules_primary', 'rules_secondary', 'scheduled_close'}
    assert payload['rules_secondary'] == 'Actual extra terms'
    assert 'result' not in str(payload)


def test_deadline_rungs_remain_separate():
    rows = [market(), market(ticker='KXNOVEL-26-Y', close_time='2026-11-01T00:00:00Z')]
    assert len(screen.group_events([screen.blind(row) for row in rows])[0]['markets']) == 2
