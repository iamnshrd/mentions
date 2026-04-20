from __future__ import annotations

from mentions_domain.market_resolution import resolve_market_candidates, resolve_market_from_query
from mentions_domain.market_resolution import extract_market_entities


def build_search_queries(query: str) -> list[str]:
    q = (query or '').strip()
    if not q:
        return []

    lowered = q.lower()
    variants = [q]

    replacements = [
        ('will ', ''),
        (' in a speech', ''),
        (' in speech', ''),
        (' this week', ''),
        (' this month', ''),
        (' mention ', ' '),
    ]
    simplified = lowered
    for old, new in replacements:
        simplified = simplified.replace(old, new)
    simplified = ' '.join(simplified.split())
    if simplified and simplified not in {x.lower() for x in variants}:
        variants.append(simplified)

    entities = extract_market_entities(query)
    speaker_terms = [s.lower() for s in entities.get('speakers', [])]
    topic_terms = entities.get('topics', [])
    event_terms = entities.get('event_types', [])

    extracted = speaker_terms + topic_terms
    if extracted:
        variants.append(' '.join(extracted))
    if speaker_terms and topic_terms:
        variants.append(' '.join(speaker_terms[:1] + topic_terms[:2]))
    if entities.get('is_mention_style') and speaker_terms and topic_terms:
        variants.append(' '.join(speaker_terms[:1] + topic_terms[:2] + ['mention']))
    if speaker_terms and event_terms:
        variants.append(' '.join(speaker_terms[:1] + event_terms[:1]))

    deduped: list[str] = []
    seen = set()
    for item in variants:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item.strip())
    return deduped


def merge_search_results(result_sets: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    seen = set()
    for rows in result_sets:
        for row in rows or []:
            ticker = (row.get('ticker') or '').strip()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            out.append(row)
    return out


__all__ = [
    'build_search_queries',
    'merge_search_results',
    'resolve_market_candidates',
    'resolve_market_from_query',
]
