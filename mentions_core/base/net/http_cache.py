"""SQLite-backed response cache with TTL."""
from __future__ import annotations

import json
import logging
import sqlite3
import time

log = logging.getLogger('mentions')

_TABLE = 'http_cache'


def _ensure_table(conn: sqlite3.Connection) -> None:
    try:
        conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {_TABLE} (
                key        TEXT PRIMARY KEY,
                body       TEXT NOT NULL,
                expires_at REAL NOT NULL,
                inserted_at REAL NOT NULL
            )
        ''')
        conn.commit()
    except sqlite3.Error as exc:
        log.debug('_ensure_table failed: %s', exc)


def get(conn: sqlite3.Connection, key: str,
        *, clock=time.time) -> tuple[bool, object | None]:
    if not key:
        return (False, None)
    _ensure_table(conn)
    try:
        row = conn.execute(
            f'SELECT body, expires_at FROM {_TABLE} WHERE key = ?',
            (key,),
        ).fetchone()
    except sqlite3.Error as exc:
        log.debug('http_cache.get failed: %s', exc)
        return (False, None)
    if not row:
        return (False, None)
    body, expires_at = row[0], float(row[1])
    if expires_at <= clock():
        return (False, None)
    try:
        return (True, json.loads(body))
    except json.JSONDecodeError:
        return (False, None)


def put(conn: sqlite3.Connection, key: str, value: object,
        *, ttl_seconds: float, clock=time.time) -> None:
    if not key or ttl_seconds <= 0:
        return
    _ensure_table(conn)
    now = clock()
    try:
        body = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as exc:
        log.debug('http_cache.put serialize failed: %s', exc)
        return
    try:
        conn.execute(
            f'''INSERT INTO {_TABLE} (key, body, expires_at, inserted_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    body        = excluded.body,
                    expires_at  = excluded.expires_at,
                    inserted_at = excluded.inserted_at''',
            (key, body, now + ttl_seconds, now),
        )
        conn.commit()
    except sqlite3.Error as exc:
        log.debug('http_cache.put failed: %s', exc)


def purge_expired(conn: sqlite3.Connection, *, clock=time.time) -> int:
    _ensure_table(conn)
    try:
        cur = conn.execute(
            f'DELETE FROM {_TABLE} WHERE expires_at <= ?', (clock(),),
        )
        conn.commit()
        return cur.rowcount or 0
    except sqlite3.Error as exc:
        log.debug('http_cache.purge_expired failed: %s', exc)
        return 0


def clear(conn: sqlite3.Connection) -> None:
    _ensure_table(conn)
    try:
        conn.execute(f'DELETE FROM {_TABLE}')
        conn.commit()
    except sqlite3.Error as exc:
        log.debug('http_cache.clear failed: %s', exc)
