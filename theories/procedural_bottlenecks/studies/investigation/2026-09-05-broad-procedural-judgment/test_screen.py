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
    if 'title' in changes and 'rules_primary' not in changes:
        changes['rules_primary'] = changes['title']
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
    row = market(raw={'result': 'yes', 'rules_secondary': 'Actual extra terms', 'yes_ask': 44,
                      'open_time':'2026-08-19T22:25:00Z','created_time':'2026-08-19T22:00:00Z'},
                 result='yes', event={'category': 'Politics', 'markets': [{'result': 'no'}]})
    payload = screen.blind(row)
    assert set(payload) == {'key', 'event_key', 'series', 'category', 'title', 'subtitle', 'yes_sub_title', 'no_sub_title', 'rules_primary', 'rules_secondary', 'scheduled_close','open_time','created_time'}
    assert payload['open_time']=='2026-08-19T22:25:00Z'
    assert payload['rules_secondary'] == 'Actual extra terms'
    assert 'result' not in str(payload)


def test_deadline_rungs_remain_separate():
    rows = [market(), market(ticker='KXNOVEL-26-Y', close_time='2026-11-01T00:00:00Z')]
    assert len(screen.group_events([screen.blind(row) for row in rows])[0]['markets']) == 2


def test_mentions_are_not_procedural_even_when_the_word_is_an_action():
    row = market(
        title='Will the Fed chair say approval at the press conference?',
        event={'category': 'Mentions'},
    )
    assert screen.reason(row, '2026-09-05T15:45:16Z') == 'mention'


@pytest.mark.parametrize('category,title,expected', [
    ('Economics', 'Japan Nominal GDP in 2026?', 'numeric_measurement'),
    ('Financials', 'Will Acme report Above $5 billion revenue in Q3?', 'numeric_measurement'),
    ('Companies', 'Will restaurant customer visits measured by Carbon Arc exceed 100?', 'vendor_panel_metric'),
    ('Commodities', 'Will the WTI settlement price be above $100?', 'market_price'),
    ('Entertainment', 'Will an album have above 10 million streams?', 'numeric_measurement'),
    ('Politics', 'Will a candidate report more than $25M in total receipts?', 'numeric_measurement'),
    ('Science and Technology', 'Will an AI model have a top-ranked score?', 'numeric_measurement'),
])
def test_reported_quantities_and_rankings_are_not_procedural(category, title, expected):
    assert screen.reason(
        market(title=title, event={'category': category}),
        '2026-09-05T15:45:16Z',
    ) == expected


@pytest.mark.parametrize('category,title', [
    ('Financials', 'Will the FDA approve the new treatment before October?'),
    ('Sports', 'Will Smith be traded before October?'),
    ('Economics', 'When will Acme officially announce an IPO?'),
    ('Commodities', 'Will the agency ban imports of Russian oil?'),
    ('Politics', 'Will the Philippines Senate approve the treaty?'),
])
def test_institutional_actions_survive_category_and_substring_filters(category, title):
    assert screen.reason(
        market(title=title, event={'category': category}),
        '2026-09-05T15:45:16Z',
    ) == 'pass'


def test_zero_threshold_production_proxy_is_retained_but_larger_quantity_is_not():
    first = market(
        title='Will Tesla report Above 0 Semi Trucks Produced before Jan 2027?',
        event={'category': 'Companies'},
    )
    quantity_title = 'Will Tesla report Above 1000 Semi Trucks Produced before Jan 2027?'
    quantity = dict(first, title=quantity_title, rules_primary=quantity_title)
    assert screen.reason(first, '2026-09-05T15:45:16Z') == 'pass'
    assert screen.reason(quantity, '2026-09-05T15:45:16Z') == 'numeric_measurement'


@pytest.mark.parametrize('title', [
    'Will Alabama qualify for the College Football Playoffs?',
    'Will Smith win Player of the Year?',
])
def test_sport_performance_and_awards_do_not_reach_judgment(title):
    assert screen.reason(
        market(title=title, event={'category': 'Sports'}),
        '2026-09-05T15:45:16Z',
    ) == 'live_sport'


@pytest.mark.parametrize('title,rules', [
    ('Will Losene win by Decision?', 'The bout result is complete when the official decision is released.'),
    ('Will Dalton Kincaid score a rushing touchdown?', 'The pass is complete when the scoring play ends.'),
])
def test_sports_boilerplate_action_words_do_not_override_the_subject(title, rules):
    assert screen.reason(
        market(title=title, rules_primary=rules, event={'category': 'Sports'}),
        '2026-09-05T15:45:16Z',
    ) == 'live_sport'


@pytest.mark.parametrize('category,title,expected', [
    ('Entertainment', 'Pure Album Sales for Taylor Swift this week?', 'numeric_measurement'),
    ('Science and Technology', 'What will the compute per hour price be?', 'market_price'),
])
def test_specific_quantity_subjects_are_filtered_from_the_headline(category, title, expected):
    assert screen.reason(
        market(title=title, event={'category': category}),
        '2026-09-05T15:45:16Z',
    ) == expected


def test_rule_boilerplate_does_not_turn_an_unknown_market_into_a_measurement():
    row = market(
        title='Will the board authorize the acquisition?',
        rules_primary='Shares and sales figures may be released by an official source.',
        event={'category': 'Companies'},
    )
    assert screen.reason(row, '2026-09-05T15:45:16Z') == 'pass'


def test_economics_category_is_not_an_automatic_exclusion():
    row = market(
        title='Will Harry Kane receive a knighthood?',
        event={'category': 'Economics'},
    )
    assert screen.reason(row, '2026-09-05T15:45:16Z') == 'pass'


@pytest.mark.parametrize('category,title,expected', [
    ('Entertainment', 'Will Addison Rae have a #1 hit this year?', 'numeric_measurement'),
    ('Economics', 'Will above 125000 jobs be added in October 2026?', 'numeric_measurement'),
    ('Financials', 'Will the Nasdaq-100 be between 22500 and 22999.99?', 'market_price'),
    ('Crypto', 'BTC price on Jan 1, 2027?', 'market_price'),
])
def test_explicit_rank_release_and_price_templates_are_filtered(category, title, expected):
    assert screen.reason(
        market(title=title, event={'category': category}),
        '2026-09-05T15:45:16Z',
    ) == expected


def test_revenue_passenger_wording_does_not_hide_an_institutional_resumption():
    title = (
        'Will a publicly scheduled commercial passenger flight carrying revenue '
        'passengers complete a nonstop trip between the United States and Lebanon?'
    )
    assert screen.reason(
        market(title=title, event={'category': 'Politics'}),
        '2026-09-05T15:45:16Z',
    ) == 'pass'
