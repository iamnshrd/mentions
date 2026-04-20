from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from agents.mentions.config import DATA
from .schema import SCHEMA_SQL

RUNTIME_DB_PATH = DATA / 'mentions_runtime.db'

RUNTIME_READ_REQUIREMENTS = {
    'transcript_search': {
        'transcripts': ('id', 'title', 'source', 'source_ref', 'event_id', 'event_date', 'raw_text', 'updated_at'),
        'transcript_segments': ('transcript_id', 'segment_index', 'speaker_id', 'text', 'start_ts', 'end_ts', 'metadata_json'),
        'speakers': ('id', 'canonical_name'),
        'events': ('id', 'event_key', 'title'),
    },
    'news_search': {
        'news_items': ('id', 'source', 'url', 'headline', 'published_at', 'body_text', 'fetched_at', 'speaker_id', 'event_id'),
        'speakers': ('id', 'canonical_name'),
        'events': ('id', 'event_key'),
    },
    'transcript_tags': {
        'transcript_tags': ('transcript_id', 'speaker_primary', 'topic_tags_json', 'format_tags_json', 'updated_at', 'tagging_confidence'),
        'transcripts': ('id', 'title', 'source', 'source_ref', 'event_id'),
        'events': ('id', 'event_key', 'title'),
    },
}


