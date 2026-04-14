"""Continuity state — track recurring markets, routes, and open analyses.

Mirrors Jordan's session/continuity.py, adapted for market context.
"""
from __future__ import annotations

from library.config import get_default_store
from library.state_store import (
    StateStore, KEY_CONTINUITY, KEY_CONTINUITY_SUMMARY,
)
from library.utils import now_iso


def _sort_items(items, key='salience'):
    return sorted(
        items,
        key=lambda x: (
            -x.get(key, 0),
            -x.get('count', 0),
            x.get('name', x.get('summary', '')),
        ),
    )


_DEFAULT: dict = {
    'version': 1,
    'recurring_themes': [],   # markets/categories seen repeatedly
    'user_patterns': [],      # routes used repeatedly (price-movement, macro, etc.)
    'open_loops': [],         # active analyses / tracked markets
    'resolved_loops': [],     # analyses concluded
    'last_updated': None,
}


def load(user_id: str = 'default', store: StateStore | None = None) -> dict:
    """Load continuity, returning defaults when missing."""
    store = store or get_default_store()
    data = store.get_json(user_id, KEY_CONTINUITY)
    if data:
        for key, default_val in _DEFAULT.items():
            if data.get(key) is None:
                data[key] = default_val if not isinstance(default_val, list) else list(default_val)
            else:
                data.setdefault(key, default_val if not isinstance(default_val, list) else list(default_val))
        return data
    return dict(_DEFAULT)


def save(data: dict, user_id: str = 'default',
         store: StateStore | None = None) -> None:
    store = store or get_default_store()
    data['last_updated'] = now_iso()
    store.put_json(user_id, KEY_CONTINUITY, data)


def bump_named(items: list, name: str, salience: int = 1) -> None:
    if not name:
        return
    for item in items:
        if item['name'] == name:
            item['count'] += 1
            item['salience'] += salience
            item['last_seen'] = now_iso()
            return
    items.append({
        'name': name,
        'count': 1,
        'salience': salience,
        'first_seen': now_iso(),
        'last_seen': now_iso(),
    })


def bump_loop(items: list, summary: str, salience: int = 1,
              status: str = 'open') -> None:
    if not summary:
        return
    for item in items:
        if item['summary'] == summary:
            item['count'] += 1
            item['salience'] += salience
            item['status'] = status
            item['last_seen'] = now_iso()
            return
    items.append({
        'summary': summary,
        'status': status,
        'count': 1,
        'salience': salience,
        'first_seen': now_iso(),
        'last_seen': now_iso(),
    })


def update(query: str, route: str = '', category: str = '',
           open_loop: str = '', resolved_loop: str = '',
           user_id: str = 'default',
           store: StateStore | None = None) -> dict:
    """Full continuity update cycle — returns the updated data dict."""
    data = load(user_id=user_id, store=store)
    bump_named(data['recurring_themes'], category, 2 if category else 1)
    bump_named(data['user_patterns'], route, 2 if route else 1)
    if open_loop:
        bump_loop(data['open_loops'], open_loop)
    if resolved_loop:
        _resolve_loop(data, resolved_loop)
    save(data, user_id=user_id, store=store)
    return data


def _resolve_loop(data: dict, summary: str) -> None:
    for item in data.get('open_loops', []):
        if item['summary'] == summary:
            item['status'] = 'resolved'
            item['last_seen'] = now_iso()
            data.setdefault('resolved_loops', []).append(item)
            data['open_loops'] = [
                x for x in data['open_loops'] if x['summary'] != summary
            ]
            return


def read(user_id: str = 'default',
         store: StateStore | None = None) -> dict:
    """Return continuity with top-5 sorted slices per bucket."""
    store = store or get_default_store()
    data = store.get_json(user_id, KEY_CONTINUITY)
    summary = store.get_json(user_id, KEY_CONTINUITY_SUMMARY)
    data_ts = data.get('last_updated', '')
    summary_ts = summary.get('last_updated', '')
    if data_ts and data_ts > summary_ts:
        return summarize(user_id=user_id, store=store)
    if summary and summary.get('top_themes') is not None:
        return summary
    return {
        'top_themes': _sort_items(data.get('recurring_themes', []))[:5],
        'top_patterns': _sort_items(data.get('user_patterns', []))[:5],
        'open_loops': _sort_items(data.get('open_loops', []))[:5],
        'resolved_loops': _sort_items(data.get('resolved_loops', []))[:5],
        'last_updated': data.get('last_updated'),
    }


def summarize(user_id: str = 'default',
              store: StateStore | None = None) -> dict:
    store = store or get_default_store()
    data = store.get_json(user_id, KEY_CONTINUITY)
    summary = {
        'top_themes': _sort_items(data.get('recurring_themes', []))[:5],
        'top_patterns': _sort_items(data.get('user_patterns', []))[:5],
        'open_loops': _sort_items(data.get('open_loops', []))[:5],
        'resolved_loops': _sort_items(data.get('resolved_loops', []))[:5],
        'last_updated': data.get('last_updated'),
    }
    store.put_json(user_id, KEY_CONTINUITY_SUMMARY, summary)
    return summary
