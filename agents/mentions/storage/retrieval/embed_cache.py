"""Persistent cache for chunk embeddings."""
from __future__ import annotations

import array
import logging
import sqlite3

log = logging.getLogger('mentions')

_TABLE = 'chunk_embeddings'


def _pack(vec: list[float]) -> bytes:
    a = array.array('f', vec)
    import sys
    if sys.byteorder == 'big':
        a.byteswap()
    return a.tobytes()


def _unpack(blob: bytes, *, dim: int) -> list[float]:
    if len(blob) != dim * 4:
        raise ValueError(
            f'embedding blob length {len(blob)} does not match dim={dim}',
        )
    a = array.array('f')
    a.frombytes(blob)
    import sys
    if sys.byteorder == 'big':
        a.byteswap()
    return list(a)


def get_many(conn: sqlite3.Connection, chunk_ids: list[int],
             model: str) -> dict[int, list[float]]:
    if not chunk_ids or not model:
        return {}
    placeholders = ','.join('?' * len(chunk_ids))
    try:
        rows = conn.execute(
            f'''SELECT chunk_id, dim, vec
                  FROM {_TABLE}
                 WHERE model = ?
                   AND chunk_id IN ({placeholders})''',
            (model, *chunk_ids),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('embed_cache.get_many failed: %s', exc)
        return {}
    out: dict[int, list[float]] = {}
    for cid, dim, blob in rows:
        try:
            out[int(cid)] = _unpack(blob, dim=int(dim))
        except ValueError as exc:
            log.debug('embed_cache.get_many unpack skipped %s: %s', cid, exc)
    return out


def put_many(conn: sqlite3.Connection, model: str,
             rows: list[tuple[int, list[float]]]) -> int:
    if not model or not rows:
        return 0
    dim = len(rows[0][1])
    if dim == 0:
        return 0
    for _, vec in rows:
        if len(vec) != dim:
            log.debug('embed_cache.put_many mixed dims (got %d vs %d)',
                      len(vec), dim)
            return 0

    payload = [(int(cid), model, dim, _pack(vec)) for cid, vec in rows]
    try:
        conn.executemany(
            f'''INSERT INTO {_TABLE} (chunk_id, model, dim, vec)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chunk_id, model) DO UPDATE SET
                    dim        = excluded.dim,
                    vec        = excluded.vec,
                    created_at = CURRENT_TIMESTAMP''',
            payload,
        )
        conn.commit()
        return len(payload)
    except sqlite3.Error as exc:
        log.debug('embed_cache.put_many failed: %s', exc)
        return 0


def count(conn: sqlite3.Connection, model: str | None = None) -> int:
    try:
        if model:
            row = conn.execute(
                f'SELECT COUNT(*) FROM {_TABLE} WHERE model = ?', (model,),
            ).fetchone()
        else:
            row = conn.execute(f'SELECT COUNT(*) FROM {_TABLE}').fetchone()
    except sqlite3.Error as exc:
        log.debug('embed_cache.count failed: %s', exc)
        return 0
    return int(row[0]) if row else 0


def clear(conn: sqlite3.Connection, model: str | None = None) -> int:
    try:
        if model:
            cur = conn.execute(
                f'DELETE FROM {_TABLE} WHERE model = ?', (model,),
            )
        else:
            cur = conn.execute(f'DELETE FROM {_TABLE}')
        conn.commit()
        return cur.rowcount or 0
    except sqlite3.Error as exc:
        log.debug('embed_cache.clear failed: %s', exc)
        return 0

