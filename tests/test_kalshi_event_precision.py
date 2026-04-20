from agents.mentions.providers.kalshi.sourcing import build_candidate_market_pool


def test_event_expansion_ignores_irrelevant_nonmention_seeds(monkeypatch):
    def fake_search(query, limit=10):
        if query == 'TRUMPMENTION':
            return {
                'markets': [
                    {'ticker': 'KXTSAW-26APR21-A2.80', 'event_ticker': 'KXTSAW-26APR21', 'title': 'Will more than 2800000 people be screened by the TSA on average this week?'},
                    {'ticker': 'KXTRUMPMENTION-26APR15-NATO', 'event_ticker': 'KXTRUMPMENTION-26APR15', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'NATO'},
                ]
            }
        return {'markets': []}

    seen_event_tickers = []

    def fake_get_markets_bundle(category='', limit=20, status='open', event_ticker=''):
        if event_ticker:
            seen_event_tickers.append(event_ticker)
        return {'markets': []}

    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.search_markets_bundle',
        fake_search,
    )
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.get_markets_bundle',
        fake_get_markets_bundle,
    )

    build_candidate_market_pool('Will Trump mention Iran?')
    assert 'KXTRUMPMENTION-26APR15' in seen_event_tickers
    assert 'KXTSAW-26APR21' not in seen_event_tickers
