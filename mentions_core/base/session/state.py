"""Session state & user profile for the Mentions agent."""
from __future__ import annotations

from mentions_core.base.config import get_default_store
from mentions_core.base.state_store import (
    StateStore, KEY_SESSION_STATE, KEY_USER_STATE, KEY_CONTINUITY,
)
from mentions_core.base.utils import now_iso


def update_session(query: str, route: str = '', category: str = '',
                   mode: str = 'deep', confidence: str = 'low',
                   intent: str = '', intent_confidence: float = 0.0,
                   intent_source: str = '',
                   speaker: str = '', ticker: str = '',
                   user_id: str = 'default',
                   store: StateStore | None = None) -> dict:
    """Write session_state with the current turn context.
    """
    store = store or get_default_store()
    data = {
        'query': query,
        'working_route': route,
        'working_category': category,
        'current_mode': mode,
        'last_confidence': confidence,
        'last_intent': intent,
        'last_intent_confidence': float(intent_confidence or 0.0),
        'last_intent_source': intent_source,
        'last_speaker': speaker,
        'last_ticker': ticker,
        'updated_at': now_iso(),
    }
    store.put_json(user_id, KEY_SESSION_STATE, data)
    return data


def _top_name(items):
    dicts = [x for x in items if isinstance(x, dict)]
    if not dicts:
        return None
    dicts = sorted(
        dicts,
        key=lambda x: (-x.get('salience', 0), -x.get('count', 0)),
    )
    return dicts[0].get('name') or dicts[0].get('summary')


def build_user_profile(user_id: str = 'default',
                       store: StateStore | None = None) -> dict:
    """Derive user_state from continuity. Returns the profile dict."""
    store = store or get_default_store()
    data = store.get_json(user_id, KEY_CONTINUITY)
    open_loops = data.get('open_loops') or []
    recurring_themes = data.get('recurring_themes') or []
    user_patterns = data.get('user_patterns') or []

    profile = {
        'dominant_market': _top_name(recurring_themes),
        'dominant_route': _top_name(user_patterns),
        'active_analyses': len(open_loops),
        'preferred_mode': (
            'deep'
            if _top_name(user_patterns) in ('macro', 'context-research', 'trend-analysis')
            else 'quick'
        ),
    }
    store.put_json(user_id, KEY_USER_STATE, profile)
    return profile
