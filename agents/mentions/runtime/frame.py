"""Market frame selection — determine what kind of analysis is needed.

Given a query, returns the best-fit analysis frame: route, category,
mode, and whether transcript search is warranted.
"""
from __future__ import annotations

import logging

from agents.mentions.runtime.routes import infer_route, route_voice_bias
from agents.mentions.config import MARKET_CATEGORIES, get_default_store
from mentions_core.base.state_store import StateStore
from agents.mentions.utils import load_json

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

    Returns::

        {
            'route': str,          # e.g. 'price-movement'
            'category': str,       # e.g. 'crypto'
            'mode': str,           # 'quick' | 'deep'
            'voice_bias': str,     # from route
            'needs_transcript': bool,
            'query': str,
        }
    """
    store = store or get_default_store()

    route = infer_route(query)
    category = _infer_category(query)
    voice_bias = route_voice_bias(route) or 'analytical'
    needs_transcript = _needs_transcript_search(route, query)

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
    }

    log.debug('frame selected: route=%s category=%s mode=%s transcript=%s',
              route, category, mode, needs_transcript)
    return frame
