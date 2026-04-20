#!/usr/bin/env python3
"""SQLite helpers shared across the Mentions agent.

Provides a context-managed connection factory, safe table listing,
common row-conversion utilities, and automatic schema migration on connect.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from agents.mentions.config import DB_PATH

ALLOWED_TABLES = frozenset({
    'markets',
    'market_history',
    'analysis_cache',
    'news_cache',
    'transcript_documents',
    'transcript_chunks',
    'transcript_chunks_fts',
})


def ensure_schema(conn):
    """Run pending migrations if the DB is behind the latest version."""
    from agents.mentions.kb.migrate import LATEST_VERSION, get_schema_version, migrate_up
    if get_schema_version(conn) < LATEST_VERSION:
        migrate_up(conn)


@contextmanager
def connect(db_path=None, auto_migrate: bool = True):
    """Yield a sqlite3 connection, committing on success.

    When *auto_migrate* is True (default), ``ensure_schema`` is called once
    after opening the connection to bring the DB up to the latest version.
    """
    db_target = Path(db_path or DB_PATH)
    db_target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_target)
    conn.execute('PRAGMA foreign_keys = ON')
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
