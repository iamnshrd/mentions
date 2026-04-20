from __future__ import annotations

from agents.mentions.services.transcripts.semantic_retrieval.family_taxonomy import TRANSCRIPT_FAMILY_TAXONOMY_V0
from agents.mentions.services.transcripts.semantic_retrieval.prototype import semantic_segment_search


def retrieve_family_segments(transcript_id: int, family: str, limit: int = 5) -> dict:
    cfg = TRANSCRIPT_FAMILY_TAXONOMY_V0.get(family)
    if not cfg:
        return {'status': 'error', 'error': f'unknown family: {family}'}

    mode = cfg.get('mode', 'semantic_hybrid')
    result = semantic_segment_search(transcript_id, family, limit=limit)
    result['mode'] = mode
    result['family_config'] = {
        'description': cfg.get('description', ''),
        'spillovers': cfg.get('spillovers', []),
        'cluster_hints': cfg.get('cluster_hints', []),
    }

    rows = result.get('results', [])
    exclude_terms = [str(x).lower() for x in cfg.get('exclude_terms', [])]

    if mode == 'semantic_native':
        result['selected_results'] = rows[:limit]
        return result

    filtered = []
    for row in rows:
        text = (row.get('text') or '').lower()
        if exclude_terms and any(term in text for term in exclude_terms):
            continue
        filtered.append(row)

    if mode == 'prompt_guided':
        positive_terms = []
        for prompt in cfg.get('prompts', []):
            for token in ['tips', 'tipped', 'restaurant', 'delivery', 'worker', 'workers', 'hospitality', 'waiter', 'waitress']:
                if token in prompt and token not in positive_terms:
                    positive_terms.append(token)
        strict = []
        for row in filtered:
            text = (row.get('text') or '').lower()
            if any(term in text for term in positive_terms):
                strict.append(row)
        result['selected_results'] = (strict or filtered or rows)[:limit]
        return result

    result['selected_results'] = (filtered or rows)[:limit]
    return result
