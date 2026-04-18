from agents.mentions.modules.market_resolution import resolve_market_from_query


def test_market_resolution_prefers_relevant_trump_mention_market():
    results = [
        {'ticker': 'KXTSAW-26APR21-A2.80', 'title': 'Will more than 2800000 people be screened by the TSA on average this week?', 'volume': 5000},
        {'ticker': 'KXTRUMPMENTION-IRAN', 'title': 'Will Trump mention Iran in a speech this week?', 'volume': 12000, 'yes_sub_title': 'Iran', 'event_ticker': 'KXTRUMPMENTION-26APR15'},
        {'ticker': 'KXQUICKSETTLE-15APR26H1430-2', 'title': '1+1 = 2', 'volume': 4000},
    ]
    resolved = resolve_market_from_query('Will Trump mention Iran in a speech?', results)
    assert resolved.ticker == 'KXTRUMPMENTION-IRAN'
    assert resolved.confidence in {'medium', 'high'}
    assert resolved.candidates[0].ticker == 'KXTRUMPMENTION-IRAN'
    assert resolved.meta['score_margin'] >= 0
