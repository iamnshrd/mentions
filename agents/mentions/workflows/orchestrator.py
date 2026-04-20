"""Canonical workflow entrypoint for orchestration."""
from __future__ import annotations

import logging

from agents.mentions.trace import new_run_id, trace_log
from agents.mentions.module_registry import (
    get_analysis_engine,
    get_frame_selector,
    get_response_renderer,
    get_retrieval_bundle_builder,
    get_ticker_retriever,
)
from agents.mentions.workflows.llm_prompt import build_prompt, build_fallback_prompt
from agents.mentions.workflows.routes import ALL_KB_KEYWORDS as _KB_TRIGGERS
from mentions_core.base.session.continuity import read as read_continuity
from mentions_core.base.session.state import build_user_profile, update_session
from mentions_core.base.session.checkpoint import log as log_checkpoint
from mentions_core.base.session.context import assemble as assemble_context
from mentions_core.base.session.progress import estimate as estimate_progress
from mentions_core.base.state_store import StateStore
from agents.mentions.config import get_default_store
from agents.mentions.utils import timing_context, get_threshold

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


def _is_kalshi_url(query: str) -> bool:
    q = query.strip()
    return q.startswith('https://') and 'kalshi.com' in q


def detect_mode(query: str) -> str:
    q = query.lower()
    if any(t in q for t in _QUICK_TRIGGERS):
        return 'quick'
    if any(t in q for t in _DEEP_TRIGGERS):
        return 'deep'
    if len(q) < get_threshold('detect_mode_short_length', 60):
        return 'quick'
    return 'deep'


def should_use_kb(query: str) -> bool:
    q = query.lower()
    return any(t in q for t in _KB_TRIGGERS)


def orchestrate(query: str, user_id: str = 'default',
                store: StateStore | None = None) -> dict:
    run_id = new_run_id()
    query = query or ''
    store = store or get_default_store()
    trace_log('orchestrator.start', run_id=run_id, query=query, user_id=user_id, is_url=_is_kalshi_url(query))
    if _is_kalshi_url(query):
        return orchestrate_url(query, user_id=user_id, store=store, run_id=run_id)
    with timing_context() as timings:
        result = _orchestrate_inner(query, user_id=user_id, store=store)
    result['_timings'] = timings
    trace_log('orchestrator.finish', run_id=run_id, query=query, action=result.get('action', ''), confidence=result.get('confidence', ''), has_data=result.get('has_data', False) if isinstance(result, dict) else False)
    return result


def orchestrate_url(url: str, user_id: str = 'default',
                    store: StateStore | None = None, run_id: str = '') -> dict:
    url = (url or '').strip()
    store = store or get_default_store()
    run_id = run_id or new_run_id()
    trace_log('orchestrator.url.start', run_id=run_id, url=url, user_id=user_id)
    with timing_context() as timings:
        result = _orchestrate_url_inner(url, user_id=user_id, store=store, run_id=run_id)
    result['_timings'] = timings
    trace_log('orchestrator.url.finish', run_id=run_id, url=url, ticker=result.get('ticker', ''), confidence=result.get('confidence', ''), has_data=result.get('has_data', False))
    return result


def _resolve_frame_and_bundle(query: str, user_id: str, store, mode: str) -> tuple[dict | None, dict, dict]:
    build_user_profile(user_id=user_id, store=store)
    progress = estimate_progress(query, user_id=user_id, store=store)
    assemble_context(user_id=user_id, store=store)
    try:
        frame = get_frame_selector()(query, user_id=user_id, store=store)
        frame['mode'] = mode
    except Exception as exc:
        log.exception('select_frame failed: %s', exc)
        return None, {'market': {}, 'transcripts': [], 'news': [], 'has_data': False}, progress
    try:
        bundle = get_retrieval_bundle_builder()(query, frame)
    except Exception as exc:
        log.exception('build_retrieval_bundle failed: %s', exc)
        bundle = {'market': {}, 'transcripts': [], 'news': [], 'has_data': False}
    return frame, bundle, progress


def _text_use_case(query: str, user_id: str, store, mode: str) -> tuple[dict | None, dict, dict, dict]:
    frame, bundle, progress = _resolve_frame_and_bundle(query, user_id=user_id, store=store, mode=mode)
    if frame is None:
        return None, bundle, progress, {}
    synth = get_analysis_engine()(query, frame, bundle)
    return frame, bundle, progress, synth


