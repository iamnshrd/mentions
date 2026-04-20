"""News context fetcher backed by GDELT primary + NewsAPI fallback with DB cache fallback."""
from __future__ import annotations

import logging
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agents.mentions.config import NEWS_API_URL
from agents.mentions.providers.news.gdelt import GdeltProviderUnavailable, fetch_gdelt_news
from agents.mentions.utils import now_iso

log = logging.getLogger('mentions')


class NewsProviderUnavailable(RuntimeError):
    """Raised when the live news provider cannot be used."""


def _empty_news_result() -> tuple[list[dict], str]:
    return [], 'unavailable'


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
                           require_live: bool = False,
                           topic_hints: list[str] | None = None,
                           speaker_hint: str = '') -> tuple[list[dict], str]:
    """Return ``(items, status)`` where status is live/cache/unavailable."""
    cached = []
    try:
        cached = _load_from_cache(query, category, limit, topic_hints=topic_hints, speaker_hint=speaker_hint)
    except Exception as exc:
        log.debug('News cache load failed: %s', exc)

    try:
        try:
            live = _fetch_live_news(
                query,
                category=category,
                limit=limit,
                topic_hints=topic_hints,
                speaker_hint=speaker_hint,
            )
        except TypeError:
            # Backwards-compatible path for tests or monkeypatches that still
            # expose the older helper signature.
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
    return _empty_news_result()


def _fetch_live_news(query: str, category: str = 'general',
                     limit: int = 5,
                     topic_hints: list[str] | None = None,
                     speaker_hint: str = '') -> list[dict]:
    """Fetch live news from GDELT primary, NewsAPI fallback."""
    provider_query = _build_query(query, category, topic_hints=topic_hints, speaker_hint=speaker_hint)

    gdelt_queries = _build_gdelt_queries(query, speaker_hint=speaker_hint, topic_hints=topic_hints)
    for gdelt_query in gdelt_queries:
        try:
            items = fetch_gdelt_news(gdelt_query, limit=limit)
            if items:
                return items
        except GdeltProviderUnavailable as exc:
            log.debug('GDELT unavailable for query %s: %s', gdelt_query, exc)

    api_key = os.environ.get('NEWSAPI_KEY', '').strip()
    if not api_key:
        raise NewsProviderUnavailable('NEWSAPI_KEY is not configured and GDELT returned no usable items.')

    url = NEWS_API_URL + '?' + urlencode({
        'q': provider_query,
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
            'provider': 'newsapi',
        })
    return items


def _build_gdelt_queries(query: str, speaker_hint: str = '', topic_hints: list[str] | None = None) -> list[str]:
    topic_hints = [hint.strip() for hint in (topic_hints or []) if hint and hint.strip()]
    queries = []
    parts = [speaker_hint] if speaker_hint else []
    if topic_hints:
        queries.append(' '.join(part for part in [speaker_hint] + topic_hints[:2] if part).strip())
        queries.append(' '.join(part for part in [speaker_hint, topic_hints[0]] if part).strip())
    if query:
        queries.append(query)
    cleaned = []
    for item in queries:
        item = ' '.join((item or '').split()).strip()
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned[:4]


def _build_query(query: str, category: str, topic_hints: list[str] | None = None, speaker_hint: str = '') -> str:
    """Build a NewsAPI query string from query/category hints."""
    topic_hints = [hint.strip() for hint in (topic_hints or []) if hint and hint.strip()]
    base = (query or '').strip() or category
    if speaker_hint and speaker_hint.lower() not in base.lower():
        base = f'{speaker_hint} {base}'.strip()
    if topic_hints:
        joined_hints = ' OR '.join(topic_hints[:3])
        if joined_hints and joined_hints.lower() not in base.lower():
            base = f'({base}) AND ({joined_hints})'
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


def _load_from_cache(query: str, category: str, limit: int,
                     topic_hints: list[str] | None = None,
                     speaker_hint: str = '') -> list[dict]:
    """Load recent news from the DB cache."""
    from agents.mentions.db import connect, row_to_dict

    results = []
    with connect() as conn:
        cur = conn.cursor()
        clauses = ['category = ?', 'headline LIKE ?', 'summary LIKE ?']
        params = [category, f'%{query[:30]}%', f'%{query[:30]}%']
        if speaker_hint:
            clauses.append('headline LIKE ?')
            params.append(f'%{speaker_hint[:30]}%')
        for hint in (topic_hints or [])[:3]:
            clauses.append('headline LIKE ?')
            params.append(f'%{hint[:30]}%')
        where = ' OR '.join(clauses)
        cur.execute(
            f'''SELECT headline, summary, source, published_at, url
                FROM news_cache
                WHERE {where}
                ORDER BY published_at DESC
                LIMIT ?''',
            (*params, limit),
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


def _news_item_key(item: dict) -> tuple[str, str, str]:
    return (
        item.get('headline', ''),
        item.get('published_at', ''),
        item.get('url', ''),
    )


def _dedupe_items(items: list[dict]) -> list[dict]:
    """Deduplicate cache/news-provider items by headline/url/published_at."""
    out = []
    seen = set()
    for item in items:
        key = _news_item_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
