"""Build / refresh the knowledge base.

Initialises the schema and indexes any unindexed transcripts in the
Mentions transcript store against the DB.
"""
from __future__ import annotations

import logging

from agents.mentions.utils import now_iso

log = logging.getLogger('mentions')


def build() -> dict:
    """Ensure schema is up to date and index any unindexed transcripts.

    Returns a summary report dict.
    """
    # Ensure schema
    from agents.mentions.db import connect
    from agents.mentions.kb.migrate import LATEST_VERSION, get_schema_version, migrate_up
    with connect(auto_migrate=False) as conn:
        current = get_schema_version(conn)
        if current < LATEST_VERSION:
            migrate_up(conn)
            log.info('Schema migrated to v%d', LATEST_VERSION)

    # Index unindexed transcripts
    indexed = _index_new_transcripts()

    # Refresh FTS
    _refresh_fts()

    return {
        'status': 'ok',
        'transcripts_indexed': indexed,
        'timestamp': now_iso(),
    }


def _index_new_transcripts() -> list[str]:
    """Find transcript files not yet in the DB and index them."""
    from agents.mentions.config import TRANSCRIPTS
    from agents.mentions.db import connect
    from agents.mentions.ingest.transcript import register

    if not TRANSCRIPTS.exists():
        return []

    # Get already-indexed files
    indexed_files: set[str] = set()
    try:
        with connect() as conn:
            cur = conn.cursor()
            for row in cur.execute('SELECT source_file FROM transcript_documents').fetchall():
                indexed_files.add(row[0])
    except Exception as exc:
        log.warning('Could not read transcript_documents: %s', exc)
        return []

    new_indexed = []
    for path in sorted(TRANSCRIPTS.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {'.txt', '.pdf'}:
            continue
        if str(path) in indexed_files:
            continue
        try:
            result = register(str(path))
            if result.get('status') == 'indexed':
                new_indexed.append(path.name)
                log.info('Auto-indexed transcript: %s', path.name)
        except Exception as exc:
            log.warning('Failed to index %s: %s', path.name, exc)

    return new_indexed


def _refresh_fts() -> None:
    """Rebuild the FTS5 index."""
    from agents.mentions.db import connect
    try:
        with connect() as conn:
            conn.execute('INSERT INTO transcript_chunks_fts(transcript_chunks_fts) VALUES("rebuild")')
        log.debug('FTS index rebuilt')
    except Exception as exc:
        log.debug('FTS rebuild note: %s', exc)
