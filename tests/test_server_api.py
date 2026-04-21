from __future__ import annotations

import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient

from mentions_core.server.app import create_app


def test_server_health_endpoint():
    client = TestClient(create_app())
    response = client.get('/api/health')

    assert response.status_code == 200
    assert response.json() == {
        'ok': True,
        'status': 'ok',
        'service': 'mentions-workspace-api',
    }


def test_server_workspace_endpoint_returns_payload(monkeypatch):
    client = TestClient(create_app())

    monkeypatch.setattr(
        'mentions_core.server.routes.workspace.build_workspace_payload_for_input',
        lambda **kwargs: {'query': kwargs.get('query'), 'analysis_card': {'thesis': 'ok'}},
    )

    response = client.post('/api/workspace', json={'query': 'Will Bernie say X?'})

    assert response.status_code == 200
    assert response.json() == {
        'ok': True,
        'payload': {
            'query': 'Will Bernie say X?',
            'analysis_card': {'thesis': 'ok'},
        },
    }


def test_server_workspace_endpoint_uses_error_contract(monkeypatch):
    client = TestClient(create_app())

    monkeypatch.setattr(
        'mentions_core.server.routes.workspace.build_workspace_payload_for_input',
        lambda **_kwargs: (_ for _ in ()).throw(ValueError('bad query')),
    )

    response = client.post('/api/workspace', json={'query': 'bad'})

    assert response.status_code == 400
    assert response.json() == {
        'ok': False,
        'error': {
            'code': 'bad_request',
            'message': 'bad query',
        },
    }
