from agents.mentions.services.intake.resolution import recover_canonical_ticker


def test_url_resolution_recovers_market_from_series(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.intake.resolution.get_markets_bundle',
        lambda category='', limit=100, status='open', event_ticker='': {
            'markets': [
                {'ticker': 'KXTRUMPMENTION-26APR15-IRAN', 'title': 'What will Donald Trump say during interview?', 'yes_sub_title': 'Iran'},
                {'ticker': 'KXTRUMPMENTION-26APR15-NATO', 'title': 'What will Donald Trump say during interview?', 'yes_sub_title': 'NATO'},
            ]
        },
    )
    result = recover_canonical_ticker({
        'is_url': True,
        'series_slug': 'kxtrumpmention',
        'ticker': 'what-will-trump-say-iran',
    })
    assert result['ticker'] == 'KXTRUMPMENTION-26APR15-IRAN'
    assert result['url_resolution_confidence'] == 'high'
