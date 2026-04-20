from agents.mentions.modules.kalshi_provider.provider import (
    get_history_bundle,
    get_market_bundle,
    search_markets_bundle,
)


def test_get_market_bundle_unavailable(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.kalshi_provider.provider.kalshi_fetch.get_market',
        lambda ticker: {},
    )
    bundle = get_market_bundle('KXTEST')
    assert bundle['status'] == 'unavailable'
    assert 'market-unavailable' in bundle['warnings']


def test_search_markets_bundle_ok(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.kalshi_provider.provider.kalshi_fetch.search_markets',
        lambda query, limit=10: [{'ticker': 'KXTEST', 'title': 'Test market'}],
    )
    bundle = search_markets_bundle('test')
    assert bundle['status'] == 'ok'
    assert bundle['markets'][0]['ticker'] == 'KXTEST'


def test_get_history_bundle_ok(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.kalshi_provider.provider.kalshi_fetch.get_history',
        lambda ticker, days=30: [{'ts': '1', 'yes_price': 55}],
    )
    bundle = get_history_bundle('KXTEST', days=7)
    assert bundle['status'] == 'ok'
    assert bundle['days'] == 7
    assert bundle['history'][0]['yes_price'] == 55
