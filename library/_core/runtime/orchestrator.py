"""Runtime orchestrator — coordinate all runtime modules via direct imports.

Supports two modes:
- Interactive: user query → analysis response
- Autonomous: no user query → scan top movers → dashboard output
"""
from __future__ import annotations

import logging

from library._core.runtime.frame import select_frame
from library._core.runtime.retrieve import build_retrieval_bundle
from library._core.runtime.synthesize import synthesize
from library._core.runtime.respond import respond
from library._core.runtime.llm_prompt import build_prompt, build_fallback_prompt
from library._core.session.continuity import read as read_continuity, load as load_continuity
from library._core.session.state import build_user_profile, update_session
from library._core.session.checkpoint import log as log_checkpoint
from library._core.session.context import assemble as assemble_context
from library.state_store import StateStore
from library.config import get_default_store
from library.utils import timing_context, get_threshold

log = logging.getLogger('mentions')

_DEEP_TRIGGERS = [
    'why', 'почему', 'explain', 'объясни', 'analysis', 'analyze',
    'deep', 'context', 'background', 'trend', 'тренд', 'history',
    'what caused', 'reason', 'причина',
]
_QUICK_TRIGGERS = [
    'quick', 'fast', 'brief', 'snapshot', 'just tell me',
    'what price', 'current price', 'how much',
]

from library._core.runtime.routes import ALL_KB_KEYWORDS as _KB_TRIGGERS


def detect_mode(query: str) -> str:
    """Return 'quick' | 'deep' for the query."""
    q = query.lower()
    if any(t in q for t in _QUICK_TRIGGERS):
        return 'quick'
    if any(t in q for t in _DEEP_TRIGGERS):
        return 'deep'
    if len(q) < get_threshold('detect_mode_short_length', 60):
        return 'quick'
    return 'deep'


def should_use_kb(query: str) -> bool:
    """Return True if the query should trigger data retrieval."""
    q = query.lower()
    return any(t in q for t in _KB_TRIGGERS)


def orchestrate(query: str, user_id: str = 'default',
                store: StateStore | None = None) -> dict:
    """Run the full interactive analysis pipeline.

    Returns a result dict with response text and all metadata.
    """
    query = query or ''
    store = store or get_default_store()

    with timing_context() as timings:
        result = _orchestrate_inner(query, user_id=user_id, store=store)
    result['_timings'] = timings
    return result


def orchestrate_for_llm(query: str, user_id: str = 'default',
                        store: StateStore | None = None) -> dict:
    """Build an LLM-ready prompt bundle for OpenClaw.

    Returns a dict with ``system``, ``user``, ``synthesis``, ``continuity``,
    plus orchestration metadata (``mode``, ``action``).
    """
    query = query or ''
    store = store or get_default_store()

    if not should_use_kb(query):
        return build_fallback_prompt(query, user_id=user_id, store=store)

    mode = detect_mode(query)
    build_user_profile(user_id=user_id, store=store)
    assemble_context(user_id=user_id, store=store)

    try:
        frame = select_frame(query, user_id=user_id, store=store)
        frame['mode'] = mode
    except Exception as exc:
        log.exception('select_frame failed in LLM path: %s', exc)
        return build_fallback_prompt(query, user_id=user_id, store=store)

    try:
        bundle = build_retrieval_bundle(query, frame)
    except Exception as exc:
        log.exception('build_retrieval_bundle failed: %s', exc)
        bundle = {'market': {}, 'transcripts': [], 'news': [], 'has_data': False}

    synth = synthesize(query, frame, bundle)

    prompt = build_prompt(query, frame=frame, bundle=bundle, synthesis=synth,
                          user_id=user_id, store=store)
    prompt['mode'] = mode
    prompt['use_kb'] = True
    prompt['action'] = 'respond-with-data'
    return prompt


def _orchestrate_inner(query: str, user_id: str = 'default',
                       store: StateStore | None = None) -> dict:
    mode = detect_mode(query)

    if not should_use_kb(query):
        return {
            'query': query,
            'mode': mode,
            'use_kb': False,
            'confidence': 'low',
            'action': 'answer-directly',
            'reason': 'Query does not match known market routes.',
            'continuity': read_continuity(user_id=user_id, store=store),
        }

    build_user_profile(user_id=user_id, store=store)

    try:
        frame = select_frame(query, user_id=user_id, store=store)
        frame['mode'] = mode
    except Exception as exc:
        log.exception('select_frame failed: %s', exc)
        return {
            'query': query,
            'mode': mode,
            'use_kb': True,
            'confidence': 'low',
            'action': 'answer-directly',
            'reason': f'Frame selection error: {exc}',
            'continuity': read_continuity(user_id=user_id, store=store),
        }

    try:
        bundle = build_retrieval_bundle(query, frame)
    except Exception as exc:
        log.exception('build_retrieval_bundle failed: %s', exc)
        bundle = {'market': {}, 'transcripts': [], 'news': [], 'has_data': False}

    assemble_context(user_id=user_id, store=store)
    continuity = read_continuity(user_id=user_id, store=store)

    synth = synthesize(query, frame, bundle)
    confidence = synth.get('confidence', 'low')

    route = frame.get('route', 'general-market')
    category = frame.get('category', 'general')

    update_session(
        query,
        route=route,
        category=category,
        mode=mode,
        confidence=confidence,
        user_id=user_id,
        store=store,
    )

    log_checkpoint({
        'query': query,
        'route': route,
        'category': category,
        'mode': mode,
        'confidence': confidence,
        'has_data': bundle.get('has_data', False),
        'sources': bundle.get('sources_used', []),
    }, user_id=user_id, store=store)

    response_text = respond(
        query,
        mode=mode,
        frame=frame,
        synthesis=synth,
        user_id=user_id,
        store=store,
    )

    return {
        'query': query,
        'mode': mode,
        'use_kb': True,
        'confidence': confidence,
        'action': 'respond-with-data',
        'frame': frame,
        'synthesis': synth,
        'continuity': continuity,
        'response': response_text,
        'sources': bundle.get('sources_used', []),
    }
