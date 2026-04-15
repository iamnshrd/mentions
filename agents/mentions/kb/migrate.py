"""Schema migrations for the Mentions pack DB."""
from __future__ import annotations

import logging

log = logging.getLogger('mentions')

LATEST_VERSION = 3


def get_schema_version(conn) -> int:
    """Return the current schema version stored in ``PRAGMA user_version``."""
    row = conn.execute('PRAGMA user_version').fetchone()
    return row[0] if row else 0


def migrate_up(conn) -> None:
    """Apply all pending migrations up to ``LATEST_VERSION``."""
    current = get_schema_version(conn)
    if current < 1:
        _v1(conn)
        current = 1
    if current < 2:
        _v2(conn)
        current = 2
    if current < 3:
        _v3(conn)
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
            category TEXT,
            url TEXT
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


def _v2(conn) -> None:
    """Schema v2: guarantee ``url`` exists in ``news_cache``."""
    cur = conn.cursor()
    cols = {row[1] for row in cur.execute('PRAGMA table_info(news_cache)').fetchall()}
    if 'url' not in cols:
        cur.execute("ALTER TABLE news_cache ADD COLUMN url TEXT DEFAULT ''")
    cur.execute('PRAGMA user_version = 2')
    log.info('Schema v2 applied')


def _v3(conn) -> None:
    """Schema v3: deduplicate ``news_cache`` and enforce uniqueness."""
    cur = conn.cursor()
    cur.execute(
        '''
        DELETE FROM news_cache
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM news_cache
            GROUP BY headline, published_at, url, category
        )
        '''
    )
    cur.execute(
        '''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_news_cache_unique
        ON news_cache(headline, published_at, url, category)
        '''
    )
    cur.execute('PRAGMA user_version = 3')
    log.info('Schema v3 applied')
