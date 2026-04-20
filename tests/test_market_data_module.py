from agents.mentions.modules.market_data.builder import build_market_data_bundle


def test_market_data_bundle_direct_ticker(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.market_data.builder.get_market_bundle',
        lambda ticker: {'status': 'ok', 'market': {'ticker': ticker, 'title': 'Test market'}},
    )
    monkeypatch.setattr(
        'agents.mentions.modules.market_data.builder.get_history_bundle',
        lambda ticker, series_ticker='', days=30: {'status': 'ok', 'history': [{'end_period_ts': 1}]},
    )

    bundle = build_market_data_bundle('KXTEST', ticker='KXTEST')
    assert bundle['mode'] == 'direct-ticker'
    assert bundle['resolved_market']['ticker'] == 'KXTEST'
    assert bundle['provider_status']['market'] == 'ok'


def test_market_data_bundle_resolved_query(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.market_data.builder.build_candidate_market_pool',
        lambda query, limit_per_call=12: {
            'markets': [{'ticker': 'KXTRUMPMENTION-IRAN', 'title': 'Will Trump mention Iran?', 'yes_sub_title': 'Iran'}],
            'diagnostics': ['series:KXTRUMPMENTION'],
            'raw_market_count': 10,
            'filtered_market_count': 1,
        },
    )
    monkeypatch.setattr(
        'agents.mentions.modules.market_data.builder.resolve_market_from_query',
        lambda query, markets: type('Resolved', (), {
            'ticker': 'KXTRUMPMENTION-IRAN',
            'title': 'Will Trump mention Iran?',
            'confidence': 'high',
            'rationale': 'topic-match:iran',
            'candidates': (),
            'meta': {'score_margin': 9},
        })(),
    )
    monkeypatch.setattr(
        'agents.mentions.modules.market_data.builder.get_market_bundle',
        lambda ticker: {'status': 'ok', 'market': {'ticker': ticker, 'title': 'Will Trump mention Iran?'}},
    )
    monkeypatch.setattr(
        'agents.mentions.modules.market_data.builder.get_history_bundle',
        lambda ticker, series_ticker='', days=30: {'status': 'unavailable', 'history': []},
    )

    bundle = build_market_data_bundle('Will Trump mention Iran?')
    assert bundle['mode'] == 'resolved-query'
    assert bundle['resolved_market']['ticker'] == 'KXTRUMPMENTION-IRAN'
    assert bundle['sourcing']['filtered_market_count'] == 1
