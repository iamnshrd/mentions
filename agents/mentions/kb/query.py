"""Query layer — search market data and transcript corpus."""
from __future__ import annotations

import logging

from agents.mentions.db import connect, row_to_dict
from agents.mentions.utils import fts_query as build_fts

log = logging.getLogger('mentions')


def query(search: str, limit: int = 8) -> dict:
    """Unified query: search markets by title + transcripts by text.

    Returns combined results dict.
    """
    market_results = query_markets(search, limit=limit)
    transcript_results = query_transcripts(build_fts(search), limit=limit)
    cached = query_analysis_cache(search, limit=3)

    return {
        'markets': market_results,
        'transcripts': transcript_results,
        'cached_analysis': cached,
        'query': search,
    }


def query_markets(search: str, limit: int = 10,
                  category: str = '') -> list[dict]:
    """Search the markets table by title or ticker."""
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            if category:
                cur.execute(
                    '''SELECT * FROM markets
                       WHERE (title LIKE ? OR ticker LIKE ?) AND category = ?
                       ORDER BY volume DESC LIMIT ?''',
                    (f'%{search}%', f'%{search}%', category, limit),
                )
            else:
                cur.execute(
                    '''SELECT * FROM markets
                       WHERE title LIKE ? OR ticker LIKE ?
                       ORDER BY volume DESC LIMIT ?''',
                    (f'%{search}%', f'%{search}%', limit),
                )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.warning('query_markets failed: %s', exc)
    return results


def query_transcripts(fts: str, limit: int = 5,
                      speaker: str = '') -> list[dict]:
    """FTS search over transcript corpus.

    *fts* should be a pre-built FTS5 query string.
    """
    if not fts:
        return []
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            if speaker:
                cur.execute(
                    '''SELECT tc.id, tc.text, tc.speaker, tc.section,
                              td.event, td.event_date
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks tc ON tc.id = fts.rowid
                       JOIN transcript_documents td ON td.id = tc.document_id
                       WHERE transcript_chunks_fts MATCH ?
                         AND tc.speaker LIKE ?
                       ORDER BY rank
                       LIMIT ?''',
                    (fts, f'%{speaker}%', limit),
                )
            else:
                cur.execute(
                    '''SELECT tc.id, tc.text, tc.speaker, tc.section,
                              td.event, td.event_date
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks tc ON tc.id = fts.rowid
                       JOIN transcript_documents td ON td.id = tc.document_id
                       WHERE transcript_chunks_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?''',
                    (fts, limit),
                )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_transcripts FTS failed: %s', exc)
    return results


def query_analysis_cache(query_text: str, limit: int = 3) -> list[dict]:
    """Return recent cached analyses matching *query_text*."""
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT * FROM analysis_cache
                   WHERE query LIKE ? OR ticker LIKE ?
                   ORDER BY created_at DESC LIMIT ?''',
                (f'%{query_text[:40]}%', f'%{query_text[:20]}%', limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_analysis_cache failed: %s', exc)
    return results


def save_analysis(query_text: str, ticker: str, frame: dict,
                  synthesis: dict) -> None:
    """Persist an analysis result to the cache."""
    import json
    from agents.mentions.utils import now_iso
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''INSERT INTO analysis_cache
                   (query, ticker, frame, reasoning, conclusion, confidence,
                    sources, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    query_text[:500],
                    ticker,
                    json.dumps(frame, ensure_ascii=False),
                    json.dumps(synthesis.get('reasoning_chain', []),
                               ensure_ascii=False),
                    synthesis.get('conclusion', ''),
                    synthesis.get('confidence', ''),
                    json.dumps([], ensure_ascii=False),
                    now_iso(),
                ),
            )
    except Exception as exc:
        log.debug('save_analysis failed: %s', exc)
