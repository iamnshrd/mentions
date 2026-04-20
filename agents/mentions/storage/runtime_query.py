from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger('mentions')

from .runtime_db import connect_runtime_db, RUNTIME_DB_PATH


def get_recent_market_snapshots(limit: int = 10, path: str | Path | None = None) -> list[dict]:
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT ticker, event_ticker, fetched_at, market_json, history_json, provider_status_json
            FROM market_snapshots
            ORDER BY fetched_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            'ticker': row['ticker'],
            'event_ticker': row['event_ticker'],
            'fetched_at': row['fetched_at'],
            'market': _loads(row['market_json'], {}),
            'history': _loads(row['history_json'], []),
            'provider_status': _loads(row['provider_status_json'], {}),
        }
        for row in rows
    ]


def get_recent_resolution_runs(limit: int = 10, path: str | Path | None = None) -> list[dict]:
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT query, resolved_ticker, confidence, score_margin, candidate_count, sourcing_json, candidates_json, created_at
            FROM market_resolution_runs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            'query': row['query'],
            'resolved_ticker': row['resolved_ticker'],
            'confidence': row['confidence'],
            'score_margin': row['score_margin'],
            'candidate_count': row['candidate_count'],
            'sourcing': _loads(row['sourcing_json'], {}),
            'candidates': _loads(row['candidates_json'], []),
            'created_at': row['created_at'],
        }
        for row in rows
    ]


def get_recent_analysis_reports(limit: int = 10, path: str | Path | None = None) -> list[dict]:
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT query, ticker, workflow_decision, output_mode, evidence_json, analysis_json, rendered_text, metadata_json, created_at
            FROM analysis_reports
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            'query': row['query'],
            'ticker': row['ticker'],
            'workflow_decision': row['workflow_decision'],
            'output_mode': row['output_mode'],
            'evidence': _loads(row['evidence_json'], {}),
            'analysis': _loads(row['analysis_json'], {}),
            'rendered_text': row['rendered_text'],
            'metadata': _loads(row['metadata_json'], {}),
            'created_at': row['created_at'],
        }
        for row in rows
    ]


def search_transcripts_runtime(query: str = '', speaker: str = '', title_query: str = '', limit: int = 10,
                               path: str | Path | None = None) -> list[dict]:
    clauses = []
    params: list = []
    if query:
        clauses.append('(ts.text LIKE ? OR t.raw_text LIKE ? OR t.title LIKE ?)')
        wildcard = f'%{query}%'
        params.extend([wildcard, wildcard, wildcard])
    if title_query:
        clauses.append('(t.title LIKE ? OR e.title LIKE ?)')
        wildcard = f'%{title_query}%'
        params.extend([wildcard, wildcard])
    if speaker:
        clauses.append('s.canonical_name = ?')
        params.append(speaker)
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''

    sql = f"""
        SELECT t.id AS transcript_id, t.title, t.source, t.source_ref, t.event_date,
               s.canonical_name AS speaker, e.event_key, e.title AS event_title,
               ts.segment_index, ts.text, ts.start_ts, ts.end_ts
        FROM transcript_segments ts
        JOIN transcripts t ON t.id = ts.transcript_id
        LEFT JOIN speakers s ON s.id = ts.speaker_id
        LEFT JOIN events e ON e.id = t.event_id
        {where}
        ORDER BY t.updated_at DESC, ts.segment_index ASC
        LIMIT ?
    """
    params.append(limit)
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_transcript_segments(transcript_id: int, path: str | Path | None = None) -> list[dict]:
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT ts.transcript_id, ts.segment_index, ts.text, ts.start_ts, ts.end_ts, ts.metadata_json,
                   s.canonical_name AS speaker
            FROM transcript_segments ts
            LEFT JOIN speakers s ON s.id = ts.speaker_id
            WHERE ts.transcript_id = ?
            ORDER BY ts.segment_index ASC
            """,
            (transcript_id,),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item['metadata'] = _loads(item.pop('metadata_json', ''), {})
        out.append(item)
    return out


def get_transcript_segment_window(transcript_id: int, segment_index: int, radius: int = 1,
                                 path: str | Path | None = None) -> list[dict]:
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT ts.transcript_id, ts.segment_index, ts.text, ts.start_ts, ts.end_ts, ts.metadata_json,
                   s.canonical_name AS speaker
            FROM transcript_segments ts
            LEFT JOIN speakers s ON s.id = ts.speaker_id
            WHERE ts.transcript_id = ?
              AND ts.segment_index BETWEEN ? AND ?
            ORDER BY ts.segment_index ASC
            """,
            (transcript_id, max(0, segment_index - radius), segment_index + radius),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item['metadata'] = _loads(item.pop('metadata_json', ''), {})
        out.append(item)
    return out