def _url_use_case(url: str, run_id: str) -> tuple[dict, dict, str, dict, str, dict]:
    from agents.mentions.services.intake.url_parser import parse_kalshi_url
    from agents.mentions.workflows.synthesize_speaker import synthesize_speaker_market

    url_info = parse_kalshi_url(url)
    ticker = url_info.get('ticker', '')
    trace_log('orchestrator.url.parsed', run_id=run_id, url=url, ticker=ticker, speaker_slug=url_info.get('speaker_slug', ''))

    if not ticker:
        return url_info, {}, '', {}, '', {}

    speaker_slug = url_info.get('speaker_slug', '')
    speaker_info = url_info.get('speaker_info', {})
    speaker_name = speaker_info.get('name', speaker_slug)

    ticker_kind = url_info.get('ticker_kind', 'unknown')
    bundle = get_ticker_retriever()(ticker, speaker=speaker_name, ticker_kind=ticker_kind)
    trace_log('orchestrator.url.bundle', run_id=run_id, ticker=ticker, ticker_kind=ticker_kind, has_data=bundle.get('has_data', False), sources=bundle.get('sources_used', []), news_count=len(bundle.get('news', [])), transcript_count=len(bundle.get('transcripts', [])))

    market_data = bundle.get('market', {}).get('market_data', {})
    trace_log('orchestrator.url.post_retrieval', run_id=run_id, ticker=ticker, market_title=market_data.get('title', '') if isinstance(market_data, dict) else '', has_market=bool(market_data), has_transcripts=bool(bundle.get('transcripts', [])), has_news=bool(bundle.get('news', [])))
    transcripts = bundle.get('transcripts', [])
    news = bundle.get('news', [])
    bundle_market = bundle.get('market', {})

    transcript_bundle = bundle.get('transcript_intelligence', {})
    if isinstance(transcript_bundle, dict) and run_id:
        transcript_bundle.setdefault('run_id', run_id)
    trace_log('orchestrator.url.pre_synthesis', run_id=run_id, ticker=ticker, transcript_candidates=len(transcript_bundle.get('top_candidates', [])) if isinstance(transcript_bundle, dict) else 0, news_count=len(news))
    synth = synthesize_speaker_market(
        ticker=ticker,
        market_data=market_data,
        transcripts=transcripts,
        news=news,
        url_info=url_info,
        transcript_bundle=transcript_bundle,
    )
    trace_log('orchestrator.url.synthesized', run_id=run_id, ticker=ticker, confidence=synth.get('confidence', ''), analysis_confidence=synth.get('analysis_confidence', ''))
    if isinstance(bundle_market, dict):
        synth['bundle_market'] = bundle_market
        synth['news_bundle'] = bundle.get('news_context', {})
        synth['transcript_bundle'] = bundle.get('transcript_intelligence', {})
        synth['speaker_event_context'] = bundle.get('speaker_event_context', {})

    return url_info, bundle, ticker, synth, speaker_name, speaker_info


def _direct_answer_result(*, query: str, mode: str, reason: str, user_id: str, store) -> dict:
    return {
        'query': query,
        'mode': mode,
        'use_kb': False,
        'confidence': 'low',
        'action': 'answer-directly',
        'reason': reason,
        'continuity': read_continuity(user_id=user_id, store=store),
    }


def _success_result(*, query: str, mode: str, confidence: str, frame: dict,
                    synthesis: dict, continuity: dict, progress: dict,
                    response_text: str, bundle: dict) -> dict:
    return {
        'query': query,
        'mode': mode,
        'use_kb': True,
        'confidence': confidence,
        'action': 'respond-with-data',
        'frame': frame,
        'synthesis': synthesis,
        'continuity': continuity,
        'progress': progress,
        'response': response_text,
        'sources': bundle.get('sources_used', []),
    }


def _url_success_result(*, url: str, ticker: str, confidence: str, synthesis: dict,
                        continuity: dict, progress: dict, bundle: dict) -> dict:
    return {
        'url': url,
        'ticker': ticker,
        'mode': 'deep',
        'route': 'speaker-event',
        'confidence': confidence,
        'action': 'respond-with-data',
        'synthesis': synthesis,
        'continuity': continuity,
        'progress': progress,
        'sources': bundle.get('sources_used', []),
        'has_data': bundle.get('has_data', False),
    }


