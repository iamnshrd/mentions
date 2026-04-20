#!/usr/bin/env python3
"""SQLite helpers shared across the Mentions agent.

Provides a context-managed connection factory, safe table listing,
common row-conversion utilities, and automatic schema migration on connect.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

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


def ensure_schema(conn):
    """Run pending migrations if the DB is behind the latest version."""
    from library._core.kb.migrate import LATEST_VERSION, get_schema_version, migrate_up
    if get_schema_version(conn) < LATEST_VERSION:
        migrate_up(conn)


@contextmanager
def connect(db_path=None, auto_migrate: bool = True):
    """Yield a sqlite3 connection, committing on success.

    When *auto_migrate* is True (default), ``ensure_schema`` is called once
    after opening the connection to bring the DB up to the latest version.

    ``DB_PATH`` is resolved lazily from ``library.config`` so tests that
    monkeypatch ``config.DB_PATH`` are honored.
    """
    if db_path is None:
        from library.config import DB_PATH
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')
    # v0.14.6: WAL + synchronous=NORMAL on every connection.
    #
    # Default ``journal_mode=DELETE`` + ``synchronous=FULL`` forces an
    # fsync on every commit, which on Windows costs tens of ms per
    # write. Ingest paths (batch ``record_application``, transcript
    # writes) spend the majority of their wall time there. WAL
    # serialises writers against a single append-only log, lets
    # readers proceed without blocking, and ``synchronous=NORMAL``
    # drops the per-commit fsync to per-checkpoint. Durability window
    # shrinks from "zero" to "last WAL checkpoint" — acceptable for
    # an analytical DB whose source-of-truth inputs (Kalshi, news,
    # transcripts) are re-fetchable.
    #
    # ``PRAGMA`` statements are idempotent, cheap, and safe to issue
    # on an in-memory or already-WAL database, so we always apply
    # them. Tests that care about durability semantics can still
    # override via direct ``sqlite3.connect``.
    try:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
    except sqlite3.Error:
        # WAL isn't available on some filesystems (e.g. some network
        # mounts). The connection is still usable; fall through.
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
