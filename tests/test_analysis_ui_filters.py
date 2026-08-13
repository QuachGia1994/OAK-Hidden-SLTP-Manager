from oak_qt_shell import filter_analysis_history_deals, filter_analysis_news_items


def test_history_filter_matches_symbol_type_and_reason_without_mutating_source():
    deals = [
        {"symbol": "GBPUSD+", "deal_type": "SELL", "reason_category": "SL", "profit": 10},
        {"symbol": "GBPJPY+", "deal_type": "BUY", "reason_category": "TP", "profit": 20},
    ]
    filtered = filter_analysis_history_deals(deals, symbol="GBPUSD+", deal_type="SELL", search="sl")
    assert filtered == [deals[0]]
    assert deals == [
        {"symbol": "GBPUSD+", "deal_type": "SELL", "reason_category": "SL", "profit": 10},
        {"symbol": "GBPJPY+", "deal_type": "BUY", "reason_category": "TP", "profit": 20},
    ]


def test_news_filter_is_case_insensitive_for_currency_and_impact():
    items = [
        {"currency": "USD", "impact": "HIGH", "title": "CPI"},
        {"currency": "EUR", "impact": "LOW", "title": "Retail"},
    ]
    assert filter_analysis_news_items(items, currency="usd", impact="high") == [items[0]]
    assert filter_analysis_news_items(items, currency="All currencies", impact="LOW") == [items[1]]
