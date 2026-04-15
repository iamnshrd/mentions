"""News context fetcher backed by NewsAPI with DB cache fallback."""
from __future__ import annotations

import logging
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agents.mentions.config import NEWS_API_URL
from agents.mentions.utils import now_iso

log = logging.getLogger('mentions')


class NewsProviderUnavailable(RuntimeError):
    """Raised when the live news provider cannot be used."""


def fetch_news(query: str, category: str = 'general',
               limit: int = 5, require_live: bool = False) -> list[dict]:
    """Fetch recent news items relevant to *query* and *category*."""
    items, _status = fetch_news_with_status(
        query,
        category=category,
        limit=limit,
        require_live=require_live,
    )
    return items


def fetch_news_with_status(query: str, category: str = 'general',
                           limit: int = 5,
                           require_live: bool = False) -> tuple[list[dict], str]:
    """Return ``(items, status)`` where status is live/cache/unavailable."""
    cached = []
    try:
        cached = _load_from_cache(query, category, limit)
    except Exception as exc:
        log.debug('News cache load failed: %s', exc)

    try:
        live = _fetch_live_news(query, category=category, limit=limit)
        if live:
            save_to_cache(live, category=category)
            return live, 'live'
    except NewsProviderUnavailable as exc:
        log.debug('Live news unavailable: %s', exc)
        if require_live:
            raise

    if cached:
        return cached, 'cache'
    if require_live:
        raise NewsProviderUnavailable('Live news unavailable and cache is empty.')
    return [], 'unavailable'


def _fetch_live_news(query: str, category: str = 'general',
                     limit: int = 5) -> list[dict]:
    """Fetch live news from NewsAPI."""
    api_key = os.environ.get('NEWSAPI_KEY', '').strip()
    if not api_key:
        raise NewsProviderUnavailable('NEWSAPI_KEY is not configured.')

    url = NEWS_API_URL + '?' + urlencode({
        'q': _build_query(query, category),
        'pageSize': max(1, min(limit, 20)),
        'language': 'en',
        'sortBy': 'publishedAt',
    })
    request = Request(url, headers={'X-Api-Key': api_key, 'Accept': 'application/json'})

    try:
        with urlopen(request, timeout=10) as response:
            import json
            payload = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        raise NewsProviderUnavailable(f'NewsAPI request failed: {exc}') from exc

    if payload.get('status') != 'ok':
        raise NewsProviderUnavailable(payload.get('message', 'NewsAPI returned an error.'))

    articles = payload.get('articles', [])
    items = []
    for article in articles[:limit]:
        headline = article.get('title', '')
        if not headline:
            continue
        items.append({
            'headline': headline,
            'summary': article.get('description', '') or '',
            'source': (article.get('source') or {}).get('name', ''),
            'published_at': article.get('publishedAt', ''),
            'url': article.get('url', ''),
        })
    return items


def _build_query(query: str, category: str) -> str:
    """Build a NewsAPI query string from query/category hints."""
    base = (query or '').strip() or category
    category_hints = {
        'macro': 'Federal Reserve OR inflation OR rate',
        'politics': 'White House OR election OR Congress',
        'geopolitics': 'sanctions OR conflict OR summit',
        'crypto': 'bitcoin OR ethereum OR crypto',
        'sports': 'FIFA OR league OR finals',
        'finance': 'market OR earnings OR yield',
    }
    hint = category_hints.get(category, '')
    if hint and hint.lower() not in base.lower():
        return f'({base}) AND ({hint})'
    return base


def _load_from_cache(query: str, category: str, limit: int) -> list[dict]:
    """Load recent news from the DB cache."""
    from agents.mentions.db import connect, row_to_dict

    results = []
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            '''SELECT headline, summary, source, published_at, url
               FROM news_cache
               WHERE category = ? OR headline LIKE ?
               ORDER BY published_at DESC
               LIMIT ?''',
            (category, f'%{query[:30]}%', limit),
        )
        for row in cur.fetchall():
            results.append(row_to_dict(cur, row))
    return _dedupe_items(results)[:limit]


def save_to_cache(items: list[dict], category: str = 'general') -> None:
    """Persist news items to the DB cache for future retrieval."""
    if not items:
        return
    from agents.mentions.db import connect

    ts = now_iso()
    with connect() as conn:
        cur = conn.cursor()
        for item in items:
            cur.execute(
                '''INSERT OR IGNORE INTO news_cache
                   (headline, summary, source, published_at, fetched_at, category, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (
                    item.get('headline', ''),
                    item.get('summary', ''),
                    item.get('source', ''),
                    item.get('published_at', ts),
                    ts,
                    category,
                    item.get('url', ''),
                ),
            )


def _dedupe_items(items: list[dict]) -> list[dict]:
    """Deduplicate cache/news-provider items by headline/url/published_at."""
    out = []
    seen = set()
    for item in items:
        key = (
            item.get('headline', ''),
            item.get('published_at', ''),
            item.get('url', ''),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
