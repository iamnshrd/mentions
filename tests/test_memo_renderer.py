from agents.mentions.presentation.response_renderer import render_user_response
import json


def test_memo_renderer_deep_contains_sections():
    text = render_user_response(
        query='Will Trump mention Iran?',
        frame={'route': 'speaker-event'},
        synthesis={
            'market_summary': 'Market: Will Trump mention Iran?',
            'signal_assessment': {'verdict': 'unclear', 'signal_strength': 'unknown'},
            'reasoning_chain': ['Resolution still weak', 'Fresh context incomplete'],
            'transcript_context': 'No speaker context yet',
            'news_context': 'No direct news confirmation',
            'conclusion': 'Partial only.',
            'confidence': 'low',
            'recommended_action': 'Wait for better context',
        },
        mode='deep',
    )
    assert 'Разбор:' in text
    assert 'Логика:' in text
    assert 'Вывод:' in text
    assert 'Маршрут:' in text


def test_memo_renderer_quick_is_compact():
    text = render_user_response(
        query='x',
        frame={},
        synthesis={
            'market_summary': 'Market summary',
            'signal_assessment': {'verdict': 'unclear', 'signal_strength': 'unknown'},
            'conclusion': 'No edge',
            'confidence': 'low',
        },
        mode='quick',
    )
    assert 'Market summary' in text
    assert 'Сигнал:' in text
    assert 'Уверенность:' in text


def test_memo_renderer_json_includes_debug_view():
    text = render_user_response(
        query='Will Trump mention Iran?',
        frame={'route': 'speaker-event'},
        synthesis={
            'evidence_debug': {
                'source_summary': {
                    'sources_used': ['news', 'transcripts'],
                    'news_count': 1,
                    'transcript_count': 2,
                    'has_market_data': True,
                    'has_history': False,
                },
                'runtime_health': {
                    'transcripts': {'contract': 'transcript_search', 'status': 'ok'},
                },
                'context_risks': {
                    'news': ['runtime-db-news-fallback'],
                    'transcripts': [],
                },
                'transcript_trace': {
                    'lead_candidate': {'transcript_id': 'tx-1', 'segment_index': 3},
                },
                'news_trace': {
                    'status': 'ok',
                    'freshness': 'stored',
                    'sufficiency': 'partial',
                    'items': [{'headline': 'Iran headline'}],
                },
            },
        },
        output_format='json',
    )
    payload = json.loads(text)
    assert payload['debug_view']['summary']['sources_used'] == ['news', 'transcripts']
    assert payload['debug_view']['runtime_health']['transcripts']['contract'] == 'transcript_search'
    assert payload['debug_view']['top_evidence']['lead_transcript']['transcript_id'] == 'tx-1'


def test_memo_renderer_debug_mode_renders_debug_sections():
    text = render_user_response(
        query='Will Trump mention Iran?',
        frame={'route': 'speaker-event'},
        synthesis={
            'evidence_debug': {
                'source_summary': {
                    'sources_used': ['news', 'transcripts'],
                    'news_count': 1,
                    'transcript_count': 2,
                },
                'runtime_health': {
                    'news': {'contract': 'news_search', 'status': 'degraded'},
                },
                'context_risks': {
                    'news': ['runtime-db-news-fallback'],
                    'transcripts': ['runtime-db-transcript-fallback'],
                },
                'transcript_trace': {
                    'lead_candidate': {'transcript_id': 'tx-1', 'source_ref': 'yt:abc'},
                },
                'news_trace': {
                    'status': 'ok',
                    'freshness': 'stored',
                    'sufficiency': 'partial',
                    'items': [{'headline': 'Iran headline'}],
                },
            },
        },
        mode='debug',
    )
    assert 'Debug View' in text
    assert 'Runtime health [news]: degraded (news_search)' in text
    assert 'Lead transcript:' in text
    assert 'Lead news: Iran headline' in text
