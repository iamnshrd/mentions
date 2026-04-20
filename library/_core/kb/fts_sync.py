"""Incremental FTS5 synchronisation for ``transcript_chunks_fts``.

The v1 migration created the FTS index with ``content='transcript_chunks'``
and ``content_rowid='id'`` — a *contentless-ish* external-content setup
that requires explicit re-population after writes (there are no triggers).

This module exposes two helpers:

* ``sync_document(conn, document_id)`` — wipe and re-index only the rows
  belonging to one document. Use this after ingest/rechunk of a single
  transcript. O(chunks_in_doc).
* ``rebuild_all(conn)`` — full FTS rebuild. Keep for nuclear recovery and
  initial seeding; avoid per-ingest.

Why not triggers? Triggers on external-content FTS are possible but add a
migration step and hide write-amplification. An explicit sync call is
easier to reason about and lets the caller batch updates.
"""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger('mentions')


def sync_document(conn: sqlite3.Connection, document_id: int) -> None:
    """Refresh FTS rows for a single document.

    Safe to call inside the caller's transaction — we do not commit here.

    .. note::
       External-content FTS5 does **not** store its own content, and a raw
       ``DELETE FROM fts WHERE rowid = X`` on a rowid that was never
       indexed raises ``database disk image is malformed``. We guard
       against that by first consulting the ``_docsize`` shadow table —
       it only lists rowids FTS has actually indexed.
    """
    cur = conn.cursor()

    # Collect rowids currently indexed in FTS that belong to this document.
    indexed_rowids = [r[0] for r in cur.execute(
        '''SELECT id FROM transcript_chunks_fts_docsize
           WHERE id IN (
               SELECT id FROM transcript_chunks WHERE document_id = ?
           )''',
        (document_id,),
    ).fetchall()]

    if indexed_rowids:
        placeholders = ','.join('?' * len(indexed_rowids))
        cur.execute(
            f'DELETE FROM transcript_chunks_fts WHERE rowid IN ({placeholders})',
            indexed_rowids,
        )

    # Re-insert fresh rows from the current chunk state.
    cur.execute(
        '''INSERT INTO transcript_chunks_fts(rowid, text, speaker, section)
           SELECT id, text, COALESCE(speaker, ''), COALESCE(section, '')
           FROM transcript_chunks
           WHERE document_id = ?''',
        (document_id,),
    )
    log.debug('FTS synced for document_id=%d (removed=%d)',
              document_id, len(indexed_rowids))


def sync_chunks(conn: sqlite3.Connection, chunk_ids: list[int]) -> None:
    """Refresh FTS rows for an explicit list of chunk ids."""
    if not chunk_ids:
        return
    cur = conn.cursor()

    # Same guard as sync_document: only delete rowids that were indexed.
    placeholders_all = ','.join('?' * len(chunk_ids))
    indexed_rowids = [r[0] for r in cur.execute(
        f'SELECT id FROM transcript_chunks_fts_docsize WHERE id IN ({placeholders_all})',
        chunk_ids,
    ).fetchall()]

    if indexed_rowids:
        placeholders_idx = ','.join('?' * len(indexed_rowids))
        cur.execute(
            f'DELETE FROM transcript_chunks_fts WHERE rowid IN ({placeholders_idx})',
            indexed_rowids,
        )

    cur.execute(
        f'''INSERT INTO transcript_chunks_fts(rowid, text, speaker, section)
            SELECT id, text, COALESCE(speaker, ''), COALESCE(section, '')
            FROM transcript_chunks
            WHERE id IN ({placeholders_all})''',
        chunk_ids,
    )
    log.debug('FTS synced for %d chunks (removed=%d)',
              len(chunk_ids), len(indexed_rowids))


def rebuild_all(conn: sqlite3.Connection) -> None:
    """Full rebuild. Use sparingly — O(total chunks)."""
    conn.execute(
        'INSERT INTO transcript_chunks_fts(transcript_chunks_fts) VALUES("rebuild")'
    )
    log.info('FTS fully rebuilt')
