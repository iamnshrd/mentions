"""Market frame selection — determine what kind of analysis is needed.

Given a query, returns the best-fit analysis frame: route, category,
mode, and whether transcript search is warranted.
"""
from __future__ import annotations

import logging

from library._core.runtime.routes import infer_route, route_voice_bias
from library.config import MARKET_CATEGORIES, get_default_store
from library._core.state_store import StateStore
from library.utils import load_json

log = logging.getLogger('mentions')

_categories_cache: list | None = None


def _get_categories() -> list:
    global _categories_cache
    if _categories_cache is None:
        _categories_cache = load_json(MARKET_CATEGORIES, default=[])
    return _categories_cache


def _infer_category(query: str) -> str:
    """Return the best-matching market category id for *query*."""
    q = query.lower()
    best_cat = 'general'
    best_score = 0
    for cat in _get_categories():
        score = sum(1 for kw in cat.get('keywords', []) if kw in q)
        if score > best_score:
            best_score = score
            best_cat = cat['id']
    return best_cat


def _needs_transcript_search(route: str, query: str) -> bool:
    """Determine if transcript corpus search is warranted."""
    transcript_routes = {
        'speaker-history', 'context-research', 'macro',
        'trend-analysis', 'speaker-event',
    }
    if route in transcript_routes:
        return True
    q = query.lower()
    transcript_triggers = [
        'said', 'speech', 'transcript', 'historically', 'in the past',
        'what did', 'quote', 'говорил', 'цитата',
    ]
    return any(t in q for t in transcript_triggers)


def select_frame(query: str, user_id: str = 'default',
                 store: StateStore | None = None) -> dict:
    """Return an analysis frame dict for the given query.

    Uses the LLM intent classifier when available (see
    :func:`library._core.intent.classify_intent`); falls back to the
    keyword-based :func:`infer_route` when the classifier is a no-op.
    Extra fields carried through when the LLM is active:
    ``intent``, ``intent_confidence``, ``intent_source``, ``entities``,
    ``speaker`` (from entities.speaker, promoted for retrieve layer).

    Returns::

        {
            'route': str,
            'category': str,
            'mode': str,
            'voice_bias': str,
            'needs_transcript': bool,
            'query': str,
            # new in v0.5 (phase 4):
            'intent': str,
            'intent_confidence': float,
            'intent_source': 'llm' | 'rules',
            'entities': dict,
            'speaker': str,
        }
    """
    store = store or get_default_store()

    # Intent classification (LLM preferred, rules fallback).
    from library._core.intent import classify_intent
    intent_result = classify_intent(query)

    route = intent_result.route or infer_route(query)
    category = _infer_category(query)
    voice_bias = route_voice_bias(route) or 'analytical'
    needs_transcript = _needs_transcript_search(route, query)
    # A detected speaker entity always warrants transcript search.
    if intent_result.entities.get('speaker'):
        needs_transcript = True

    q = query.lower()
    # Deep mode: explicit depth signals or macro/context routes
    deep_triggers = [
        'why', 'почему', 'explain', 'объясни', 'analysis', 'analyze',
        'deep', 'глубокий', 'context', 'background', 'history',
        'trend', 'тренд',
    ]
    mode = 'deep' if any(t in q for t in deep_triggers) else 'quick'
    if route in {'macro', 'context-research', 'trend-analysis',
                 'speaker-history', 'speaker-event'}:
        mode = 'deep'

    frame = {
        'route': route,
        'category': category,
        'mode': mode,
        'voice_bias': voice_bias,
        'needs_transcript': needs_transcript,
        'query': query,
        'intent':            intent_result.intent,
        'intent_confidence': intent_result.confidence,
        'intent_source':     intent_result.source,
        'entities':          intent_result.entities,
        'speaker':           intent_result.entities.get('speaker', ''),
    }

    log.debug('frame selected: route=%s category=%s mode=%s transcript=%s '
              'intent=%s source=%s conf=%.2f',
              route, category, mode, needs_transcript,
              intent_result.intent, intent_result.source,
              intent_result.confidence)
    return frame
