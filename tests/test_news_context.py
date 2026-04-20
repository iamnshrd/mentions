import pytest

from agents.mentions.interfaces.capabilities.news_context import api


def test_news_context_build_live(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{
                'headline': 'Federal Reserve Signals Rate Path',
                'summary': 'Policy remains data dependent.',
                'source': 'Example',
                'published_at': '2026-04-15T00:00:00Z',
                'url': 'https://example.com/fed',
            }],
            'queries': [],
            'search_reports': [],
        },
    )
    context = api.build_context(
        'fed rate decision market',
        category='macro',
        require_live=True,
    )
    assert context['news_status'] == 'live'
    assert context['news']
    assert isinstance(context['direct_paths'], list)
    assert 'ranking_debug' in context
    assert 'direct_event_news' in context
    assert 'background_news' in context
    assert 'summary_sections' in context


def test_news_context_fetch_news_uses_google_news_only(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{'headline': 'Google only headline', 'url': 'https://example.com/google'}],
            'queries': [],
            'search_reports': [],
        },
    )
    items, status = api.fetch_news('fed', require_live=True)
    assert status == 'live'
    assert items[0]['headline'] == 'Google only headline'
