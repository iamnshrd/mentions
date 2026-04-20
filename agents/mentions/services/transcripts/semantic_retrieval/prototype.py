from __future__ import annotations

"""Experimental semantic transcript retrieval prototype.

This module is intentionally isolated from the main mentions path.
It will be used to compare ML-assisted transcript segment retrieval
against the current rule-based baseline before any production wiring.
"""

from agents.mentions.storage.runtime_query import get_transcript_segments
from agents.mentions.services.transcripts.semantic_retrieval.client import semantic_search, worker_health
from agents.mentions.services.transcripts.semantic_retrieval.family_taxonomy import TRANSCRIPT_FAMILY_TAXONOMY_V0


def semantic_segment_search(transcript_id: int, family: str, limit: int = 5) -> dict:
    """Experimental ML-assisted segment retrieval via remote GPU worker."""
    rows = get_transcript_segments(transcript_id)
    prompts = (TRANSCRIPT_FAMILY_TAXONOMY_V0.get(family) or {}).get('prompts', [])
    corpus = [
        {
            'id': row.get('segment_index'),
            'text': row.get('text', ''),
            'speaker': row.get('speaker', ''),
            'transcript_id': row.get('transcript_id'),
            'segment_index': row.get('segment_index'),
            'source': row.get('source', ''),
            'source_ref': row.get('source_ref', ''),
            'event_title': row.get('event_title', ''),
            'event_date': row.get('event_date', ''),
            'metadata': row.get('metadata', {}),
        }
        for row in rows
        if (row.get('text') or '').strip()
    ]
    health = worker_health()
    if health.get('status') != 'ok':
        return {
            'status': 'error',
            'family': family,
            'error': 'semantic worker unavailable',
            'worker': health,
        }
    query = ' '.join(prompts) if prompts else family
    result = semantic_search(query=query, family=family, segments=corpus, top_k=limit)
    result['segment_count'] = len(corpus)
    result['prompts'] = prompts
    result['worker'] = health
    return result
