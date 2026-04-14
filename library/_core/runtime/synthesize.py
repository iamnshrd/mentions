"""Response synthesis — combine frame, retrieval bundle, and analysis into a structured result.

Produces a synthesis dict consumed by respond.py for rendering.
"""
from __future__ import annotations

import logging

from library.utils import timed

log = logging.getLogger('mentions')


@timed('synthesize')
def synthesize(query: str, frame: dict, bundle: dict) -> dict:
    """Synthesize a structured analysis from retrieved data.

    Returns::

        {
            'market_summary': str,
            'signal_assessment': str,
            'reasoning_chain': list[str],
            'transcript_context': str,
            'news_context': str,
            'conclusion': str,
            'confidence': str,      # 'low' | 'medium' | 'high'
            'recommended_action': str,
        }
    """
    from library._core.analysis.market import analyze_market
    from library._core.analysis.signal import assess_signal
    from library._core.analysis.speaker import extract_speaker_context
    from library._core.analysis.reasoning import build_reasoning_chain

    market = bundle.get('market', {})
    transcripts = bundle.get('transcripts', [])
    news = bundle.get('news', [])

    market_summary = analyze_market(market, frame)
    signal = assess_signal(market, frame)
    transcript_context = extract_speaker_context(transcripts, query)
    reasoning = build_reasoning_chain(
        query=query,
        frame=frame,
        market_summary=market_summary,
        signal=signal,
        transcript_context=transcript_context,
        news=news,
    )

    confidence = _compute_confidence(bundle, signal)
    conclusion = _build_conclusion(signal, reasoning, confidence)

    return {
        'market_summary': market_summary,
        'signal_assessment': signal,
        'reasoning_chain': reasoning,
        'transcript_context': transcript_context,
        'news_context': _summarize_news(news),
        'conclusion': conclusion,
        'confidence': confidence,
        'recommended_action': _recommend_action(signal, confidence),
    }


def _compute_confidence(bundle: dict, signal: dict) -> str:
    has_live = bool(bundle.get('market', {}).get('market_data'))
    has_history = bool(bundle.get('market', {}).get('history'))
    has_transcripts = bool(bundle.get('transcripts'))
    has_news = bool(bundle.get('news'))

    score = sum([has_live, has_history, has_transcripts, has_news])
    signal_str = signal.get('signal_strength', 'unknown') if isinstance(signal, dict) else 'unknown'

    if score >= 3 and signal_str in ('strong', 'moderate'):
        return 'high'
    elif score >= 2:
        return 'medium'
    elif score >= 1:
        return 'low'
    return 'low'


def _build_conclusion(signal: dict, reasoning: list, confidence: str) -> str:
    if not isinstance(signal, dict):
        return 'Insufficient data to draw conclusions.'

    verdict = signal.get('verdict', 'unclear')
    strength = signal.get('signal_strength', 'unknown')

    parts = []
    if verdict == 'signal':
        parts.append(f'This appears to be a genuine signal (strength: {strength}).')
    elif verdict == 'noise':
        parts.append('This appears to be market noise rather than a meaningful move.')
    else:
        parts.append('The signal/noise classification is unclear with available data.')

    parts.append(f'Confidence: {confidence}.')

    if reasoning:
        parts.append('Key factor: ' + reasoning[-1])

    return ' '.join(parts)


def _summarize_news(news: list) -> str:
    if not news:
        return ''
    headlines = [n.get('headline', '') for n in news[:3] if n.get('headline')]
    return '; '.join(headlines) if headlines else ''


def _recommend_action(signal: dict, confidence: str) -> str:
    if not isinstance(signal, dict):
        return 'Monitor — insufficient data'

    verdict = signal.get('verdict', 'unclear')

    if confidence == 'low':
        return 'Monitor — low confidence, gather more data'
    if verdict == 'signal' and confidence in ('medium', 'high'):
        return 'Consider position — signal detected with adequate confidence'
    if verdict == 'noise':
        return 'Hold / ignore — likely noise'
    return 'Monitor — signal unclear'
