import pytest

from agents.mentions.capabilities.news_context import api
from agents.mentions.fetch.news import NewsProviderUnavailable, fetch_news_with_status


def test_news_context_build_live(monkeypatch):
    def fake_fetch(_query, category='general', limit=5):
        return [{
            'headline': 'Federal Reserve Signals Rate Path',
            'summary': 'Policy remains data dependent.',
            'source': 'Example',
            'published_at': '2026-04-15T00:00:00Z',
            'url': 'https://example.com/fed',
        }]

    monkeypatch.setattr('agents.mentions.fetch.news._fetch_live_news', fake_fetch)
    context = api.build_context(
        'fed rate decision market',
        category='macro',
        require_live=True,
    )
    assert context['news_status'] == 'live'
    assert context['news']
    assert isinstance(context['direct_paths'], list)


def test_news_context_require_live_raises(monkeypatch):
    monkeypatch.delenv('NEWSAPI_KEY', raising=False)
    with pytest.raises(NewsProviderUnavailable):
        fetch_news_with_status('fed', require_live=True)
