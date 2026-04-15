"""Context-graph assembly for the Mentions agent.

Builds a lightweight context graph from continuity and session state,
linking tracked markets to analysis routes and source effectiveness.
"""
from __future__ import annotations

from mentions_core.base.config import get_default_store
from mentions_core.base.state_store import (
    StateStore, KEY_CONTINUITY, KEY_SESSION_STATE,
    KEY_EFFECTIVENESS, KEY_CONTEXT_GRAPH,
)


def assemble(user_id: str = 'default',
             store: StateStore | None = None) -> dict:
    """Build context graph from continuity, session state, and effectiveness.

    Writes context_graph and returns the graph dict.
    """
    store = store or get_default_store()
    cont = store.get_json(user_id, KEY_CONTINUITY)
    session = store.get_json(user_id, KEY_SESSION_STATE)
    effect = store.get_json(user_id, KEY_EFFECTIVENESS)

    graph: dict = {
        'market_links': [],
        'route_links': [],
        'source_links': [],
        'session': session,
    }

    markets = [
        x.get('name')
        for x in (cont.get('recurring_themes') or [])[:5]
        if isinstance(x, dict)
    ]
    routes = [
        x.get('name')
        for x in (cont.get('user_patterns') or [])[:5]
        if isinstance(x, dict)
    ]

    for m in markets:
        for r in routes:
            graph['market_links'].append({'market': m, 'route': r})

    current_route = session.get('working_route', '')
    if current_route:
        graph['route_links'].append({
            'route': current_route,
            'times_used': (
                effect
                .get('routes', {})
                .get(current_route, {})
                .get('times_used', 0)
            ),
        })

    store.put_json(user_id, KEY_CONTEXT_GRAPH, graph)
    return graph
