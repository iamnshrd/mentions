from agents.mentions.services.news.context_builder import build_news_context_bundle
from agents.mentions.services.news.relevance import score_news_relevance


def test_news_context_bundle_shape_with_empty_inputs(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': [], 'qa_likelihood': 'low'},
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {'provider_status': 'unavailable', 'raw_items': [], 'search_reports': [], 'queries': []},
    )

    bundle = build_news_context_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'unavailable'
    assert bundle['freshness'] == 'missing'
    assert bundle['sufficiency'] == 'weak'
    assert bundle['paths']['direct'] == []
    assert bundle['news'] == []
    assert 'no-news-context' in bundle['context_risks']
    assert 'missing-fresh-news' in bundle['context_risks']
    assert bundle['quality_signals']['sufficiency'] == 'weak'


def test_news_context_bundle_marks_live_as_strong(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': ['iran'], 'qa_likelihood': 'high'},
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{'headline': 'Trump comments on Iran tensions'}, {'headline': 'White House weighs new Iran response'}],
            'search_reports': [],
            'queries': [],
        },
    )

    bundle = build_news_context_bundle('Will Trump mention Iran?')
    assert bundle['status'] == 'live'
    assert bundle['freshness'] == 'fresh'
    assert bundle['sufficiency'] == 'strong'
    assert 'Iran' in bundle['paths']['direct'][0]


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
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{'headline': 'Trump hosts no tax on tips roundtable', 'source': 'The Hill'}],
            'search_reports': [{'query': 'Donald Trump "no tax on tips"', 'status': 'ok', 'accepted_count': 1}],
            'queries': ['Donald Trump "no tax on tips"'],
        },
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': ['no tax on tips'], 'qa_likelihood': 'high'},
    )

    bundle = build_news_context_bundle('What will Donald Trump say during Roundtable on No Tax on Tips?')
    assert bundle['status'] == 'live'
    assert bundle['google_news_provider']['provider_status'] == 'ok'
    assert bundle['news'][0]['headline'] == 'Trump hosts no tax on tips roundtable'


def test_news_context_bundle_surfaces_ranking_debug(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{
                'headline': 'Trump comments on Iran tensions',
                'source': 'Reuters',
                'url': 'https://example.com/reuters',
                'published_at': '2026-04-21T09:00:00Z',
            }],
            'queries': [],
        },
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': ['iran'], 'qa_likelihood': 'high'},
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.relevance.score_news_relevance',
        lambda *args, **kwargs: {
            'ranked_items': [{
                'headline': 'Trump comments on Iran tensions',
                'source': 'Reuters',
                'decision': 'keep',
                'final_relevance_score': 3.1,
                'topic_matches': ['iran'],
                'event_hint_matches': ['remarks'],
                'event_anchor_matches': [],
                'event_phrase_matches': [],
                'noise_flags': [],
            }],
            'kept_items': [{
                'headline': 'Trump comments on Iran tensions',
                'source': 'Reuters',
                'decision': 'keep',
                'final_relevance_score': 3.1,
                'topic_matches': ['iran'],
                'event_hint_matches': ['remarks'],
                'event_anchor_matches': [],
                'event_phrase_matches': [],
                'noise_flags': [],
            }],
            'rejected_items': [{
                'headline': 'White House officials discuss campaign strategy',
                'source': 'Example',
                'decision': 'reject',
                'final_relevance_score': 1.2,
                'topic_matches': [],
                'event_hint_matches': [],
                'event_anchor_matches': [],
                'event_phrase_matches': [],
                'noise_flags': ['generic-context-only'],
            }],
        },
        raising=False,
    )

    bundle = build_news_context_bundle('Will Trump mention Iran?')
    debug = bundle['ranking_debug']
    assert debug['ranking_summary']['kept_count'] == 1
    assert debug['provider_coverage']['rss_status'] == 'disabled'
    assert debug['provider_coverage']['rss_count'] == 0
    assert debug['provider_coverage']['google_news_count'] == 1
    assert debug['lead_news']['headline'] == 'Trump comments on Iran tensions'
    assert debug['top_ranked'][0]['decision'] == 'keep'
    assert debug['top_rejected'][0]['noise_flags'] == ['generic-context-only']