def search_news_runtime(query: str = '', speaker: str = '', limit: int = 10,
                        path: str | Path | None = None) -> list[dict]:
    clauses = []
    params: list = []
    if query:
        clauses.append('(n.headline LIKE ? OR n.body_text LIKE ?)')
        wildcard = f'%{query}%'
        params.extend([wildcard, wildcard])
    if speaker:
        clauses.append('s.canonical_name = ?')
        params.append(speaker)
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''

    sql = f"""
        SELECT n.id, n.source, n.url, n.headline, n.published_at, n.body_text, n.fetched_at,
               s.canonical_name AS speaker, e.event_key
        FROM news_items n
        LEFT JOIN speakers s ON s.id = n.speaker_id
        LEFT JOIN events e ON e.id = n.event_id
        {where}
        ORDER BY n.fetched_at DESC, n.id DESC
        LIMIT ?
    """
    params.append(limit)
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_transcript_knowledge_artifacts(query: str = '', speaker: str = '', category: str = '', limit: int = 10,
                                     path: str | Path | None = None) -> list[dict]:
    clauses = []
    params: list = []
    if query:
        clauses.append('(tka.artifact_json LIKE ? OR tka.hits_json LIKE ?)')
        wildcard = f'%{query}%'
        params.extend([wildcard, wildcard])
    if speaker:
        clauses.append('s.canonical_name = ?')
        params.append(speaker)
    if category:
        clauses.append('tka.category = ?')
        params.append(category)
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''

    sql = f"""
        SELECT tka.id, tka.category, tka.score, tka.hits_json, tka.artifact_json, tka.created_at,
               s.canonical_name AS speaker, e.event_key
        FROM transcript_knowledge_artifacts tka
        LEFT JOIN speakers s ON s.id = tka.speaker_id
        LEFT JOIN events e ON e.id = tka.event_id
        {where}
        ORDER BY tka.score DESC, tka.id DESC
        LIMIT ?
    """
    params.append(limit)
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            'id': row['id'],
            'category': row['category'],
            'score': row['score'],
            'hits': _loads(row['hits_json'], []),
            'artifact': _loads(row['artifact_json'], {}),
            'speaker': row['speaker'],
            'event_key': row['event_key'],
            'created_at': row['created_at'],
        }
        for row in rows
    ]


def get_transcript_knowledge_bundle(query: str = '', speaker: str = '', limit_per_category: int = 2,
                                  path: str | Path | None = None) -> dict:
    categories = [
        'pricing_signals',
        'execution_patterns',
        'phase_logic',
        'crowd_mistakes',
        'decision_cases',
        'speaker_tendencies',
    ]
    selected = {}
    for category in categories:
        selected[category] = get_transcript_knowledge_artifacts(
            query=query,
            speaker=speaker,
            category=category,
            limit=limit_per_category,
            path=path,
        )
    return {
        'query': query,
        'speaker': speaker,
        'selected': selected,
    }


