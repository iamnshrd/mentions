from __future__ import annotations

from agents.mentions.application.workspace_service import (
    build_workspace_payload_for_input,
    build_workspace_payload_for_market_url,
    build_workspace_payload_for_query,
)


def test_workspace_service_builds_query_payload(monkeypatch):
    captured = {}

    def fake_build_workspace_payload(query, **kwargs):
        captured['query'] = query
        captured.update(kwargs)
        return {'query': query, 'mode': kwargs.get('mode')}

    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.build_workspace_payload',
        fake_build_workspace_payload,
    )

    payload = build_workspace_payload_for_query(
        'What will Bernie say?',
        user_id='u-1',
        news_limit=7,
        transcript_limit=4,
    )

    assert payload == {'query': 'What will Bernie say?', 'mode': 'query'}
    assert captured == {
        'query': 'What will Bernie say?',
        'user_id': 'u-1',
        'mode': 'query',
        'news_limit': 7,
        'transcript_limit': 4,
    }


def test_workspace_service_builds_market_url_payload(monkeypatch):
    captured = {}

    def fake_build_workspace_payload(query, **kwargs):
        captured['query'] = query
        captured.update(kwargs)
        return {'query': query, 'mode': kwargs.get('mode')}

    monkeypatch.setattr(
        'agents.mentions.application.workspace_service.build_workspace_payload',
        fake_build_workspace_payload,
    )

    payload = build_workspace_payload_for_market_url(
        'https://kalshi.com/markets/test-market',
        user_id='u-2',
    )

    assert payload == {
        'query': 'https://kalshi.com/markets/test-market',
        'mode': 'url',
    }
    assert captured['mode'] == 'url'
    assert captured['user_id'] == 'u-2'


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
