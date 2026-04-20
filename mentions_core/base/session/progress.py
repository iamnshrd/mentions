"""Generic progress-state estimation for OpenClaw sessions.

Reads the checkpoint log and continuity summary to determine whether the user
is stuck on the same topic, making progress (resolved loops), or in a
fragile/early state.

States
------
stuck    — user has asked about the same topic 3+ times without resolution
moving   — at least one related analysis has been resolved/concluded
fragile  — early or unknown state (default)
"""
from __future__ import annotations

from mentions_core.base.config import get_default_store
from mentions_core.base.state_store import (
    StateStore, KEY_CHECKPOINTS, KEY_CONTINUITY_SUMMARY, KEY_PROGRESS_STATE,
)

_STOP_WORDS = {
    'with', 'that', 'this', 'from', 'what', 'when', 'where', 'which',
    'about', 'into', 'just', 'will', 'would', 'could', 'should', 'than',
    'have', 'has', 'had', 'your', 'their', 'there', 'then', 'them',
}


def _extract_topic_keywords(query: str) -> list[str]:
    import re

    return [
        token
        for token in re.findall(r'[a-z0-9][a-z0-9_-]{2,}', query.lower())
        if token not in _STOP_WORDS
    ][:8]


def estimate(query: str = '', user_id: str = 'default',
             store: StateStore | None = None) -> dict:
    """Compute progress state from checkpoints + continuity summary.

    Writes ``progress_state`` to the store and returns the result dict.

    Returns
    -------
    dict with keys:
        query, repeat_count, resolved_count, stuckness_score,
        progress_state ('stuck' | 'moving' | 'fragile'),
        recommended_response_mode ('narrow' | 'normal')
    """
    store = store or get_default_store()
    checkpoints = store.read_jsonl(user_id, KEY_CHECKPOINTS)
    cont = store.get_json(user_id, KEY_CONTINUITY_SUMMARY)

    topic_keywords = _extract_topic_keywords(query) if query else []

    # -- find checkpoints related to this query / topic ---------------------
    if query:
        same: list[dict] = [c for c in checkpoints if c.get('query') == query]
        if not same and topic_keywords:
            for c in checkpoints:
                cq = (c.get('query') or '').lower()
                if any(kw in cq for kw in topic_keywords):
                    same.append(c)
    else:
        # No specific query — look at the last few entries
        same = checkpoints[-3:]

    repeat_count = len(same)

    # -- count resolved loops related to the topic --------------------------
    all_resolved = cont.get('resolved_loops') or []
    if topic_keywords:
        resolved_count = sum(
            1 for r in all_resolved
            if isinstance(r, dict) and any(
                kw in (r.get('summary') or '').lower()
                for kw in topic_keywords
            )
        )
    elif repeat_count > 0:
        recent_resolved = all_resolved[-3:] if all_resolved else []
        resolved_count = len(recent_resolved)
    else:
        resolved_count = 0

    stuckness_score = max(0, repeat_count * 2 - resolved_count)

    # -- determine state ----------------------------------------------------
    from mentions_core.base.utils import get_threshold
    stuck_threshold = get_threshold('progress_repeat_stuck_threshold', 3)

    if repeat_count >= stuck_threshold and resolved_count == 0:
        state = 'stuck'
    elif resolved_count >= 1:
        state = 'moving'
    else:
        state = 'fragile'

    out = {
        'query': query,
        'repeat_count': repeat_count,
        'resolved_count': resolved_count,
        'stuckness_score': stuckness_score,
        'progress_state': state,
        'recommended_response_mode': 'narrow' if state == 'stuck' else 'normal',
    }
    store.put_json(user_id, KEY_PROGRESS_STATE, out)
    return out
