from agents.mentions.providers.kalshi.sourcing import build_candidate_market_pool


def test_candidate_pool_uses_series_hints(monkeypatch):
    calls = []

    def fake_get_markets_bundle(category='', limit=20, status='open'):
        calls.append(category)
        if category == 'KXTRUMPMENTIONB':
            return {'markets': [{'ticker': 'KXTRUMPMENTION-IRAN', 'title': 'Will Trump mention Iran?'}]}
        return {'markets': []}

    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.get_markets_bundle',
        fake_get_markets_bundle,
    )
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.search_markets_bundle',
        lambda query, limit=10: {'markets': []},
    )

    pool = build_candidate_market_pool('Will Trump mention Iran?')
    assert 'KXTRUMPMENTIONB' in calls
    assert pool['markets'][0]['ticker'] == 'KXTRUMPMENTION-IRAN'
    assert any(item.startswith('series:') for item in pool['diagnostics'])


def test_candidate_pool_expands_series_when_topic_missing_initially(monkeypatch):
    calls = []

    def fake_get_markets_bundle(category='', limit=20, status='open', event_ticker=''):
        calls.append((category, limit, event_ticker))
        if category == 'KXTRUMPMENTION' and limit < 100:
            return {'markets': [{'ticker': 'KXTRUMPMENTION-NATO', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'NATO'}]}
        if category == 'KXTRUMPMENTION' and limit >= 100:
            return {'markets': [{'ticker': 'KXTRUMPMENTION-IRAN', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'Iran'}]}
        return {'markets': []}

    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.get_markets_bundle',
        fake_get_markets_bundle,
    )
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.search_markets_bundle',
        lambda query, limit=10: {'markets': []},
    )

    pool = build_candidate_market_pool('Will Trump mention Iran?')
    assert pool['markets'][0]['ticker'] == 'KXTRUMPMENTION-IRAN'
    assert 'series-expand:KXTRUMPMENTION' in pool['diagnostics']


def test_candidate_pool_falls_back_to_search(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.get_markets_bundle',
        lambda **kwargs: {'markets': []},
    )
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.search_markets_bundle',
        lambda query, limit=10: {'markets': [{'ticker': 'KXTEST', 'title': query}] if query == 'Will Trump mention Iran?' else []},
    )

    pool = build_candidate_market_pool('Will Trump mention Iran?')
    assert pool['markets'][0]['ticker'] == 'KXTEST'
    assert 'fallback-search' in pool['diagnostics']


def test_candidate_pool_filters_to_topic_and_mention_series(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.get_markets_bundle',
        lambda **kwargs: {
            'markets': [
                {'ticker': 'KXTRUMPMENTION-IRAN', 'title': 'What will Donald Trump say about Iran?', 'yes_sub_title': 'Iran'},
                {'ticker': 'KXTRUMPMENTION-NATO', 'title': 'What will Donald Trump say about NATO?', 'yes_sub_title': 'NATO'},
                {'ticker': 'KXTSAW-26APR21-A2.80', 'title': 'Will more than 2800000 people be screened by the TSA on average this week?'},
            ]
        },
    )
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.search_markets_bundle',
        lambda query, limit=10: {'markets': []},
    )

    pool = build_candidate_market_pool('Will Trump mention Iran?')
    tickers = [m['ticker'] for m in pool['markets']]
    assert tickers == ['KXTRUMPMENTION-IRAN']
    assert 'filter:mention-series-priority' in pool['diagnostics']
    assert any(item in pool['diagnostics'] for item in ('filter:exact-topic-label', 'filter:topic-match'))


def test_candidate_pool_topic_aliases_iran_not_israel(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.get_markets_bundle',
        lambda **kwargs: {
            'markets': [
                {'ticker': 'KXTRUMPMENTION-26APR15-IRAN', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'Iran'},
                {'ticker': 'KXTRUMPMENTION-26APR15-ISRA', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'Israel / Israeli'},
                {'ticker': 'KXTRUMPMENTION-26APR15-URAN', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'Uranium'},
            ]
        },
    )
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.search_markets_bundle',
        lambda query, limit=10: {'markets': []},
    )

    pool = build_candidate_market_pool('Will Trump mention Iran?')
    tickers = [m['ticker'] for m in pool['markets']]
    assert tickers == ['KXTRUMPMENTION-26APR15-IRAN']


def test_candidate_pool_can_expand_event_markets(monkeypatch):
    def fake_search(query, limit=10):
        if query == 'TRUMPMENTION':
            return {'markets': [{'ticker': 'KXTRUMPMENTION-26APR15-NATO', 'event_ticker': 'KXTRUMPMENTION-26APR15', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'NATO'}]}
        return {'markets': []}

    def fake_get_markets_bundle(category='', limit=20, status='open', event_ticker=''):
        if event_ticker == 'KXTRUMPMENTION-26APR15':
            return {
                'markets': [
                    {'ticker': 'KXTRUMPMENTION-26APR15-IRAN', 'event_ticker': event_ticker, 'title': 'What will Donald Trump say?', 'yes_sub_title': 'Iran'},
                    {'ticker': 'KXTRUMPMENTION-26APR15-NATO', 'event_ticker': event_ticker, 'title': 'What will Donald Trump say?', 'yes_sub_title': 'NATO'},
                ]
            }
        return {'markets': []}

    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.search_markets_bundle',
        fake_search,
    )
    monkeypatch.setattr(
        'agents.mentions.providers.kalshi.sourcing.get_markets_bundle',
        fake_get_markets_bundle,
    )

    pool = build_candidate_market_pool('Will Trump mention Iran?')
    tickers = [m['ticker'] for m in pool['markets']]
    assert 'KXTRUMPMENTION-26APR15-IRAN' in tickers
    assert any(item.startswith('event-expand:') for item in pool['diagnostics'])