def _record_turn_state(*, query: str, route: str, category: str, mode: str,
                       confidence: str, has_data: bool, sources: list,
                       progress: dict, user_id: str, store, extra: dict | None = None) -> None:
    update_session(
        query,
        route=route,
        category=category,
        mode=mode,
        confidence=confidence,
        user_id=user_id,
        store=store,
    )
    payload = {
        'query': query,
        'route': route,
        'category': category,
        'mode': mode,
        'confidence': confidence,
        'has_data': has_data,
        'sources': sources,
        'progress_state': progress.get('progress_state', 'fragile'),
        'stuckness_score': progress.get('stuckness_score', 0),
    }
    if extra:
        payload.update(extra)
    log_checkpoint(payload, user_id=user_id, store=store)


def _llm_prompt_result(*, prompt: dict, mode: str, progress: dict) -> dict:
    prompt['mode'] = mode
    prompt['use_kb'] = True
    prompt['action'] = 'respond-with-data'
    prompt['progress'] = progress
    return prompt


def _frame_error_result(*, query: str, mode: str, user_id: str, store) -> dict:
    return {
        'query': query,
        'mode': mode,
        'use_kb': True,
        'confidence': 'low',
        'action': 'answer-directly',
        'reason': 'Frame selection error.',
        'continuity': read_continuity(user_id=user_id, store=store),
    }


def orchestrate_for_llm(query: str, user_id: str = 'default',
                        store: StateStore | None = None) -> dict:
    query = query or ''
    store = store or get_default_store()

    result = orchestrate(query, user_id=user_id, store=store)
    result['action'] = 'respond-with-data' if result.get('use_kb', True) else result.get('action', 'answer-directly')
    result['mode'] = result.get('mode', detect_mode(query))
    return result


def _orchestrate_url_inner(url: str, user_id: str = 'default',
                           store: StateStore | None = None, run_id: str = '') -> dict:
    url_info, bundle, ticker, synth, speaker_name, speaker_info = _url_use_case(url, run_id=run_id)

    if not ticker:
        log.warning('Could not extract ticker from URL: %s', url)
        return {
            'url': url,
            'error': 'Could not extract market ticker from URL.',
            'action': 'answer-directly',
            'confidence': 'low',
        }

    confidence = synth.get('confidence', 'low')

    build_user_profile(user_id=user_id, store=store)
    progress = estimate_progress(ticker, user_id=user_id, store=store)
    assemble_context(user_id=user_id, store=store)
    continuity = read_continuity(user_id=user_id, store=store)

    _record_turn_state(
        query=ticker,
        route='speaker-event',
        category=speaker_info.get('domain', 'general'),
        mode='deep',
        confidence=confidence,
        has_data=bundle.get('has_data', False),
        sources=bundle.get('sources_used', []),
        progress=progress,
        user_id=user_id,
        store=store,
        extra={'ticker': ticker, 'speaker': speaker_name},
    )

    result = _url_success_result(
        url=url,
        ticker=ticker,
        confidence=confidence,
        synthesis=synth,
        continuity=continuity,
        progress=progress,
        bundle=bundle,
    )
    trace_log('orchestrator.url.result', run_id=run_id, ticker=ticker, rendered_len=len(synth.get('analysis_report', '') or ''), sources=result.get('sources', []))
    return result


def _orchestrate_inner(query: str, user_id: str = 'default',
                       store: StateStore | None = None) -> dict:
    mode = detect_mode(query)

    if not should_use_kb(query):
        return _direct_answer_result(
            query=query,
            mode=mode,
            reason='Query does not match known market routes.',
            user_id=user_id,
            store=store,
        )

    frame, bundle, progress, synth = _text_use_case(query, user_id=user_id, store=store, mode=mode)
    if frame is None:
        return _frame_error_result(query=query, mode=mode, user_id=user_id, store=store)

    continuity = read_continuity(user_id=user_id, store=store)
    confidence = synth.get('confidence', 'low')

    route = frame.get('route', 'general-market')
    category = frame.get('category', 'general')

    _record_turn_state(
        query=query,
        route=route,
        category=category,
        mode=mode,
        confidence=confidence,
        has_data=bundle.get('has_data', False),
        sources=bundle.get('sources_used', []),
        progress=progress,
        user_id=user_id,
        store=store,
    )

    response_text = get_response_renderer()(
        query,
        mode=mode,
        frame=frame,
        synthesis=synth,
        user_id=user_id,
        store=store,
    )

    return _success_result(
        query=query,
        mode=mode,
        confidence=confidence,
        frame=frame,
        synthesis=synth,
        continuity=continuity,
        progress=progress,
        response_text=response_text,
        bundle=bundle,
    )


__all__ = [
    'detect_mode',
    'orchestrate',
    'orchestrate_for_llm',
    'orchestrate_url',
    'should_use_kb',
]
