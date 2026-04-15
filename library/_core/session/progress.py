"""Progress-state estimation for the Mentions agent.

Mirrors Jordan's session/progress.py, adapted for market-analysis context.

Reads the checkpoint log and continuity summary to determine whether the user
is stuck on the same market/topic, making progress (resolved analyses), or in
a fragile/early state.

States
------
stuck    — user has asked about the same topic 3+ times without resolution
moving   — at least one related analysis has been resolved/concluded
fragile  — early or unknown state (default)
"""
from __future__ import annotations

from library.config import get_default_store
from library._core.state_store import (
    StateStore, KEY_CHECKPOINTS, KEY_CONTINUITY_SUMMARY, KEY_PROGRESS_STATE,
)

# Market-domain keywords used to match related checkpoints
_TOPIC_KEYWORDS = [
    'bitcoin', 'btc', 'eth', 'ethereum', 'crypto',
    'fed', 'rate', 'fomc', 'inflation', 'cpi',
    'election', 'president', 'senate', 'house',
    'signal', 'noise', 'movement', 'price',
    'oil', 'gold', 'sp500', 'nasdaq',
]


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

    # -- topic keyword extraction -------------------------------------------
    topic_keywords: list[str] = []
    if query:
        q = query.lower()
        for kw in _TOPIC_KEYWORDS:
            if kw in q:
                topic_keywords.append(kw)

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
    from library.utils import get_threshold
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
