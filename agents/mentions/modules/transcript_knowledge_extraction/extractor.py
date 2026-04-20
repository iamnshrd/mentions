from __future__ import annotations

from collections import defaultdict

CATEGORY_RULES = {
    'pricing_signals': ['fair value', 'priced', 'mispriced', 'overpriced', 'underpriced', 'edge', 'odds'],
    'execution_patterns': ['limit order', 'maker', 'taker', 'fill', 'fills', 'orderbook', 'spread'],
    'phase_logic': ['q&a', 'questions', 'prepared remarks', 'late', 'early', 'opening'],
    'crowd_mistakes': ['everyone', 'crowd', 'overreaction', 'assume', 'chasing'],
    'decision_cases': ['i bought', 'i sold', 'i should have', 'i regret', 'i faded', 'i held'],
    'speaker_tendencies': ['usually', 'tends to', 'historically', 'often says', 'rarely mentions'],
}

MAX_PER_SPEAKER_PER_CATEGORY = 3
MIN_TEXT_LEN = 120


def extract_transcript_knowledge_bundle(query: str, transcript_bundle: dict) -> dict:
    chunks = transcript_bundle.get('chunks', []) if isinstance(transcript_bundle, dict) else []
    candidates = _extract_candidates(chunks)
    selected = _select_bundle(candidates)
    return {
        'query': query,
        'status': 'ok' if any(selected.values()) else 'empty',
        'candidates': candidates,
        'selected': selected,
    }


def _extract_candidates(chunks: list[dict]) -> dict:
    out = {category: [] for category in CATEGORY_RULES}
    per_speaker = defaultdict(lambda: defaultdict(int))

    for chunk in chunks:
        text = ' '.join(((chunk.get('text') or chunk.get('content') or '')).split())
        if len(text) < MIN_TEXT_LEN:
            continue
        lowered = text.lower()
        speaker = (chunk.get('speaker') or '').strip() or 'unknown'

        for category, hints in CATEGORY_RULES.items():
            hits = [hint for hint in hints if hint in lowered]
            if not hits:
                continue
            if per_speaker[speaker][category] >= MAX_PER_SPEAKER_PER_CATEGORY:
                continue
            per_speaker[speaker][category] += 1
            out[category].append({
                'speaker': speaker,
                'event': chunk.get('event', ''),
                'text': text,
                'score': len(hits),
                'hits': hits,
            })

    for category in out:
        out[category].sort(key=lambda row: (-row['score'], row['speaker'], row['text']))
    return out


def _select_bundle(candidates: dict) -> dict:
    return {
        'main_pricing_signal': _first(candidates.get('pricing_signals', [])),
        'main_execution_pattern': _first(candidates.get('execution_patterns', [])),
        'main_phase_logic': _first(candidates.get('phase_logic', [])),
        'main_crowd_mistake': _first(candidates.get('crowd_mistakes', [])),
        'closest_decision_case': _first(candidates.get('decision_cases', [])),
        'speaker_tendency': _first(candidates.get('speaker_tendencies', [])),
        'secondary': {
            'pricing_signals': candidates.get('pricing_signals', [])[1:3],
            'execution_patterns': candidates.get('execution_patterns', [])[1:3],
            'phase_logic': candidates.get('phase_logic', [])[1:3],
            'crowd_mistakes': candidates.get('crowd_mistakes', [])[1:3],
            'decision_cases': candidates.get('decision_cases', [])[1:3],
            'speaker_tendencies': candidates.get('speaker_tendencies', [])[1:3],
        },
    }


def _first(rows: list[dict]) -> dict | None:
    return rows[0] if rows else None
