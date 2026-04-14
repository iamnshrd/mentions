"""Schema migrations for mentions_data.db.

Versioned, idempotent migrations applied in order.
Current latest version: 1
"""
from __future__ import annotations

import logging

log = logging.getLogger('mentions')

LATEST_VERSION = 1


def get_schema_version(conn) -> int:
    """Return the current schema version stored in user_version pragma."""
    row = conn.execute('PRAGMA user_version').fetchone()
    return row[0] if row else 0


def migrate_up(conn) -> None:
    """Apply all pending migrations up to LATEST_VERSION."""
    current = get_schema_version(conn)
    if current < 1:
        _v1(conn)
    log.info('Schema migrated to version %d', LATEST_VERSION)


def _v1(conn) -> None:
    """Initial schema: markets, history, analysis cache, news cache, transcripts."""
    cur = conn.cursor()

    cur.executescript('''
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            title TEXT,
            category TEXT,
            status TEXT,
            yes_price REAL,
            no_price REAL,
            volume REAL,
            open_interest REAL,
            close_time TEXT,
            fetched_at TEXT
        );

        CREATE TABLE IF NOT EXISTS market_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            yes_price REAL,
            volume REAL,
            timestamp TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_market_history_ticker
            ON market_history(ticker);

        CREATE TABLE IF NOT EXISTS analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            ticker TEXT,
            frame TEXT,
            reasoning TEXT,
            conclusion TEXT,
            confidence TEXT,
            sources TEXT,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_cache_ticker
            ON analysis_cache(ticker);

        CREATE TABLE IF NOT EXISTS news_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT,
            summary TEXT,
            source TEXT,
            published_at TEXT,
            fetched_at TEXT,
            category TEXT
        );

        CREATE TABLE IF NOT EXISTS transcript_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker TEXT,
            event TEXT,
            event_date TEXT,
            source_file TEXT UNIQUE,
            status TEXT DEFAULT 'indexed',
            added_at TEXT
        );

        CREATE TABLE IF NOT EXISTS transcript_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER REFERENCES transcript_documents(id)
                ON DELETE CASCADE,
            chunk_index INTEGER,
            text TEXT,
            speaker TEXT,
            section TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts
            USING fts5(
                text,
                speaker,
                section,
                content='transcript_chunks',
                content_rowid='id'
            );

        PRAGMA user_version = 1;
    ''')
    log.info('Schema v1 applied')
