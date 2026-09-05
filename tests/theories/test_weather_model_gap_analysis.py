from datetime import date, timedelta


def rows(days=40, cities=3):
    return [{"ticker": f"S{city}-{day}", "event_ticker": f"S{city}-{day}",
             "series_ticker": f"S{city}", "target_date": str(date(2026, 7, 1) + timedelta(days=day)),
             "settlement_day": str(date(2026, 7, 2) + timedelta(days=day)),
             "side": "yes", "result": "yes", "entry_price": .5}
            for day in range(days) for city in range(cities)]


def test_three_cities_do_not_turn_ten_weather_days_into_thirty():
    from theories.weather_model_gap.analysis import summarize
    result = summarize(rows(days=10))
    assert result["n"] == 30
    assert result["day"]["clusters"] == 10
    assert result["supported"] is False


def test_pending_weather_bets_stay_in_denominator_and_block_support():
    from theories.weather_model_gap.analysis import summarize
    bets = rows(cities=1)
    bets[-1]["result"] = None
    result = summarize(bets, city=True)
    assert result["n"] == 39
    assert result["total_n"] == 40
    assert result["pending_n"] == 1
    assert result["supported"] is False
    assert result["pending_best_case_net_pts"] > result["pending_worst_case_net_pts"]


def test_city_can_earn_support_without_a_positive_parent():
    from theories.weather_model_gap.analysis import summarize
    bets = rows(cities=1)
    assert summarize(bets, city=True)["supported"] is True
    losses = [dict(r, event_ticker=r["event_ticker"] + "L", result="no") for r in bets]
    assert summarize(bets + losses)["supported"] is False