def test_news_context_bundle_surfaces_context_risks_for_generic_indirect_news(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{
                'headline': 'White House officials discuss campaign strategy',
                'source': 'Example',
                'url': 'https://example.com/generic',
            }],
            'queries': [],
        },
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': ['iran'], 'qa_likelihood': 'high'},
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.relevance.score_news_relevance',
        lambda *args, **kwargs: {
            'ranked_items': [{
                'headline': 'White House officials discuss campaign strategy',
                'source': 'Example',
                'decision': 'reject',
                'final_relevance_score': 1.1,
                'topic_matches': [],
                'event_hint_matches': [],
                'event_anchor_matches': [],
                'event_phrase_matches': [],
                'noise_flags': ['generic-context-only', 'speaker-not-mentioned'],
            }],
            'kept_items': [],
            'rejected_items': [{
                'headline': 'White House officials discuss campaign strategy',
                'source': 'Example',
                'decision': 'reject',
                'final_relevance_score': 1.1,
                'topic_matches': [],
                'event_hint_matches': [],
                'event_anchor_matches': [],
                'event_phrase_matches': [],
                'noise_flags': ['generic-context-only', 'speaker-not-mentioned'],
            }],
        },
        raising=False,
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._build_typed_news',
        lambda **kwargs: {
            'core_news': [],
            'expansion_news': [],
            'ambient_news': [{'headline': 'White House officials discuss campaign strategy'}],
            'families': {},
            'has_event_core': False,
            'has_topic_expansion': False,
            'has_ambient_regime': True,
            'coverage_state': 'ambient-only',
        },
    )

    bundle = build_news_context_bundle('Will Trump mention Iran?')
    assert 'ambient-only-news' in bundle['context_risks']
    assert 'generic-news-context' in bundle['context_risks']
    assert 'speaker-not-explicit-in-news' in bundle['context_risks']
    assert bundle['quality_signals']['coverage_state'] == 'ambient-only'
    assert bundle['ranking_debug']['quality_signals']['coverage_state'] == 'ambient-only'


def test_news_context_bundle_separates_direct_and_background_news(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._fetch_google_news_bundle',
        lambda *args, **kwargs: {
            'provider_status': 'ok',
            'raw_items': [{
                'headline': 'Trump comments on Iran tensions',
                'source': 'Reuters',
                'url': 'https://example.com/direct',
            }, {
                'headline': 'Broader oil market volatility continues',
                'source': 'Bloomberg',
                'url': 'https://example.com/background',
            }],
            'queries': [],
        },
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder.analyze_event_context',
        lambda market_data, news, speaker_info: {'likely_topics': ['iran'], 'qa_likelihood': 'high'},
    )
    monkeypatch.setattr(
        'agents.mentions.services.news.context_builder._build_typed_news',
        lambda **kwargs: {
            'core_news': [{'headline': 'Trump comments on Iran tensions', 'url': 'https://example.com/direct'}],
            'expansion_news': [],
            'ambient_news': [{'headline': 'Broader oil market volatility continues', 'url': 'https://example.com/background'}],
            'families': {},
            'has_event_core': True,
            'has_topic_expansion': False,
            'has_ambient_regime': True,
            'coverage_state': 'event-led',
        },
    )

    bundle = build_news_context_bundle('Will Trump mention Iran?')
    assert bundle['direct_event_news'][0]['headline'] == 'Trump comments on Iran tensions'
    assert bundle['background_news'][0]['headline'] == 'Broader oil market volatility continues'
    assert bundle['summary_sections']['lead_direct_news']['headline'] == 'Trump comments on Iran tensions'
    assert bundle['summary_sections']['lead_background_news']['headline'] == 'Broader oil market volatility continues'