def connect_runtime_db(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else RUNTIME_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _runtime_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _runtime_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _runtime_table_exists(conn, table):
        return set()
    rows = conn.execute(f'PRAGMA table_info({table})').fetchall()
    return {row['name'] for row in rows}


def validate_runtime_schema(
    conn: sqlite3.Connection,
    requirements: dict[str, tuple[str, ...]],
) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for table, columns in requirements.items():
        existing = _runtime_table_columns(conn, table)
        if not existing:
            missing[table] = ['<table missing>']
            continue
        absent = [column for column in columns if column not in existing]
        if absent:
            missing[table] = absent
    return missing


def get_runtime_health(path: str | Path | None = None) -> dict:
    db_path = Path(path) if path else RUNTIME_DB_PATH
    with connect_runtime_db(db_path) as conn:
        contracts = {
            name: validate_runtime_schema(conn, requirement)
            for name, requirement in RUNTIME_READ_REQUIREMENTS.items()
        }
    return {
        'status': 'ok' if not any(contracts.values()) else 'degraded',
        'path': str(db_path),
        'contracts': contracts,
    }


def bootstrap_runtime_db(path: str | Path | None = None) -> str:
    db_path = Path(path) if path else RUNTIME_DB_PATH
    with connect_runtime_db(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_runtime_migrations(conn)
        conn.commit()
    return str(db_path)


def _ensure_runtime_migrations(conn: sqlite3.Connection) -> None:
    transcript_tag_columns = {
        'user_topic_tags_json': "ALTER TABLE transcript_tags ADD COLUMN user_topic_tags_json TEXT NOT NULL DEFAULT '[]'",
        'user_format_tags_json': "ALTER TABLE transcript_tags ADD COLUMN user_format_tags_json TEXT NOT NULL DEFAULT '[]'",
        'user_event_tags_json': "ALTER TABLE transcript_tags ADD COLUMN user_event_tags_json TEXT NOT NULL DEFAULT '[]'",
        'user_mention_tags_json': "ALTER TABLE transcript_tags ADD COLUMN user_mention_tags_json TEXT NOT NULL DEFAULT '[]'",
        'user_quality_tags_json': "ALTER TABLE transcript_tags ADD COLUMN user_quality_tags_json TEXT NOT NULL DEFAULT '[]'",
        'suggested_topic_tags_json': "ALTER TABLE transcript_tags ADD COLUMN suggested_topic_tags_json TEXT NOT NULL DEFAULT '[]'",
        'suggested_format_tags_json': "ALTER TABLE transcript_tags ADD COLUMN suggested_format_tags_json TEXT NOT NULL DEFAULT '[]'",
        'suggested_event_tags_json': "ALTER TABLE transcript_tags ADD COLUMN suggested_event_tags_json TEXT NOT NULL DEFAULT '[]'",
        'suggested_mention_tags_json': "ALTER TABLE transcript_tags ADD COLUMN suggested_mention_tags_json TEXT NOT NULL DEFAULT '[]'",
        'suggested_quality_tags_json': "ALTER TABLE transcript_tags ADD COLUMN suggested_quality_tags_json TEXT NOT NULL DEFAULT '[]'",
        'accepted_suggested_topic_tags_json': "ALTER TABLE transcript_tags ADD COLUMN accepted_suggested_topic_tags_json TEXT NOT NULL DEFAULT '[]'",
        'accepted_suggested_format_tags_json': "ALTER TABLE transcript_tags ADD COLUMN accepted_suggested_format_tags_json TEXT NOT NULL DEFAULT '[]'",
        'accepted_suggested_event_tags_json': "ALTER TABLE transcript_tags ADD COLUMN accepted_suggested_event_tags_json TEXT NOT NULL DEFAULT '[]'",
        'accepted_suggested_mention_tags_json': "ALTER TABLE transcript_tags ADD COLUMN accepted_suggested_mention_tags_json TEXT NOT NULL DEFAULT '[]'",
        'accepted_suggested_quality_tags_json': "ALTER TABLE transcript_tags ADD COLUMN accepted_suggested_quality_tags_json TEXT NOT NULL DEFAULT '[]'",
        'rejected_suggested_topic_tags_json': "ALTER TABLE transcript_tags ADD COLUMN rejected_suggested_topic_tags_json TEXT NOT NULL DEFAULT '[]'",
        'rejected_suggested_format_tags_json': "ALTER TABLE transcript_tags ADD COLUMN rejected_suggested_format_tags_json TEXT NOT NULL DEFAULT '[]'",
        'rejected_suggested_event_tags_json': "ALTER TABLE transcript_tags ADD COLUMN rejected_suggested_event_tags_json TEXT NOT NULL DEFAULT '[]'",
        'rejected_suggested_mention_tags_json': "ALTER TABLE transcript_tags ADD COLUMN rejected_suggested_mention_tags_json TEXT NOT NULL DEFAULT '[]'",
        'rejected_suggested_quality_tags_json': "ALTER TABLE transcript_tags ADD COLUMN rejected_suggested_quality_tags_json TEXT NOT NULL DEFAULT '[]'",
        'review_status': "ALTER TABLE transcript_tags ADD COLUMN review_status TEXT NOT NULL DEFAULT 'unreviewed'",
    }
    existing = {row['name'] for row in conn.execute("PRAGMA table_info(transcript_tags)").fetchall()}
    for column, sql in transcript_tag_columns.items():
        if column not in existing:
            conn.execute(sql)


def upsert_speaker(canonical_name: str, metadata: dict | None = None,
                   path: str | Path | None = None) -> int:
    metadata = metadata or {}
    slug = _slugify(canonical_name)
    with connect_runtime_db(path) as conn:
        conn.execute(
            """
            INSERT INTO speakers (canonical_name, slug, metadata_json)
            VALUES (?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                canonical_name=excluded.canonical_name,
                metadata_json=excluded.metadata_json
            """,
            (canonical_name, slug, json.dumps(metadata, ensure_ascii=False)),
        )
        row = conn.execute("SELECT id FROM speakers WHERE slug = ?", (slug,)).fetchone()
        conn.commit()
        return int(row['id'])


def upsert_topic(name: str, metadata: dict | None = None,
                 path: str | Path | None = None) -> int:
    metadata = metadata or {}
    slug = _slugify(name)
    with connect_runtime_db(path) as conn:
        conn.execute(
            """
            INSERT INTO topics (name, slug, metadata_json)
            VALUES (?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                metadata_json=excluded.metadata_json
            """,
            (name, slug, json.dumps(metadata, ensure_ascii=False)),
        )
        row = conn.execute("SELECT id FROM topics WHERE slug = ?", (slug,)).fetchone()
        conn.commit()
        return int(row['id'])


def upsert_event(event_key: str, title: str = '', event_date: str = '', source: str = '',
                 metadata: dict | None = None, path: str | Path | None = None) -> int:
    metadata = metadata or {}
    with connect_runtime_db(path) as conn:
        conn.execute(
            """
            INSERT INTO events (event_key, title, event_date, source, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET
                title=excluded.title,
                event_date=excluded.event_date,
                source=excluded.source,
                metadata_json=excluded.metadata_json
            """,
            (event_key, title, event_date, source, json.dumps(metadata, ensure_ascii=False)),
        )
        row = conn.execute("SELECT id FROM events WHERE event_key = ?", (event_key,)).fetchone()
        conn.commit()
        return int(row['id'])


def upsert_transcript(source: str, source_ref: str, title: str = '',
                      speaker_name: str = '', event_key: str = '', event_title: str = '',
                      event_date: str = '', raw_text: str = '', metadata: dict | None = None,
                      path: str | Path | None = None) -> int:
    metadata = metadata or {}
    speaker_id = upsert_speaker(speaker_name, path=path) if speaker_name else None
    event_id = upsert_event(event_key, title=event_title, event_date=event_date, source=source, path=path) if event_key else None
    with connect_runtime_db(path) as conn:
        conn.execute(
            """
            INSERT INTO transcripts (
                source, source_ref, title, speaker_id, event_id, event_date, raw_text, metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(source, source_ref) DO UPDATE SET
                title=excluded.title,
                speaker_id=excluded.speaker_id,
                event_id=excluded.event_id,
                event_date=excluded.event_date,
                raw_text=excluded.raw_text,
                metadata_json=excluded.metadata_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                source,
                source_ref,
                title,
                speaker_id,
                event_id,
                event_date,
                raw_text,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        row = conn.execute(
            "SELECT id FROM transcripts WHERE source = ? AND source_ref = ?",
            (source, source_ref),
        ).fetchone()
        conn.commit()
        return int(row['id'])


def replace_transcript_segments(transcript_id: int, segments: list[dict],
                                path: str | Path | None = None) -> int:
    speaker_cache: dict[str, int] = {}
    with connect_runtime_db(path) as conn:
        conn.execute("DELETE FROM transcript_segments WHERE transcript_id = ?", (transcript_id,))
        inserted = 0
        for idx, segment in enumerate(segments):
            speaker_name = (segment.get('speaker') or '').strip()
            speaker_id = None
            if speaker_name:
                if speaker_name not in speaker_cache:
                    slug = _slugify(speaker_name)
                    conn.execute(
                        """
                        INSERT INTO speakers (canonical_name, slug, metadata_json)
                        VALUES (?, ?, ?)
                        ON CONFLICT(slug) DO UPDATE SET canonical_name=excluded.canonical_name
                        """,
                        (speaker_name, slug, '{}'),
                    )
                    row = conn.execute("SELECT id FROM speakers WHERE slug = ?", (slug,)).fetchone()
                    speaker_cache[speaker_name] = int(row['id'])
                speaker_id = speaker_cache[speaker_name]
            conn.execute(
                """
                INSERT INTO transcript_segments (
                    transcript_id, segment_index, speaker_id, start_ts, end_ts, text, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transcript_id,
                    int(segment.get('segment_index', idx)),
                    speaker_id,
                    segment.get('start_ts', ''),
                    segment.get('end_ts', ''),
                    segment.get('text', ''),
                    json.dumps(segment.get('metadata', {}), ensure_ascii=False),
                ),
            )
            inserted += 1
        conn.commit()
        return inserted


def upsert_news_item(source: str, url: str, headline: str = '', published_at: str = '',
                     body_text: str = '', speaker_name: str = '', event_key: str = '',
                     metadata: dict | None = None, path: str | Path | None = None) -> int:
    metadata = metadata or {}
    speaker_id = upsert_speaker(speaker_name, path=path) if speaker_name else None
    event_id = upsert_event(event_key, source=source, path=path) if event_key else None
    dedupe_hash = _dedupe_hash(url, headline)
    with connect_runtime_db(path) as conn:
        conn.execute(
            """
            INSERT INTO news_items (
                source, url, headline, published_at, body_text, speaker_id, event_id, dedupe_hash, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                headline=excluded.headline,
                published_at=excluded.published_at,
                body_text=excluded.body_text,
                speaker_id=excluded.speaker_id,
                event_id=excluded.event_id,
                dedupe_hash=excluded.dedupe_hash,
                metadata_json=excluded.metadata_json,
                fetched_at=CURRENT_TIMESTAMP
            """,
            (
                source,
                url,
                headline,
                published_at,
                body_text,
                speaker_id,
                event_id,
                dedupe_hash,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        row = conn.execute("SELECT id FROM news_items WHERE url = ?", (url,)).fetchone()
        conn.commit()
        return int(row['id'])


def insert_transcript_knowledge_artifacts(transcript_id: int, knowledge_bundle: dict,
                                        speaker_name: str = '', event_key: str = '',
                                        path: str | Path | None = None) -> int:
    candidates = (knowledge_bundle or {}).get('candidates', {}) if isinstance(knowledge_bundle, dict) else {}
    speaker_id = upsert_speaker(speaker_name, path=path) if speaker_name else None
    event_id = upsert_event(event_key, path=path) if event_key else None
    inserted = 0
    with connect_runtime_db(path) as conn:
        for category, rows in candidates.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO transcript_knowledge_artifacts (
                        transcript_id, category, speaker_id, event_id, score, hits_json, artifact_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transcript_id,
                        category,
                        speaker_id,
                        event_id,
                        float(row.get('score', 0) or 0),
                        json.dumps(row.get('hits', []), ensure_ascii=False),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
                inserted += 1
        conn.commit()
    return inserted


def upsert_transcript_tags(transcript_id: int, tags: dict,
                           path: str | Path | None = None) -> int:
    tags = tags or {}
    user_topic_tags = tags.get('user_topic_tags', [])
    user_format_tags = tags.get('user_format_tags', [])
    user_event_tags = tags.get('user_event_tags', [])
    user_mention_tags = tags.get('user_mention_tags', [])
    user_quality_tags = tags.get('user_quality_tags', [])

    suggested_topic_tags = tags.get('suggested_topic_tags', tags.get('topic_tags', []))
    suggested_format_tags = tags.get('suggested_format_tags', tags.get('format_tags', []))
    suggested_event_tags = tags.get('suggested_event_tags', tags.get('event_tags', []))
    suggested_mention_tags = tags.get('suggested_mention_tags', tags.get('mention_tags', []))
    suggested_quality_tags = tags.get('suggested_quality_tags', tags.get('quality_tags', []))

    accepted_topic_tags = tags.get('accepted_suggested_topic_tags', suggested_topic_tags)
    accepted_format_tags = tags.get('accepted_suggested_format_tags', suggested_format_tags)
    accepted_event_tags = tags.get('accepted_suggested_event_tags', suggested_event_tags)
    accepted_mention_tags = tags.get('accepted_suggested_mention_tags', suggested_mention_tags)
    accepted_quality_tags = tags.get('accepted_suggested_quality_tags', suggested_quality_tags)

    rejected_topic_tags = tags.get('rejected_suggested_topic_tags', [])
    rejected_format_tags = tags.get('rejected_suggested_format_tags', [])
    rejected_event_tags = tags.get('rejected_suggested_event_tags', [])
    rejected_mention_tags = tags.get('rejected_suggested_mention_tags', [])
    rejected_quality_tags = tags.get('rejected_suggested_quality_tags', [])

    merged_topic_tags = _unique_list(user_topic_tags + accepted_topic_tags)
    merged_format_tags = _unique_list(user_format_tags + accepted_format_tags)
    merged_event_tags = _unique_list(user_event_tags + accepted_event_tags)
    merged_mention_tags = _unique_list(user_mention_tags + accepted_mention_tags)
    merged_quality_tags = _unique_list(user_quality_tags + accepted_quality_tags)
    review_status = tags.get('review_status', 'unreviewed')

    with connect_runtime_db(path) as conn:
        conn.execute(
            """
            INSERT INTO transcript_tags (
                transcript_id,
                speaker_primary,
                speaker_aliases_json,
                speaker_family_json,
                topic_tags_json,
                topic_family_tags_json,
                format_tags_json,
                event_tags_json,
                mention_tags_json,
                quality_tags_json,
                user_topic_tags_json,
                user_format_tags_json,
                user_event_tags_json,
                user_mention_tags_json,
                user_quality_tags_json,
                suggested_topic_tags_json,
                suggested_format_tags_json,
                suggested_event_tags_json,
                suggested_mention_tags_json,
                suggested_quality_tags_json,
                accepted_suggested_topic_tags_json,
                accepted_suggested_format_tags_json,
                accepted_suggested_event_tags_json,
                accepted_suggested_mention_tags_json,
                accepted_suggested_quality_tags_json,
                rejected_suggested_topic_tags_json,
                rejected_suggested_format_tags_json,
                rejected_suggested_event_tags_json,
                rejected_suggested_mention_tags_json,
                rejected_suggested_quality_tags_json,
                review_status,
                tagging_confidence,
                tagging_source,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(transcript_id) DO UPDATE SET
                speaker_primary=excluded.speaker_primary,
                speaker_aliases_json=excluded.speaker_aliases_json,
                speaker_family_json=excluded.speaker_family_json,
                topic_tags_json=excluded.topic_tags_json,
                topic_family_tags_json=excluded.topic_family_tags_json,
                format_tags_json=excluded.format_tags_json,
                event_tags_json=excluded.event_tags_json,
                mention_tags_json=excluded.mention_tags_json,
                quality_tags_json=excluded.quality_tags_json,
                user_topic_tags_json=excluded.user_topic_tags_json,
                user_format_tags_json=excluded.user_format_tags_json,
                user_event_tags_json=excluded.user_event_tags_json,
                user_mention_tags_json=excluded.user_mention_tags_json,
                user_quality_tags_json=excluded.user_quality_tags_json,
                suggested_topic_tags_json=excluded.suggested_topic_tags_json,
                suggested_format_tags_json=excluded.suggested_format_tags_json,
                suggested_event_tags_json=excluded.suggested_event_tags_json,
                suggested_mention_tags_json=excluded.suggested_mention_tags_json,
                suggested_quality_tags_json=excluded.suggested_quality_tags_json,
                accepted_suggested_topic_tags_json=excluded.accepted_suggested_topic_tags_json,
                accepted_suggested_format_tags_json=excluded.accepted_suggested_format_tags_json,
                accepted_suggested_event_tags_json=excluded.accepted_suggested_event_tags_json,
                accepted_suggested_mention_tags_json=excluded.accepted_suggested_mention_tags_json,
                accepted_suggested_quality_tags_json=excluded.accepted_suggested_quality_tags_json,
                rejected_suggested_topic_tags_json=excluded.rejected_suggested_topic_tags_json,
                rejected_suggested_format_tags_json=excluded.rejected_suggested_format_tags_json,
                rejected_suggested_event_tags_json=excluded.rejected_suggested_event_tags_json,
                rejected_suggested_mention_tags_json=excluded.rejected_suggested_mention_tags_json,
                rejected_suggested_quality_tags_json=excluded.rejected_suggested_quality_tags_json,
                review_status=excluded.review_status,
                tagging_confidence=excluded.tagging_confidence,
                tagging_source=excluded.tagging_source,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                transcript_id,
                tags.get('speaker_primary', ''),
                json.dumps(tags.get('speaker_aliases', []), ensure_ascii=False),
                json.dumps(tags.get('speaker_family', []), ensure_ascii=False),
                json.dumps(merged_topic_tags, ensure_ascii=False),
                json.dumps(tags.get('topic_family_tags', []), ensure_ascii=False),
                json.dumps(merged_format_tags, ensure_ascii=False),
                json.dumps(merged_event_tags, ensure_ascii=False),
                json.dumps(merged_mention_tags, ensure_ascii=False),
                json.dumps(merged_quality_tags, ensure_ascii=False),
                json.dumps(user_topic_tags, ensure_ascii=False),
                json.dumps(user_format_tags, ensure_ascii=False),
                json.dumps(user_event_tags, ensure_ascii=False),
                json.dumps(user_mention_tags, ensure_ascii=False),
                json.dumps(user_quality_tags, ensure_ascii=False),
                json.dumps(suggested_topic_tags, ensure_ascii=False),
                json.dumps(suggested_format_tags, ensure_ascii=False),
                json.dumps(suggested_event_tags, ensure_ascii=False),
                json.dumps(suggested_mention_tags, ensure_ascii=False),
                json.dumps(suggested_quality_tags, ensure_ascii=False),
                json.dumps(accepted_topic_tags, ensure_ascii=False),
                json.dumps(accepted_format_tags, ensure_ascii=False),
                json.dumps(accepted_event_tags, ensure_ascii=False),
                json.dumps(accepted_mention_tags, ensure_ascii=False),
                json.dumps(accepted_quality_tags, ensure_ascii=False),
                json.dumps(rejected_topic_tags, ensure_ascii=False),
                json.dumps(rejected_format_tags, ensure_ascii=False),
                json.dumps(rejected_event_tags, ensure_ascii=False),
                json.dumps(rejected_mention_tags, ensure_ascii=False),
                json.dumps(rejected_quality_tags, ensure_ascii=False),
                review_status,
                float(tags.get('tagging_confidence', 0) or 0),
                tags.get('tagging_source', ''),
            ),
        )
        row = conn.execute('SELECT id FROM transcript_tags WHERE transcript_id = ?', (transcript_id,)).fetchone()
        conn.commit()
        return int(row['id'])


def link_document(document_type: str, document_id: int, speaker_id: int | None = None,
                  topic_id: int | None = None, event_id: int | None = None,
                  link_type: str = '', confidence: float = 0.0,
                  metadata: dict | None = None,
                  path: str | Path | None = None) -> int:
    metadata = metadata or {}
    with connect_runtime_db(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO document_links (
                document_type, document_id, speaker_id, topic_id, event_id, link_type, confidence, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_type,
                document_id,
                speaker_id,
                topic_id,
                event_id,
                link_type,
                float(confidence),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def insert_market_snapshot(ticker: str, market: dict, history: list | None = None,
                           provider_status: dict | None = None,
                           path: str | Path | None = None) -> int:
    history = history or []
    provider_status = provider_status or {}
    with connect_runtime_db(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO market_snapshots (ticker, event_ticker, market_json, history_json, provider_status_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ticker,
                (market or {}).get('event_ticker', ''),
                json.dumps(market or {}, ensure_ascii=False),
                json.dumps(history, ensure_ascii=False),
                json.dumps(provider_status, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def insert_resolution_run(query: str, resolved_market: dict, sourcing: dict | None = None,
                          path: str | Path | None = None) -> int:
    resolved_market = resolved_market or {}
    sourcing = sourcing or {}
    with connect_runtime_db(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO market_resolution_runs (
                query, resolved_ticker, confidence, score_margin, candidate_count, sourcing_json, candidates_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                resolved_market.get('ticker', ''),
                resolved_market.get('confidence', 'low'),
                float(resolved_market.get('score_margin', 0) or 0),
                len(resolved_market.get('candidates', []) or []),
                json.dumps(sourcing, ensure_ascii=False),
                json.dumps(resolved_market.get('candidates', []) or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def insert_analysis_report(query: str, ticker: str, workflow_policy: dict,
                           evidence: dict, analysis: dict,
                           rendered_text: str = '', metadata: dict | None = None,
                           path: str | Path | None = None) -> int:
    metadata = metadata or {}
    with connect_runtime_db(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO analysis_reports (
                query, ticker, workflow_decision, output_mode,
                evidence_json, analysis_json, rendered_text, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                ticker,
                (workflow_policy or {}).get('decision', ''),
                (workflow_policy or {}).get('output_mode', ''),
                json.dumps(evidence or {}, ensure_ascii=False),
                json.dumps(analysis or {}, ensure_ascii=False),
                rendered_text or '',
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def _unique_list(values: list | None) -> list:
    seen = []
    for value in values or []:
        if value and value not in seen:
            seen.append(value)
    return seen


def _slugify(value: str) -> str:
    value = (value or '').strip().lower()
    value = re.sub(r'[^a-z0-9а-яё]+', '-', value)
    return value.strip('-') or 'unknown'


def _dedupe_hash(url: str, headline: str) -> str:
    import hashlib
    raw = f'{url}|{headline}'.encode('utf-8', errors='ignore')
    return hashlib.sha256(raw).hexdigest()
