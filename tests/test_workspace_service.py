from __future__ import annotations

from agents.mentions.application.workspace_service import (
    build_workspace_payload_for_input,
    build_workspace_payload_for_market_url,
    build_workspace_payload_for_query,
)


def test_workspace_service_builds_query_payload_from_single_pass_bundle(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.should_use_kb',
        lambda query: True,
    )
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.get_default_store',
        lambda: object(),
    )
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.get_frame_selector',
        lambda: (lambda query, user_id, store: {'route': 'market', 'category': 'general'}),
    )
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.get_retrieval_bundle_builder',
        lambda: (lambda query, frame: {
            'has_data': True,
            'sources_used': ['market', 'news'],
            'news_context': {'direct_event_news': [{'headline': 'Direct source', 'source': 'Action Network'}]},
            'transcripts': [{'id': 7, 'text': 'Transcript snippet', 'speaker': 'Bernie Sanders'}],
        }),
    )
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.get_analysis_engine',
        lambda: (lambda query, frame, bundle: {
            'confidence': 'medium',
            'analysis_profiles': {
                'analysis_card': {
                    'thesis': 'Structured thesis',
                    'evidence': ['E1'],
                    'uncertainty': 'U',
                    'risk': 'R',
                    'next_check': 'N',
                    'action': 'A',
                    'fair_value_view': 'F',
                }
            },
        }),
    )

    payload = build_workspace_payload_for_query('What will Bernie say?', user_id='u-1')

    assert payload['analysis_card']['thesis'] == 'Structured thesis'
    assert payload['direct_event_news'][0]['headline'] == 'Direct source'
    assert payload['transcript_trace']['excerpt'] == 'Transcript snippet'


def test_workspace_service_falls_back_fast_for_non_kb_query(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.should_use_kb',
        lambda query: False,
    )

    payload = build_workspace_payload_for_query('hello world')

    assert payload['analysis_card']['uncertainty'] == 'Query does not match known market routes.'
    assert payload['direct_event_news'] == []
    assert payload['background_news'] == []


def test_workspace_service_builds_market_url_payload(monkeypatch):
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.parse_kalshi_url',
        lambda url: {
            'ticker': 'TEST-123',
            'ticker_kind': 'market',
            'speaker_info': {'name': 'Bernie Sanders'},
        },
    )
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.get_ticker_retriever',
        lambda: (lambda ticker, speaker, ticker_kind: {
            'has_data': True,
            'sources_used': ['market'],
            'market': {'market_data': {'title': 'Test market'}},
            'news_context': {},
            'transcript_intelligence': {},
            'transcripts': [],
            'news': [],
        }),
    )
    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.synthesize_speaker_market',
        lambda **kwargs: {
            'confidence': 'low',
            'analysis_profiles': {
                'analysis_card': {
                    'thesis': 'URL thesis',
                    'evidence': [],
                    'uncertainty': 'U',
                    'risk': 'R',
                    'next_check': 'N',
                    'action': 'A',
                    'fair_value_view': 'F',
                }
            },
        },
    )

    payload = build_workspace_payload_for_market_url(
        'https://kalshi.com/markets/test-market',
        user_id='u-2',
    )

    assert payload['analysis_card']['thesis'] == 'URL thesis'


def test_workspace_service_requires_exactly_one_input():
    try:
        build_workspace_payload_for_input()
    except ValueError as exc:
        assert 'exactly one' in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError('expected ValueError when neither query nor market_url is provided')

    try:
        build_workspace_payload_for_input(query='x', market_url='https://kalshi.com/test')
    except ValueError as exc:
        assert 'exactly one' in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError('expected ValueError when both query and market_url are provided')
