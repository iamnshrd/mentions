from agents.mentions.modules.url_intake.resolution import recover_canonical_ticker


def test_url_resolution_prefers_exact_content_label(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.url_intake.resolution.get_markets_bundle',
        lambda category='', limit=100, status='open', event_ticker='': {
            'markets': [
                {'ticker': 'KXTRUMPMENTION-26APR15-VENE', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'Venezuela'},
                {'ticker': 'KXTRUMPMENTION-26APR15-IRAN', 'title': 'What will Donald Trump say?', 'yes_sub_title': 'Iran'},
            ]
        },
    )
    result = recover_canonical_ticker({
        'is_url': True,
        'series_slug': 'kxtrumpmention',
        'ticker': 'what-will-trump-say-iran',
    })
    assert result['ticker'] == 'KXTRUMPMENTION-26APR15-IRAN'
