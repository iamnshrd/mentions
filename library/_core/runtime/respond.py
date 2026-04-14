"""Response rendering — format synthesized analysis for output.

Supports two output modes:
- Interactive: human-readable text with reasoning chain (for OpenClaw)
- Structured: JSON bundle for dashboards
"""
from __future__ import annotations

import logging

from library.utils import timed

log = logging.getLogger('mentions')


@timed('respond')
def respond(query: str, mode: str = 'deep', output_format: str = 'text',
            frame: dict | None = None, synthesis: dict | None = None,
            user_id: str = 'default', store=None) -> str:
    """Render a formatted analysis response.

    If *synthesis* is not provided, runs the full pipeline.
    """
    from library._core.runtime.frame import select_frame
    from library._core.runtime.retrieve import build_retrieval_bundle
    from library._core.runtime.synthesize import synthesize as do_synthesize
    from library.config import get_default_store

    store = store or get_default_store()

    if frame is None:
        frame = select_frame(query, user_id=user_id, store=store)
    if synthesis is None:
        bundle = build_retrieval_bundle(query, frame)
        synthesis = do_synthesize(query, frame, bundle)

    if output_format == 'json':
        import json
        return json.dumps({
            'query': query,
            'frame': frame,
            'synthesis': synthesis,
        }, ensure_ascii=False, indent=2)

    return _render_text(query, frame, synthesis, mode)


def _render_text(query: str, frame: dict, synthesis: dict, mode: str) -> str:
    """Render human-readable analysis text."""
    route = frame.get('route', 'general-market')
    confidence = synthesis.get('confidence', 'low')
    market_summary = synthesis.get('market_summary', '')
    signal = synthesis.get('signal_assessment', {})
    reasoning = synthesis.get('reasoning_chain', [])
    transcript_context = synthesis.get('transcript_context', '')
    news_context = synthesis.get('news_context', '')
    conclusion = synthesis.get('conclusion', '')
    recommended_action = synthesis.get('recommended_action', '')

    if mode == 'quick':
        return _render_quick(market_summary, signal, conclusion, confidence)

    return _render_deep(
        query=query,
        route=route,
        market_summary=market_summary,
        signal=signal,
        reasoning=reasoning,
        transcript_context=transcript_context,
        news_context=news_context,
        conclusion=conclusion,
        confidence=confidence,
        recommended_action=recommended_action,
    )


def _render_quick(market_summary: str, signal: dict, conclusion: str,
                  confidence: str) -> str:
    parts = []
    if market_summary:
        parts.append(market_summary)
    if isinstance(signal, dict) and signal.get('verdict'):
        verdict = signal['verdict']
        strength = signal.get('signal_strength', '')
        parts.append(f'Signal: {verdict} ({strength})' if strength else f'Signal: {verdict}')
    if conclusion:
        parts.append(conclusion)
    parts.append(f'Confidence: {confidence}.')
    return '\n\n'.join(p for p in parts if p)


def _render_deep(query: str, route: str, market_summary: str, signal: dict,
                 reasoning: list, transcript_context: str, news_context: str,
                 conclusion: str, confidence: str, recommended_action: str) -> str:
    parts = []

    # Header
    parts.append(f'Analysis: {query}')
    parts.append(f'Route: {route} | Confidence: {confidence}')
    parts.append('─' * 48)

    # Market summary
    if market_summary:
        parts.append('Market data:')
        parts.append(market_summary)

    # Signal assessment
    if isinstance(signal, dict) and signal.get('verdict'):
        verdict = signal['verdict']
        strength = signal.get('signal_strength', 'unknown')
        note = signal.get('note', '')
        parts.append(f'\nSignal assessment: {verdict} (strength: {strength})')
        if note:
            parts.append(note)

    # Reasoning chain
    if reasoning:
        parts.append('\nReasoning chain:')
        for i, step in enumerate(reasoning, 1):
            parts.append(f'  {i}. {step}')

    # Transcript context
    if transcript_context:
        parts.append('\nHistorical speaker context:')
        parts.append(transcript_context)

    # News context
    if news_context:
        parts.append('\nNews context:')
        parts.append(news_context)

    # Conclusion
    if conclusion:
        parts.append('\nConclusion:')
        parts.append(conclusion)

    # Recommended action
    if recommended_action:
        parts.append(f'\nRecommended action: {recommended_action}')

    return '\n'.join(parts)
