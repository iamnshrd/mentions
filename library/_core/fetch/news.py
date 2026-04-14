"""News context fetcher.

Fetches recent headlines relevant to a market category or query.
Currently a lightweight stub — returns cached DB results when available,
falls back to empty list when no news source is configured.

Extend this module to plug in a real news API (e.g. NewsAPI, GDELT, etc.).
"""
from __future__ import annotations

import logging

from library.utils import now_iso

log = logging.getLogger('mentions')


def fetch_news(query: str, category: str = 'general',
               limit: int = 5) -> list[dict]:
    """Fetch recent news items relevant to *query* and *category*.

    Returns a list of dicts::

        {
            'headline': str,
            'summary': str,
            'source': str,
            'published_at': str,
            'url': str,
        }

    Falls back to DB cache when live fetch is unavailable.
    """
    # Try DB cache first
    try:
        cached = _load_from_cache(query, category, limit)
        if cached:
            return cached
    except Exception as exc:
        log.debug('News cache load failed: %s', exc)

    # Stub: no live news source configured — return empty
    log.debug('No live news source configured; returning empty news for: %s', query)
    return []


def _load_from_cache(query: str, category: str, limit: int) -> list[dict]:
    """Load recent news from the DB cache."""
    from library.db import connect, row_to_dict
    from library.utils import fts_query
    fts = fts_query(query)
    results = []
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            '''SELECT headline, summary, source, published_at
               FROM news_cache
               WHERE category = ? OR headline LIKE ?
               ORDER BY published_at DESC
               LIMIT ?''',
            (category, f'%{query[:30]}%', limit),
        )
        for row in cur.fetchall():
            results.append(row_to_dict(cur, row))
    return results


def save_to_cache(items: list[dict], category: str = 'general') -> None:
    """Persist news items to the DB cache for future retrieval."""
    if not items:
        return
    from library.db import connect
    ts = now_iso()
    with connect() as conn:
        cur = conn.cursor()
        for item in items:
            cur.execute(
                '''INSERT OR IGNORE INTO news_cache
                   (headline, summary, source, published_at, fetched_at, category)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    item.get('headline', ''),
                    item.get('summary', ''),
                    item.get('source', ''),
                    item.get('published_at', ts),
                    ts,
                    category,
                ),
            )
