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
    from library._core.analysis.anti_patterns import (
        check_anti_patterns, apply_to_p_signal,
    )
    from library._core.analysis.evidence_conflict import detect_conflict
    from library._core.analysis.regime import detect_regime

    market = bundle.get('market', {})
    transcripts = bundle.get('transcripts', [])
    news = bundle.get('news', [])

    market_summary = analyze_market(market, frame)
    signal = assess_signal(market, frame)

    # v0.14.5: auto-classify regime so downstream record_application
    # / record_speaker_application calls can tag the Beta update
    # without the caller hand-labelling context.
    regime = detect_regime(bundle)

    # v0.13: fold anti-patterns / crowd mistakes / dispute patterns
    # into p_signal before we derive legacy labels. The bundle carries
    # doc_ids from retrieve_bundle; check_anti_patterns re-joins the
    # structured tables and returns warning flags plus down-weight
    # factor probabilities.
    warnings = check_anti_patterns(bundle)
    # v0.13.1: also scan for directional disagreement between
    # retrieved transcripts and news. This is orthogonal to
    # anti-patterns (which reads structured knowledge rows); here we
    # read the raw text content for conflicting stances.
    conflict = detect_conflict(bundle)
    warnings['conflict'] = conflict
    if conflict.get('conflicted'):
        warnings.setdefault('flags', []).append(conflict['flag'])
        warnings.setdefault('factor_ps', {})['evidence_conflict'] = (
            conflict['factor_p']
        )
        warnings['any_triggered'] = True

    if warnings['any_triggered'] and signal.get('p_signal') is not None:
        # Both anti-patterns and evidence-conflict contribute through
        # the same ``warnings['factor_ps']`` dict, so one call folds
        # everything at once. The separate
        # ``apply_conflict_to_p_signal`` helper is kept for callers who
        # only want the conflict contribution.
        adjusted = apply_to_p_signal(signal['p_signal'], warnings)
        signal['p_signal_pre_warnings'] = signal['p_signal']
        signal['p_signal'] = round(adjusted, 4)
        # Re-derive verdict / strength from the new p_signal.
        from library._core.analysis.signal import _derive_verdict
        verdict, strength = _derive_verdict(adjusted)
        signal['verdict'] = verdict
        signal['signal_strength'] = strength
        signal['score'] = round(adjusted * 4.0, 2)
        signal.setdefault('factor_ps', {}).update(warnings['factor_ps'])

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
        'warnings': warnings,
        'regime': regime,
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
