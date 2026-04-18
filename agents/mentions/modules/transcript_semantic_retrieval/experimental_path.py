"""Experimental family-path runner for transcript retrieval evaluation.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations

from agents.mentions.modules.transcript_semantic_retrieval.strategy import retrieve_family_segments


EXPERIMENTAL_FAMILIES = ['war_geopolitics', 'trade_tariffs']


def run_experimental_family_path(transcript_ids: list[int], limit_per_family: int = 3) -> dict:
    output = {}
    for family in EXPERIMENTAL_FAMILIES:
        family_rows = []
        for transcript_id in transcript_ids:
            result = retrieve_family_segments(transcript_id, family, limit=limit_per_family)
            rows = result.get('selected_results', [])[:limit_per_family]
            if rows:
                family_rows.append({
                    'transcript_id': transcript_id,
                    'mode': result.get('mode'),
                    'results': rows,
                })
        output[family] = family_rows
    return {
        'status': 'ok',
        'families': output,
    }
