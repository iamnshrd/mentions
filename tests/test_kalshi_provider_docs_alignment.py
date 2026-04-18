from agents.mentions.modules.kalshi_provider.provider import get_event_bundle, get_history_bundle


def test_get_event_bundle_ok(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.kalshi_provider.provider.kalshi_fetch.get_event',
        lambda event_ticker, with_nested_markets=False: {
            'event': {'event_ticker': event_ticker, 'title': 'Test Event'},
            'markets': [{'ticker': 'KXTEST'}],
        },
    )
    bundle = get_event_bundle('EVT-TEST')
    assert bundle['status'] == 'ok'
    assert bundle['event']['event_ticker'] == 'EVT-TEST'
    assert bundle['markets'][0]['ticker'] == 'KXTEST'


def test_get_history_bundle_passes_series_ticker(monkeypatch):
    seen = {}

    def fake_get_history(ticker, series_ticker='', days=30):
        seen['ticker'] = ticker
        seen['series_ticker'] = series_ticker
        seen['days'] = days
        return [{'end_period_ts': 1}]

    monkeypatch.setattr(
        'agents.mentions.modules.kalshi_provider.provider.kalshi_fetch.get_history',
        fake_get_history,
    )
    bundle = get_history_bundle('KXTEST', series_ticker='KX', days=14)
    assert bundle['status'] == 'ok'
    assert seen['series_ticker'] == 'KX'
    assert seen['days'] == 14
