from agents.mentions.runtime.retrieve import retrieve_news, retrieve_transcripts


def test_retrieve_transcripts_falls_back_to_runtime_db(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.runtime.retrieve.build_transcript_intelligence_bundle',
        lambda query, limit=5: {
            'query': query,
            'speaker': 'Donald Trump',
            'status': 'empty',
            'chunks': [],
            'summary': '',
            'top_speakers': [],
            'top_events': [],
            'context_risks': ['no-transcript-hits'],
        },
        raising=False,
    )
    monkeypatch.setattr(
        'agents.mentions.storage.runtime_query.search_transcripts_runtime',
        lambda query='', speaker='', limit=10: [{'speaker': 'Donald Trump', 'event_title': 'Interview', 'text': 'Iran mention'}],
    )
    bundle = retrieve_transcripts({'query': 'Will Trump mention Iran?', 'needs_transcript': True})
    assert bundle['status'] == 'ok'
    assert bundle['context_risks'] == ['runtime-db-transcript-fallback']


def test_retrieve_news_falls_back_to_runtime_db(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.runtime.retrieve.build_news_context_bundle',
        lambda query, category='general', market_data=None, limit=5, require_live=False: {
            'query': query,
            'category': category,
            'status': 'unavailable',
            'freshness': 'missing',
            'sufficiency': 'weak',
            'news': [],
            'summary': '',
            'event_context': {},
            'paths': {'direct': [], 'weak': [], 'late': []},
            'context_risks': ['no-news-context'],
        },
        raising=False,
    )
    monkeypatch.setattr(
        'agents.mentions.storage.runtime_query.search_news_runtime',
        lambda query='', speaker='', limit=10: [{'headline': 'Iran headline', 'url': 'https://example.com'}],
    )
    bundle = retrieve_news({'query': 'Will Trump mention Iran?', 'category': 'general'})
    assert bundle['status'] == 'ok'
    assert bundle['freshness'] == 'stored'
    assert bundle['context_risks'] == ['runtime-db-news-fallback']
