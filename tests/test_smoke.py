"""Smoke tests — minimal coverage to catch regressions at v0.1 baseline."""
from __future__ import annotations

import pytest


def test_db_migrates_to_latest(tmp_db):
    from library.db import connect
    from library._core.kb.migrate import LATEST_VERSION, get_schema_version
    with connect(db_path=tmp_db, auto_migrate=False) as conn:
        assert get_schema_version(conn) >= LATEST_VERSION


def test_core_tables_present(tmp_db):
    import sqlite3
    expected = {
        'markets', 'market_history', 'analysis_cache', 'news_cache',
        'transcript_documents', 'transcript_chunks', 'transcript_chunks_fts',
    }
    with sqlite3.connect(tmp_db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r[0] for r in rows}
    assert expected.issubset(names), f'missing: {expected - names}'


def test_audit_pipeline_passes(tmp_db, tmp_workspace):
    from library._core.eval.audit import audit
    report = audit()
    assert report['status'] in {'ok', 'degraded'}
    assert report['passed'] >= 1


def test_frame_selection_no_crash(tmp_db, tmp_workspace):
    from library._core.runtime.frame import select_frame
    frame = select_frame('why is BTC moving today?')
    assert isinstance(frame, dict)
    assert 'route' in frame


def test_orchestrate_fallback_on_empty_query(tmp_db, tmp_workspace):
    from library._core.runtime.orchestrator import orchestrate
    result = orchestrate('')
    assert isinstance(result, dict)
    assert 'action' in result


def test_fts_query_builder_respects_token_cap():
    from library.utils import fts_query
    out = fts_query('one two three four five six seven eight nine ten')
    tokens = out.split(' OR ')
    assert len(tokens) <= 8
