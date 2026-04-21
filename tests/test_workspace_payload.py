from __future__ import annotations

from agents.mentions.presentation.workspace_payload import compose_workspace_payload


def test_compose_workspace_payload_uses_structured_analysis_card():
    payload = compose_workspace_payload(
        query='Will Bernie say X?',
        analysis_result={
            'synthesis': {
                'analysis_profiles': {
                    'analysis_card': {
                        'thesis': 'Structured thesis',
                        'evidence': ['E1', 'E2'],
                        'uncertainty': 'Some uncertainty',
                        'risk': 'Some risk',
                        'next_check': 'Check more',
                        'action': 'Wait',
                        'fair_value_view': 'No fair value yet',
                    }
                },
                'evidence_debug': {
                    'transcript_trace': {
                        'lead_candidate': {
                            'transcript_id': 'doc-1',
                            'segment_index': 7,
                            'source_ref': 'youtube:abc',
                            'event_title': 'Kick Off Call',
                            'event_date': '2026-04-20',
                            'start_ts': '00:01:00',
                            'end_ts': '00:01:20',
                            'speaker': 'Bernie Sanders',
                        },
                        'retrieval_hits': [
                            {
                                'chunk_id': 7,
                                'document_id': 4,
                                'chunk_index': 7,
                                'source_file': 'kickoff.txt',
                                'speaker': 'Bernie Sanders',
                                'event': 'Kick Off Call',
                            }
                        ],
                        'excerpt': 'Real transcript excerpt.',
                    },
                    'news_trace': {
                        'status': 'ok',
                        'freshness': 'fresh',
                        'sufficiency': 'strong',
                        'items': [{'headline': 'Lead item', 'source': 'Action Network'}],
                    },
                    'source_summary': {
                        'sources_used': ['news', 'transcripts'],
                        'news_count': 2,
                        'transcript_count': 1,
                    },
                    'context_risks': {
                        'news': ['limited-direct-event-coverage'],
                        'transcripts': ['partial-transcript-coverage'],
                    },
                },
            }
        },
        news_context={
            'direct_event_news': [
                {'headline': 'Direct news', 'source': 'Action Network', 'published_at': '2026-04-20T18:00:00Z'}
            ],
            'background_news': [
                {'headline': 'Background news', 'source': 'Inside Higher Ed', 'published_at': '2026-04-18T12:00:00Z'}
            ],
            'context_risks': ['limited-direct-event-coverage'],
            'ranking_debug': {
                'typed_coverage': {'coverage_state': 'event-led', 'core_count': 1},
                'ranking_summary': {'ranked_count': 2, 'kept_count': 1, 'rejected_count': 1},
            },
        },
        transcript_hits=[],
    )

    assert payload['analysis_card']['thesis'] == 'Structured thesis'
    assert payload['direct_event_news'][0]['headline'] == 'Direct news'
    assert payload['background_news'][0]['headline'] == 'Background news'
    assert payload['transcript_trace']['excerpt'] == 'Real transcript excerpt.'
    assert payload['context_risks'] == [
        'limited-direct-event-coverage',
        'partial-transcript-coverage',
    ]
    assert payload['evidence_sources'][0]['sourceType'] == 'direct'


def test_compose_workspace_payload_builds_fallback_card_without_synthesis():
    payload = compose_workspace_payload(
        query='What will Bernie say?',
        analysis_result={
            'action': 'answer-directly',
            'reason': 'Query does not match known market routes.',
        },
        news_context={
            'direct_event_news': [
                {'headline': 'Event page', 'source': 'Action Network', 'published_at': '2026-04-20T18:00:00Z'}
            ],
            'background_news': [],
            'context_risks': ['no-news-context'],
            'ranking_debug': {},
        },
        transcript_hits=[
            {
                'id': 91,
                'text': 'Transcript snippet',
                'speaker': 'Bernie Sanders',
                'event': 'Kick Off Call',
                'event_date': '2026-04-20',
            }
        ],
    )

    assert payload['analysis_card']['thesis'].startswith('Структурный market-linked analysis')
    assert 'Query does not match known market routes.' in payload['analysis_card']['uncertainty']
    assert payload['transcript_trace']['excerpt'] == 'Transcript snippet'
    assert payload['evidence_sources'][0]['sourceType'] == 'direct'
