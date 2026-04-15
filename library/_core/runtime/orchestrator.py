"""Runtime orchestrator — coordinate all runtime modules via direct imports.

Supports three modes:
- Interactive (text query): user query → analysis response
- URL (Kalshi link):        URL → speaker event market analysis
- Autonomous:               no user query → scan top movers → dashboard output
"""
from __future__ import annotations

import logging

from library._core.runtime.frame import select_frame
from library._core.runtime.retrieve import build_retrieval_bundle
from library._core.runtime.synthesize import synthesize
from library._core.runtime.respond import respond
from library._core.runtime.llm_prompt import build_prompt, build_fallback_prompt
from library._core.session.continuity import read as read_continuity
from library._core.session.state import build_user_profile, update_session
from library._core.session.checkpoint import log as log_checkpoint
from library._core.session.context import assemble as assemble_context
from library._core.session.progress import estimate as estimate_progress
from library._core.state_store import StateStore
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


def _is_kalshi_url(query: str) -> bool:
    """Return True if *query* looks like a Kalshi market URL."""
    q = query.strip()
    return q.startswith('https://') and 'kalshi.com' in q


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


# ── Public entry points ────────────────────────────────────────────────────

def orchestrate(query: str, user_id: str = 'default',
                store: StateStore | None = None) -> dict:
    """Run the full interactive analysis pipeline.

    Auto-detects Kalshi URLs and routes to ``orchestrate_url()`` when found.
    Returns a result dict with response text and all metadata.
    """
    query = query or ''
    store = store or get_default_store()

    # Auto-detect: if the query is a Kalshi URL, use the URL pipeline
    if _is_kalshi_url(query):
        return orchestrate_url(query, user_id=user_id, store=store)

    with timing_context() as timings:
        result = _orchestrate_inner(query, user_id=user_id, store=store)
    result['_timings'] = timings
    return result


def orchestrate_url(url: str, user_id: str = 'default',
                    store: StateStore | None = None) -> dict:
    """URL-triggered speaker event market analysis.

    Parses a Kalshi market URL, fetches all relevant data, and produces a
    full structured trade brief (event context, speaker tendency, trade params).

    Returns a result dict compatible with the standard ``orchestrate()`` shape,
    plus ``synthesis.speaker``, ``synthesis.event_context``, and
    ``synthesis.trade_params``.
    """
    url = (url or '').strip()
    store = store or get_default_store()

    with timing_context() as timings:
        result = _orchestrate_url_inner(url, user_id=user_id, store=store)
    result['_timings'] = timings
    return result


def orchestrate_for_llm(query: str, user_id: str = 'default',
                        store: StateStore | None = None) -> dict:
    """Build an LLM-ready prompt bundle for OpenClaw.

    Returns a dict with ``system``, ``user``, ``synthesis``, ``continuity``,
    ``progress``, plus orchestration metadata (``mode``, ``action``).
    """
    query = query or ''
    store = store or get_default_store()

    # URL path: return speaker synthesis directly (no LLM prompt wrapping needed)
    if _is_kalshi_url(query):
        result = orchestrate_url(query, user_id=user_id, store=store)
        result['action'] = 'respond-with-data'
        result['mode']   = 'deep'
        return result

    if not should_use_kb(query):
        return build_fallback_prompt(query, user_id=user_id, store=store)

    mode = detect_mode(query)
    build_user_profile(user_id=user_id, store=store)
    progress = estimate_progress(query, user_id=user_id, store=store)
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
    prompt['mode']     = mode
    prompt['use_kb']   = True
    prompt['action']   = 'respond-with-data'
    prompt['progress'] = progress
    return prompt


# ── Internal pipelines ─────────────────────────────────────────────────────

def _orchestrate_url_inner(url: str, user_id: str = 'default',
                            store: StateStore | None = None) -> dict:
    """Core URL analysis pipeline — speaker event market."""
    from library._core.fetch.url_parser import parse_kalshi_url
    from library._core.runtime.retrieve import retrieve_by_ticker
    from library._core.runtime.synthesize_speaker import synthesize_speaker_market

    # ── Parse URL ──────────────────────────────────────────────────────────
    url_info = parse_kalshi_url(url)
    ticker   = url_info.get('ticker', '')

    if not ticker:
        log.warning('Could not extract ticker from URL: %s', url)
        return {
            'url': url,
            'error': 'Could not extract market ticker from URL.',
            'action': 'answer-directly',
            'confidence': 'low',
        }

    # ── Retrieve all data ──────────────────────────────────────────────────
    speaker_slug = url_info.get('speaker_slug', '')
    speaker_info = url_info.get('speaker_info', {})
    speaker_name = speaker_info.get('name', speaker_slug)

    bundle = retrieve_by_ticker(ticker, speaker=speaker_name)

    market_data = bundle.get('market', {}).get('market_data', {})
    transcripts = bundle.get('transcripts', [])
    news        = bundle.get('news', [])

    # ── Speaker event synthesis ────────────────────────────────────────────
    synth = synthesize_speaker_market(
        ticker=ticker,
        market_data=market_data,
        transcripts=transcripts,
        news=news,
        url_info=url_info,
    )

    confidence = synth.get('confidence', 'low')

    # ── Session updates ────────────────────────────────────────────────────
    build_user_profile(user_id=user_id, store=store)
    progress = estimate_progress(ticker, user_id=user_id, store=store)
    assemble_context(user_id=user_id, store=store)
    continuity = read_continuity(user_id=user_id, store=store)

    update_session(
        ticker,
        route='speaker-event',
        category=speaker_info.get('domain', 'general'),
        mode='deep',
        confidence=confidence,
        user_id=user_id,
        store=store,
    )

    log_checkpoint({
        'query':           url,
        'ticker':          ticker,
        'route':           'speaker-event',
        'speaker':         speaker_name,
        'confidence':      confidence,
        'has_data':        bundle.get('has_data', False),
        'sources':         bundle.get('sources_used', []),
        'progress_state':  progress.get('progress_state', 'fragile'),
        'stuckness_score': progress.get('stuckness_score', 0),
    }, user_id=user_id, store=store)

    return {
        'url':        url,
        'ticker':     ticker,
        'mode':       'deep',
        'route':      'speaker-event',
        'confidence': confidence,
        'action':     'respond-with-data',
        'synthesis':  synth,
        'continuity': continuity,
        'progress':   progress,
        'sources':    bundle.get('sources_used', []),
    }


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
    progress = estimate_progress(query, user_id=user_id, store=store)

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

    route    = frame.get('route', 'general-market')
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
        'query':           query,
        'route':           route,
        'category':        category,
        'mode':            mode,
        'confidence':      confidence,
        'has_data':        bundle.get('has_data', False),
        'sources':         bundle.get('sources_used', []),
        'progress_state':  progress.get('progress_state', 'fragile'),
        'stuckness_score': progress.get('stuckness_score', 0),
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
        'query':      query,
        'mode':       mode,
        'use_kb':     True,
        'confidence': confidence,
        'action':     'respond-with-data',
        'frame':      frame,
        'synthesis':  synth,
        'continuity': continuity,
        'progress':   progress,
        'response':   response_text,
        'sources':    bundle.get('sources_used', []),
    }
