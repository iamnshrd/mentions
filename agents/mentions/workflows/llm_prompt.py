"""Canonical workflow entrypoint for prompt building."""
from __future__ import annotations

import logging

from mentions_core.base.state_store import StateStore
from agents.mentions.config import get_default_store

log = logging.getLogger('mentions')

_SYSTEM_PREFIX = """\
You are Mentions — a rigorous, data-driven analyst of Kalshi prediction markets.

Your role:
- Analyze prediction market data with precision and intellectual honesty
- Always show your reasoning chain
- Distinguish facts from interpretations; label uncertainty explicitly
- Use historical speaker transcripts when relevant patterns exist
- Be useful for decision-making, not impressive

Core principles:
- Never give confident forecasts without supporting evidence
- Distinguish signal from noise before drawing conclusions
- Historical context matters — check patterns before calling moves unusual
- Label confidence levels: low / medium / high
"""

_CONTINUITY_TEMPLATE = """\

## Session continuity
Markets tracked: {top_markets}
Recurring themes: {top_themes}
Open analyses: {open_loops}
"""

_DATA_TEMPLATE = """\

## Market data
{market_summary}

## Signal assessment
{signal_assessment}
"""

_TRANSCRIPT_TEMPLATE = """\

## Transcript corpus context
{transcript_context}
"""

_NEWS_TEMPLATE = """\

## News context
{news_context}
"""

_REASONING_TEMPLATE = """\

## Reasoning chain
{reasoning_steps}
"""


def build_prompt(query: str, frame: dict, bundle: dict, synthesis: dict,
                 user_id: str = 'default',
                 store: StateStore | None = None) -> dict:
    store = store or get_default_store()
    _ = bundle

    from mentions_core.base.session.continuity import read as read_continuity
    continuity = read_continuity(user_id=user_id, store=store)

    system = _build_system_prompt(frame, synthesis, continuity)

    return {
        'system': system,
        'user': query,
        'synthesis': synthesis,
        'continuity': continuity,
        'mode': frame.get('mode', 'deep'),
        'action': 'respond-with-data',
    }


def build_fallback_prompt(query: str, user_id: str = 'default',
                          store: StateStore | None = None) -> dict:
    store = store or get_default_store()
    from mentions_core.base.session.continuity import read as read_continuity
    continuity = read_continuity(user_id=user_id, store=store)

    return {
        'system': _SYSTEM_PREFIX,
        'user': query,
        'synthesis': None,
        'continuity': continuity,
        'mode': 'quick',
        'action': 'answer-directly',
    }


def _build_system_prompt(frame: dict, synthesis: dict, continuity: dict) -> str:
    parts = [_SYSTEM_PREFIX]

    top_markets = ', '.join(
        x.get('name', '') for x in continuity.get('top_themes', [])[:3]
        if isinstance(x, dict)
    ) or 'none yet'
    top_themes = ', '.join(
        x.get('name', '') for x in continuity.get('top_patterns', [])[:3]
        if isinstance(x, dict)
    ) or 'none yet'
    open_loops = str(len(continuity.get('open_loops', [])))

    parts.append(_CONTINUITY_TEMPLATE.format(
        top_markets=top_markets,
        top_themes=top_themes,
        open_loops=open_loops,
    ))

    market_summary = synthesis.get('market_summary', '') or 'No live data available.'
    signal = synthesis.get('signal_assessment', {})
    if isinstance(signal, dict):
        verdict = signal.get('verdict', 'unclear')
        strength = signal.get('signal_strength', 'unknown')
        signal_text = f'{verdict} (strength: {strength})'
    else:
        signal_text = 'unknown'

    parts.append(_DATA_TEMPLATE.format(
        market_summary=market_summary,
        signal_assessment=signal_text,
    ))

    reasoning = synthesis.get('reasoning_chain', [])
    if reasoning:
        steps = '\n'.join(f'  {i+1}. {step}' for i, step in enumerate(reasoning))
        parts.append(_REASONING_TEMPLATE.format(reasoning_steps=steps))

    transcript_context = synthesis.get('transcript_context', '')
    if transcript_context:
        parts.append(_TRANSCRIPT_TEMPLATE.format(
            transcript_context=transcript_context,
        ))

    news_context = synthesis.get('news_context', '')
    if news_context:
        parts.append(_NEWS_TEMPLATE.format(news_context=news_context))

    route = frame.get('route', 'general-market')
    confidence = synthesis.get('confidence', 'low')
    mode = frame.get('mode', 'deep')

    parts.append(
        f'\n## Instructions\n'
        f'Route: {route} | Mode: {mode} | Confidence: {confidence}\n'
        f'Respond with a structured analysis. Show your reasoning. '
        f'Label uncertainty. End with a clear conclusion and '
        f'recommended action.\n'
    )

    return ''.join(parts)


__all__ = ['build_fallback_prompt', 'build_prompt']
