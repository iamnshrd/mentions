from agents.mentions.modules.news_context.builder import build_news_context_bundle
from agents.mentions.modules.news_relevance.scorer import score_news_relevance


def test_news_context_bundle_shape_with_empty_inputs(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder.fetch_news_with_status',
        lambda *args, **kwargs: ([], 'unavailable'),
    )
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': [], 'qa_likelihood': 'low'},
    )
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {'provider_status': 'unavailable', 'raw_items': [], 'search_reports': [], 'queries': []},
    )

    bundle = build_news_context_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'unavailable'
    assert bundle['freshness'] == 'missing'
    assert bundle['sufficiency'] == 'weak'
    assert bundle['paths']['direct']
    assert 'no-news-context' in bundle['context_risks']


def test_news_context_bundle_marks_live_as_strong(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder.fetch_news_with_status',
        lambda *args, **kwargs: ([{'headline': 'Trump comments on Iran tensions'}, {'headline': 'White House weighs new Iran response'}], 'live'),
    )
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': ['iran'], 'qa_likelihood': 'high'},
    )
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {'provider_status': 'unavailable', 'raw_items': [], 'search_reports': [], 'queries': []},
    )

    bundle = build_news_context_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'live'
    assert bundle['freshness'] == 'fresh'
    assert bundle['sufficiency'] == 'strong'
    assert bundle['paths']['direct'][0] == 'iran'


def test_news_relevance_rejects_generic_context_only():
    scored = score_news_relevance(
        news=[{'headline': 'White House officials discuss campaign strategy', 'summary': 'Election positioning dominates the meeting.'}],
        speaker_hint='Donald Trump',
        topic_hints=['iran'],
        event_context={'likely_topics': ['iran'], 'format': 'press_conference', 'qa_likelihood': 'high'},
        event_hints=['press briefing'],
        event_anchors=['press briefing'],
    )
    assert not scored['kept_items']
    assert 'generic-context-only' in scored['rejected_items'][0]['noise_flags']


def test_news_context_bundle_includes_google_news_items(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder.fetch_news_with_status',
        lambda *args, **kwargs: ([], 'unavailable'),
    )
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder.fetch_rss_news_bundle',
        lambda *args, **kwargs: {'provider_status': 'unavailable', 'raw_items': [], 'feed_reports': []},
    )
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{'headline': 'Trump hosts no tax on tips roundtable', 'source': 'The Hill'}],
            'search_reports': [{'query': 'Donald Trump "no tax on tips"', 'status': 'ok', 'accepted_count': 1}],
            'queries': ['Donald Trump "no tax on tips"'],
        },
    )
    monkeypatch.setattr(
        'agents.mentions.modules.news_context.builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': ['no tax on tips'], 'qa_likelihood': 'high'},
    )

    bundle = build_news_context_bundle('What will Donald Trump say during Roundtable on No Tax on Tips?')
    assert bundle['status'] == 'live'
    assert bundle['google_news_provider']['provider_status'] == 'ok'
    assert bundle['news'][0]['headline'] == 'Trump hosts no tax on tips roundtable'
