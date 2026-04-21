"""Experimental corpus-sampling helper for transcript-family discovery.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from agents.mentions.config import PROJECT
from agents.mentions.services.transcripts.semantic_retrieval.client import embed_texts, worker_health

DB_PATH = PROJECT / 'workspace' / 'mentions' / 'mentions_runtime.db'


def sample_segments(speaker: str = 'Donald Trump', limit: int = 200, per_transcript: int = 3) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        select ts.transcript_id, ts.segment_index, ts.text, ts.metadata_json, t.title as transcript_title, s.canonical_name as speaker
        from transcript_segments ts
        join transcripts t on t.id = ts.transcript_id
        join speakers s on s.id = ts.speaker_id
        where s.canonical_name = ?
          and length(ts.text) >= 120
        order by t.updated_at desc, ts.transcript_id asc, ts.segment_index asc
        """,
        (speaker,),
    ).fetchall()
    grouped = {}
    sampled = []
    for row in rows:
        tid = row['transcript_id']
        grouped.setdefault(tid, 0)
        if grouped[tid] >= per_transcript:
            continue
        grouped[tid] += 1
        sampled.append(dict(row))
        if len(sampled) >= limit:
            break
    return sampled


def discover_transcript_families(speaker: str = 'Donald Trump', limit: int = 200) -> dict:
    health = worker_health()
    if health.get('status') != 'ok':
        return {'status': 'error', 'error': 'worker unavailable', 'worker': health}
    segments = sample_segments(speaker=speaker, limit=limit)
    texts = [row.get('text', '') for row in segments]
    result = embed_texts(texts)
    return {
        'status': result.get('status', 'error'),
        'speaker': speaker,
        'segment_count': len(segments),
        'worker': health,
        'embedding_count': result.get('count', 0),
        'sample_titles': [row.get('transcript_title', '') for row in segments[:10]],
    }
