"""Continuity state — track recurring markets, routes, and open analyses.

Schema v4 adds market-domain intent and entity buckets:
  - ``intents``  — tally of classified intents
  - ``speakers`` — named speakers referenced
  - ``tickers``  — Kalshi tickers referenced
"""
from __future__ import annotations

import copy

from mentions_core.base.config import get_default_store
from mentions_core.base.state_store import (
    StateStore, KEY_CONTINUITY, KEY_CONTINUITY_SUMMARY,
)
from mentions_core.base.utils import now_iso


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
    'version': 4,
    'recurring_themes': [],   # markets/categories seen repeatedly
    'user_patterns': [],      # routes used repeatedly (price-movement, macro, etc.)
    'open_loops': [],         # active analyses / tracked markets
    'resolved_loops': [],     # analyses concluded
    'macro_loops': [],        # macro/fed/rate recurring threads
    'crypto_loops': [],       # crypto-specific recurring threads
    'intents': [],            # classified intent frequencies
    'speakers': [],           # named speakers referenced
    'tickers': [],            # Kalshi tickers referenced
    'last_updated': None,
}

# Keys that are lists in the schema
_LIST_KEYS = frozenset({
    'recurring_themes', 'user_patterns', 'open_loops', 'resolved_loops',
    'macro_loops', 'crypto_loops', 'intents', 'speakers', 'tickers',
})

# Category → domain bucket mapping
_MACRO_CATEGORIES  = frozenset({'macro', 'politics', 'finance', 'geopolitics'})
_CRYPTO_CATEGORIES = frozenset({'crypto'})


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migrate(data: dict) -> dict:
    """Upgrade data to the latest schema version in-place."""
    version = data.get('version', 1)
    if version < 3:
        for key in ('macro_loops', 'crypto_loops'):
            if key not in data:
                data[key] = []
        data['version'] = 3
        version = 3

    if version < 4:
        for key in ('intents', 'speakers', 'tickers'):
            if key not in data:
                data[key] = []
        data['version'] = 4
    return data


# ---------------------------------------------------------------------------
# Core I/O
# ---------------------------------------------------------------------------

def load(user_id: str = 'default', store: StateStore | None = None) -> dict:
    """Load continuity, migrate to the latest schema, returning defaults when missing."""
    store = store or get_default_store()
    data = store.get_json(user_id, KEY_CONTINUITY)
    if data:
        data = _migrate(data)
        # Ensure all expected keys exist
        for key, default_val in _DEFAULT.items():
            if data.get(key) is None:
                data[key] = list(default_val) if isinstance(default_val, list) else default_val
            else:
                if isinstance(default_val, list) and not isinstance(data[key], list):
                    data[key] = []
        return data
    return copy.deepcopy(_DEFAULT)


def save(data: dict, user_id: str = 'default',
         store: StateStore | None = None) -> None:
    store = store or get_default_store()
    data['last_updated'] = now_iso()
    store.put_json(user_id, KEY_CONTINUITY, data)


# ---------------------------------------------------------------------------
# Bump helpers
# ---------------------------------------------------------------------------

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


def _route_bucket(data: dict, category: str) -> list | None:
    """Return the domain-specific loop bucket for *category*, or None."""
    if category in _MACRO_CATEGORIES:
        return data.get('macro_loops')
    if category in _CRYPTO_CATEGORIES:
        return data.get('crypto_loops')
    return None


# ---------------------------------------------------------------------------
# Update cycle
# ---------------------------------------------------------------------------

def update(query: str, route: str = '', category: str = '',
           open_loop: str = '', resolved_loop: str = '',
           intent: str = '', speaker: str = '', ticker: str = '',
           user_id: str = 'default',
           store: StateStore | None = None) -> dict:
    """Full continuity update cycle — returns the updated data dict."""
    data = load(user_id=user_id, store=store)
    bump_named(data['recurring_themes'], category, 2 if category else 1)
    bump_named(data['user_patterns'], route, 2 if route else 1)
    if open_loop:
        bump_loop(data['open_loops'], open_loop)
        # Also bump domain bucket if applicable
        bucket = _route_bucket(data, category)
        if bucket is not None:
            bump_loop(bucket, open_loop)
    if resolved_loop:
        _resolve_loop(data, resolved_loop)
    if intent:
        bump_named(data['intents'], intent)
    if speaker:
        bump_named(data['speakers'], speaker)
    if ticker:
        bump_named(data['tickers'], ticker)
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


# ---------------------------------------------------------------------------
# Read / summarize
# ---------------------------------------------------------------------------

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
    return _build_summary_dict(data)


def summarize(user_id: str = 'default',
              store: StateStore | None = None) -> dict:
    store = store or get_default_store()
    data = store.get_json(user_id, KEY_CONTINUITY)
    summary = _build_summary_dict(data)
    store.put_json(user_id, KEY_CONTINUITY_SUMMARY, summary)
    return summary


def _build_summary_dict(data: dict) -> dict:
    return {
        'top_themes':    _sort_items(data.get('recurring_themes', []))[:5],
        'top_patterns':  _sort_items(data.get('user_patterns',    []))[:5],
        'open_loops':    _sort_items(data.get('open_loops',       []))[:5],
        'resolved_loops': _sort_items(data.get('resolved_loops',  []))[:5],
        'macro_loops':   _sort_items(data.get('macro_loops',      []))[:5],
        'crypto_loops':  _sort_items(data.get('crypto_loops',     []))[:5],
        'top_intents':   _sort_items(data.get('intents',          []))[:5],
        'top_speakers':  _sort_items(data.get('speakers',         []))[:5],
        'top_tickers':   _sort_items(data.get('tickers',          []))[:5],
        'last_updated':  data.get('last_updated'),
    }
