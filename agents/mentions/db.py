#!/usr/bin/env python3
"""SQLite helpers shared across the Mentions agent.

Provides a context-managed connection factory, safe table listing,
common row-conversion utilities, and automatic schema migration on connect.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

ALLOWED_TABLES = frozenset({
    # v1 — core market + transcript tables
    'markets',
    'market_history',
    'analysis_cache',
    'news_cache',
    'transcript_documents',
    'transcript_chunks',
    'transcript_chunks_fts',
    # v2 — structured knowledge layer
    'speaker_profiles',
    'event_formats',
    'market_archetypes',
    'heuristics',
    'heuristic_evidence',
    'pricing_signals',
    'phase_logic',
    'crowd_mistakes',
    'anti_patterns',
    'execution_patterns',
    'dispute_patterns',
    'live_trading_tells',
    'sizing_lessons',
    'decision_cases',
    'case_principles',
    'case_anti_patterns',
    'case_crowd_mistakes',
    'case_dispute_patterns',
    'case_execution_patterns',
    'case_live_trading_tells',
    'case_pricing_signals',
    'case_speaker_profiles',
})

TRANSCRIPT_SCHEMA_REQUIREMENTS = {
    'transcript_documents': (
        'id', 'source_file', 'status', 'source_type', 'language',
        'sha256', 'summary', 'char_count', 'token_count',
    ),
    'transcript_chunks': (
        'id', 'document_id', 'chunk_index', 'text', 'speaker',
        'speaker_canonical', 'section', 'char_start', 'char_end',
        'token_count', 'speaker_turn_id', 'text_sha1',
    ),
}


def ensure_schema(conn):
    """Run pending migrations if the DB is behind the latest version."""
    from agents.mentions.storage.knowledge.migrate import (
        LATEST_VERSION,
        get_schema_version,
        migrate_up,
    )
    if get_schema_version(conn) < LATEST_VERSION:
        migrate_up(conn)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    rows = conn.execute(f'PRAGMA table_info({table})').fetchall()
    return {row[1] for row in rows}


def validate_required_schema(
    conn,
    requirements: dict[str, tuple[str, ...]],
) -> dict[str, list[str]]:
    """Return missing tables/columns for a required schema contract."""
    missing: dict[str, list[str]] = {}
    for table, columns in requirements.items():
        existing = _table_columns(conn, table)
        if not existing:
            missing[table] = ['<table missing>']
            continue
        absent = [column for column in columns if column not in existing]
        if absent:
            missing[table] = absent
    return missing


def assert_transcript_schema(conn) -> None:
    """Raise when the transcript ingest contract is not satisfied."""
    missing = validate_required_schema(conn, TRANSCRIPT_SCHEMA_REQUIREMENTS)
    if not _table_exists(conn, 'transcript_chunks_fts'):
        missing['transcript_chunks_fts'] = ['<table missing>']
    if not missing:
        return
    parts = []
    for table, columns in missing.items():
        if columns == ['<table missing>']:
            parts.append(f'{table} missing')
        else:
            parts.append(f'{table} missing columns: {", ".join(columns)}')
    raise RuntimeError('Transcript schema contract not satisfied: ' + '; '.join(parts))


@contextmanager
def connect(db_path=None, auto_migrate: bool = True):
    """Yield a sqlite3 connection, committing on success.

    When *auto_migrate* is True (default), ``ensure_schema`` is called once
    after opening the connection to bring the DB up to the latest version.

    ``DB_PATH`` is resolved lazily from ``agents.mentions.config`` so tests
    that monkeypatch ``config.DB_PATH`` are honored.
    """
    if db_path is None:
        from agents.mentions.config import DB_PATH
        db_path = DB_PATH

    db_target = Path(db_path)
    db_target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_target)
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
    except sqlite3.Error:
        pass
    try:
        if auto_migrate:
            ensure_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(cur, row):
    """Convert a sqlite3 row tuple to a dict using cursor description."""
    return {d[0]: row[i] for i, d in enumerate(cur.description)}


def list_table(conn, table, limit=20):
    """List rows from *table* with a whitelist guard against SQL injection."""
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table '{table}' is not in the allowed list")
    cur = conn.cursor()
    cur.execute(f'SELECT * FROM {table} LIMIT ?', (limit,))
    return [row_to_dict(cur, row) for row in cur.fetchall()]
