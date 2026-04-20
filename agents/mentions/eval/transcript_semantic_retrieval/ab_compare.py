"""Experimental comparison helper for transcript family retrieval.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations

from agents.mentions.eval.transcript_semantic_retrieval.experimental_path import run_experimental_family_path


def compare_baseline_vs_experimental(top_candidates: list[dict], transcript_ids: list[int]) -> dict:
    baseline = [
        {
            'transcript_id': row.get('transcript_id'),
            'event_title': row.get('event_title', ''),
            'quote': row.get('quote', ''),
            'topic_matches': row.get('topic_matches', []),
            'format_matches': row.get('format_matches', []),
        }
        for row in (top_candidates or [])[:5]
    ]
    experimental = run_experimental_family_path(transcript_ids)
    return {
        'status': 'ok',
        'baseline': baseline,
        'experimental': experimental.get('families', {}),
    }