def search_transcript_tags_runtime(speaker: str = '', topic_tags: list[str] | None = None,
                                   format_tags: list[str] | None = None, limit: int = 10,
                                   path: str | Path | None = None) -> list[dict]:
    topic_tags = topic_tags or []
    format_tags = format_tags or []
    clauses = []
    params: list = []
    if speaker:
        clauses.append('tt.speaker_primary = ?')
        params.append(speaker)
    for topic in topic_tags:
        clauses.append('tt.topic_tags_json LIKE ?')
        params.append(f'%"{topic}"%')
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''

    sql = f"""
        SELECT tt.transcript_id, tt.speaker_primary, tt.topic_tags_json, tt.topic_family_tags_json,
               tt.format_tags_json, tt.event_tags_json, tt.mention_tags_json, tt.quality_tags_json,
               tt.user_topic_tags_json, tt.user_format_tags_json, tt.user_event_tags_json,
               tt.user_mention_tags_json, tt.user_quality_tags_json,
               tt.suggested_topic_tags_json, tt.suggested_format_tags_json, tt.suggested_event_tags_json,
               tt.suggested_mention_tags_json, tt.suggested_quality_tags_json,
               tt.accepted_suggested_topic_tags_json, tt.accepted_suggested_format_tags_json, tt.accepted_suggested_event_tags_json,
               tt.accepted_suggested_mention_tags_json, tt.accepted_suggested_quality_tags_json,
               tt.rejected_suggested_topic_tags_json, tt.rejected_suggested_format_tags_json, tt.rejected_suggested_event_tags_json,
               tt.rejected_suggested_mention_tags_json, tt.rejected_suggested_quality_tags_json,
               tt.review_status,
               tt.tagging_confidence, tt.tagging_source,
               t.title, t.source, t.source_ref, e.event_key, e.title AS event_title
        FROM transcript_tags tt
        JOIN transcripts t ON t.id = tt.transcript_id
        LEFT JOIN events e ON e.id = t.event_id
        {where}
        ORDER BY tt.tagging_confidence DESC, tt.updated_at DESC, tt.id DESC
        LIMIT ?
    """
    params.append(limit)
    with connect_runtime_db(path or RUNTIME_DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item['topic_tags'] = _loads(item.pop('topic_tags_json', ''), [])
        item['topic_family_tags'] = _loads(item.pop('topic_family_tags_json', ''), [])
        item['format_tags'] = _loads(item.pop('format_tags_json', ''), [])
        item['event_tags'] = _loads(item.pop('event_tags_json', ''), [])
        item['mention_tags'] = _loads(item.pop('mention_tags_json', ''), [])
        item['quality_tags'] = _loads(item.pop('quality_tags_json', ''), [])
        item['user_topic_tags'] = _loads(item.pop('user_topic_tags_json', ''), [])
        item['user_format_tags'] = _loads(item.pop('user_format_tags_json', ''), [])
        item['user_event_tags'] = _loads(item.pop('user_event_tags_json', ''), [])
        item['user_mention_tags'] = _loads(item.pop('user_mention_tags_json', ''), [])
        item['user_quality_tags'] = _loads(item.pop('user_quality_tags_json', ''), [])
        item['suggested_topic_tags'] = _loads(item.pop('suggested_topic_tags_json', ''), [])
        item['suggested_format_tags'] = _loads(item.pop('suggested_format_tags_json', ''), [])
        item['suggested_event_tags'] = _loads(item.pop('suggested_event_tags_json', ''), [])
        item['suggested_mention_tags'] = _loads(item.pop('suggested_mention_tags_json', ''), [])
        item['suggested_quality_tags'] = _loads(item.pop('suggested_quality_tags_json', ''), [])
        item['accepted_suggested_topic_tags'] = _loads(item.pop('accepted_suggested_topic_tags_json', ''), [])
        item['accepted_suggested_format_tags'] = _loads(item.pop('accepted_suggested_format_tags_json', ''), [])
        item['accepted_suggested_event_tags'] = _loads(item.pop('accepted_suggested_event_tags_json', ''), [])
        item['accepted_suggested_mention_tags'] = _loads(item.pop('accepted_suggested_mention_tags_json', ''), [])
        item['accepted_suggested_quality_tags'] = _loads(item.pop('accepted_suggested_quality_tags_json', ''), [])
        item['rejected_suggested_topic_tags'] = _loads(item.pop('rejected_suggested_topic_tags_json', ''), [])
        item['rejected_suggested_format_tags'] = _loads(item.pop('rejected_suggested_format_tags_json', ''), [])
        item['rejected_suggested_event_tags'] = _loads(item.pop('rejected_suggested_event_tags_json', ''), [])
        item['rejected_suggested_mention_tags'] = _loads(item.pop('rejected_suggested_mention_tags_json', ''), [])
        item['rejected_suggested_quality_tags'] = _loads(item.pop('rejected_suggested_quality_tags_json', ''), [])
        if format_tags and not any(fmt in item['format_tags'] for fmt in format_tags):
            continue
        result.append(item)
    return result


def _loads(raw: str, default):
    try:
        return json.loads(raw) if raw else default
    except Exception as exc:
        log.debug('Failed to decode runtime JSON blob: %s', exc)
        return default
