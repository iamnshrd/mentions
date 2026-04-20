"""Persistent cache for chunk embeddings.

Semantic fusion in :mod:`library._core.retrieve.hybrid` calls
``backend.encode([query, *chunk_texts])`` on every retrieval. With a
400-chunk corpus and a 40-chunk candidate pool that's 40 needless
model invocations per query — a hot loop that dominates latency on
CPU-bound sentence-transformers.

This module backs the cache with a SQLite table (``chunk_embeddings``,
defined in schema migration v3) keyed by ``(chunk_id, model)`` so
different embedding models coexist without collision.

Vector storage
--------------

Vectors are packed as little-endian float32 (`array('f', ...)`). At
384 dims that's 1.5 KB/chunk — a few MB for a 1000-chunk corpus,
trivial compared to an in-memory faiss/hnsw index. A row also stores
``dim`` so reads can validate against the expected length.

Failure policy
--------------

All SQLite errors log at ``debug`` and degrade to "no cached rows"
for reads / silent drop for writes. The cache is an accelerator, not
a correctness dependency — a broken cache must never break retrieval.
"""
from __future__ import annotations

import array
import logging
import sqlite3

log = logging.getLogger('mentions')


_TABLE = 'chunk_embeddings'


# ── Pack / unpack ──────────────────────────────────────────────────────────

def _pack(vec: list[float]) -> bytes:
    """Serialize a vector to little-endian float32 bytes.

    ``array('f')`` is platform-dependent for byte order, so we force
    little-endian via ``byteswap`` on big-endian hosts. Round-trip is
    deterministic across machines.
    """
    a = array.array('f', vec)
    import sys
    if sys.byteorder == 'big':
        a.byteswap()
    return a.tobytes()


def _unpack(blob: bytes, *, dim: int) -> list[float]:
    """Deserialize bytes back to a list[float].

    Raises :class:`ValueError` if the blob length does not match
    ``dim * 4``.
    """
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


# ── Reads ──────────────────────────────────────────────────────────────────

def get_many(conn: sqlite3.Connection, chunk_ids: list[int],
             model: str) -> dict[int, list[float]]:
    """Return ``{chunk_id: vec}`` for every cached row.

    Missing chunk_ids are simply absent from the returned mapping — the
    caller decides how to handle a partial hit (typically: embed the
    missing texts, then :func:`put_many` the new vectors).
    """
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


# ── Writes ─────────────────────────────────────────────────────────────────

def put_many(conn: sqlite3.Connection, model: str,
             rows: list[tuple[int, list[float]]]) -> int:
    """Upsert vectors. Returns the number of rows written.

    *rows* is a list of ``(chunk_id, vec)`` tuples. Vectors must be
    non-empty and of uniform dimension per call (mixing dims in one
    batch is rejected).
    """
    if not model or not rows:
        return 0
    # Validate uniform dim.
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


# ── Admin ──────────────────────────────────────────────────────────────────

def count(conn: sqlite3.Connection, model: str | None = None) -> int:
    """Return the number of cached vectors, optionally filtered by model."""
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
    """Delete every cached row (or rows for *model*). Returns count deleted."""
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
