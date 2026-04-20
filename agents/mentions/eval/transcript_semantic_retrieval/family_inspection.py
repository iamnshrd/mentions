"""Experimental inspection helper for transcript-family quality checks.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations

from agents.mentions.services.transcripts.semantic_retrieval.family_taxonomy import TRANSCRIPT_FAMILY_TAXONOMY_V0


def inspect_family(family: str, speaker: str = 'Donald Trump', transcript_limit: int = 8, top_k: int = 2) -> dict:
    from agents.mentions.services.transcripts.semantic_retrieval.prototype import semantic_segment_search
    from agents.mentions.eval.transcript_semantic_retrieval.corpus_discovery import sample_segments

    family_cfg = TRANSCRIPT_FAMILY_TAXONOMY_V0.get(family)
    if not family_cfg:
        return {'status': 'error', 'error': f'unknown family: {family}'}

    sampled = sample_segments(speaker=speaker, limit=transcript_limit * 3, per_transcript=1)
    transcripts = []
    seen = set()
    for row in sampled:
        tid = row.get('transcript_id')
        if not tid or tid in seen:
            continue
        seen.add(tid)
        transcripts.append({'transcript_id': tid, 'title': row.get('transcript_title', '')})
        if len(transcripts) >= transcript_limit:
            break

    inspected = []
    for row in transcripts:
        result = semantic_segment_search(row['transcript_id'], family, limit=top_k)
        family_cfg = TRANSCRIPT_FAMILY_TAXONOMY_V0.get(family, {})
        exclude_terms = [str(x).lower() for x in family_cfg.get('exclude_terms', [])]
        filtered = []
        for hit in result.get('results', []):
            text = (hit.get('text') or '').lower()
            if exclude_terms and any(term in text for term in exclude_terms):
                continue
            filtered.append(hit)
        inspected.append({
            'transcript_id': row['transcript_id'],
            'title': row['title'],
            'results': filtered or result.get('results', []),
        })

    return {
        'status': 'ok',
        'family': family,
        'description': family_cfg.get('description', ''),
        'spillovers': family_cfg.get('spillovers', []),
        'prompts': family_cfg.get('prompts', []),
        'inspected': inspected,
    }
