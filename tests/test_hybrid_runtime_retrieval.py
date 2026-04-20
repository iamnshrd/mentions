from agents.mentions.retrieval_contracts import build_retrieval_result
from agents.mentions.workflows.retrieve import retrieve_news, retrieve_transcripts


def test_retrieve_transcripts_falls_back_to_runtime_db(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.workflows.retrieve.build_transcript_intelligence_bundle',
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
    assert bundle['runtime_health']['contract'] == 'transcript_search'
    assert 'status' in bundle['runtime_health']


def test_retrieve_news_falls_back_to_runtime_db(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.workflows.retrieve.build_news_context_bundle',
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
    assert bundle['runtime_health']['contract'] == 'news_search'
    assert 'status' in bundle['runtime_health']


def test_build_retrieval_result_surfaces_runtime_health_summary():
    result = build_retrieval_result(
        market={},
        market_prior={},
        transcripts=[],
        transcript_intelligence={
            'runtime_health': {'contract': 'transcript_search', 'status': 'degraded'},
        },
        news=[],
        news_status='stored',
        news_context={
            'runtime_health': {'contract': 'news_search', 'status': 'ok'},
        },
        workflow_policy={},
        pmt_knowledge={},
        selected_pmt_evidence={},
        text_evidence_assessment={},
        posterior_update={},
        challenge_block={},
        fused_evidence={},
        has_data=True,
        sources_used=['news'],
    )
    assert result['runtime_health']['transcripts']['contract'] == 'transcript_search'
    assert result['runtime_health']['news']['contract'] == 'news_search'
