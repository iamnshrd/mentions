"""Evidence-conflict detection.

This module scores disagreement between transcript/news snippets so
callers can downweight directional confidence when the evidence base
pulls in opposite directions.
"""
from __future__ import annotations

import re

_BULLISH = frozenset({
    'dovish', 'cut', 'cuts', 'ease', 'easing', 'loose', 'loosen',
    'accommodative', 'stimulus', 'pause',
    'bullish', 'rally', 'surge', 'breakout', 'uptrend',
    'gain', 'gains', 'advance', 'upgrade', 'upgraded',
    'beat', 'beats', 'outperform', 'strong', 'robust', 'resilient',
    'expansion', 'growth',
})

_BEARISH = frozenset({
    'hawkish', 'hike', 'hikes', 'raise', 'raising', 'tighten',
    'tightening', 'restrictive',
    'bearish', 'selloff', 'plunge', 'plunged', 'decline', 'declined',
    'downtrend', 'crash', 'collapse', 'downgrade', 'downgraded',
    'miss', 'misses', 'underperform', 'weak', 'weaken', 'recession',
    'slowdown', 'contraction', 'stagflation',
})

_CONFLICT_THRESHOLD = 0.30
_BASE_P = 0.50
_MAX_SHIFT = 0.40


def classify_stance(text: str) -> str:
    """Return ``bullish``, ``bearish`` or ``neutral`` for a text."""
    if not text:
        return 'neutral'
    tokens = {token for token in re.split(r'[^a-z]+', text.lower()) if len(token) > 2}
    bulls = len(tokens & _BULLISH)
    bears = len(tokens & _BEARISH)
    if bulls > bears:
        return 'bullish'
    if bears > bulls:
        return 'bearish'
    return 'neutral'


def _iter_snippets(bundle: dict):
    """Yield ``(source, text)`` pairs from known bundle sections."""
    for transcript in bundle.get('transcripts') or []:
        text = transcript.get('text') or transcript.get('snippet') or ''
        if text:
            yield ('transcript', text)
    for news_item in bundle.get('news') or []:
        text = ' '.join(
            str(news_item.get(key, '')) for key in ('headline', 'summary', 'text')
        ).strip()
        if text:
            yield ('news', text)


def detect_conflict(bundle: dict) -> dict:
    """Measure directional disagreement across bundle snippets."""
    stances: list[dict] = []
    counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
    for source, text in _iter_snippets(bundle):
        stance = classify_stance(text)
        counts[stance] += 1
        stances.append({
            'source': source,
            'stance': stance,
            'snippet': text[:160],
        })

    polarised = counts['bullish'] + counts['bearish']
    if polarised < 2:
        return {
            'stances': stances,
            'counts': counts,
            'conflict_ratio': 0.0,
            'conflicted': False,
            'factor_p': None,
            'flag': None,
        }

    minority = min(counts['bullish'], counts['bearish'])
    majority = max(counts['bullish'], counts['bearish'])
    ratio = minority / (minority + majority) if (minority + majority) else 0.0
    conflicted = ratio >= _CONFLICT_THRESHOLD
    factor_p = None
    flag = None
    if conflicted:
        factor_p = max(0.0, min(1.0, _BASE_P - _MAX_SHIFT * ratio))
        flag = (
            f'Evidence conflict: {counts["bullish"]} bullish vs '
            f'{counts["bearish"]} bearish across {polarised} snippets'
        )
    return {
        'stances': stances,
        'counts': counts,
        'conflict_ratio': round(ratio, 4),
        'conflicted': conflicted,
        'factor_p': round(factor_p, 4) if factor_p is not None else None,
        'flag': flag,
    }


def apply_to_p_signal(p_signal: float | None, conflict: dict) -> float | None:
    """Fold the conflict factor into an existing ``p_signal``."""
    from mentions_domain.posteriors.probability import clamp01, combine_independent

    if p_signal is None or not conflict.get('conflicted'):
        return p_signal
    factor = conflict.get('factor_p')
    if factor is None:
        return p_signal
    return clamp01(combine_independent(p_signal, [factor]))
