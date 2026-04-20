from agents.mentions.modules.market_prior.builder import build_market_prior


def test_build_market_prior_from_live_market_bundle():
    prior = build_market_prior({
        'ticker': 'KXTRUMPMENTION-26APR15-IRAN',
        'market': {
            'ticker': 'KXTRUMPMENTION-26APR15-IRAN',
            'title': 'Will Trump mention Iran?',
            'yes_bid': 41,
            'yes_ask': 45,
            'liquidity': 2500,
            'volume': 800,
        },
        'history': [{}, {}, {}, {}, {}],
        'resolved_market': {
            'ticker': 'KXTRUMPMENTION-26APR15-IRAN',
            'title': 'Will Trump mention Iran?',
        },
        'provider_status': {'market': 'ok', 'history': 'ok'},
    })
    assert prior['prior_probability'] == 0.45
    assert prior['prior_confidence'] in ('medium', 'high')
    assert prior['market_regime'] in ('ambiguous_mid_confidence', 'tradable_market')
    assert prior['source'] == 'kalshi_market_prior'
