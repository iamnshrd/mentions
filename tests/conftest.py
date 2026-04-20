"""Shared pytest fixtures for the Mentions test suite.

All tests run against a temporary DB seeded by migrations, never the real
mentions_data.db. Monkeypatch canonical config modules at session scope so
lazy imports resolve to the temp file and temp workspace.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    """Yield a fresh sqlite DB path with schema migrated to latest version."""
    db_path = tmp_path / 'test_mentions.db'

    # Redirect both the module-level path and the lazy connect() reader.
    from agents.mentions import config as cfg
    monkeypatch.setattr(cfg, 'DB_PATH', db_path)

    from agents.mentions.db import connect
    with connect(db_path=db_path, auto_migrate=True) as conn:
        conn.execute('PRAGMA foreign_keys = ON')

    yield db_path


@pytest.fixture
def tmp_workspace(monkeypatch, tmp_path):
    """Redirect WORKSPACE and related JSON files to a temp dir."""
    ws = tmp_path / 'workspace'
    ws.mkdir()
    from mentions_core.base import config as cfg
    monkeypatch.setattr(cfg, 'WORKSPACE', ws)
    monkeypatch.setattr(cfg, 'CONTINUITY', ws / 'continuity.json')
    monkeypatch.setattr(cfg, 'SESSION_STATE', ws / 'session_state.json')
    monkeypatch.setattr(cfg, 'USER_STATE', ws / 'user_state.json')
    monkeypatch.setattr(cfg, 'CHECKPOINTS', ws / 'session_checkpoints.jsonl')
    monkeypatch.setattr(cfg, 'CONTEXT_GRAPH', ws / 'context_graph.json')
    monkeypatch.setattr(cfg, 'METRICS_LOG', ws / 'metrics.jsonl')
    monkeypatch.setattr(cfg, 'TRACE_LOG', ws / 'traces.jsonl')
    monkeypatch.setattr(cfg, '_default_store', None)
    yield ws
