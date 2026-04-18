from __future__ import annotations

import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agents.mentions.config import GDELT_DOC_API_URL

log = logging.getLogger('mentions')


class GdeltProviderUnavailable(RuntimeError):
    pass


def fetch_gdelt_news(query: str, limit: int = 5, mode: str = 'ArtList') -> list[dict]:
    if not query.strip():
        raise GdeltProviderUnavailable('empty query')

    gdelt_query = _normalize_gdelt_query(query)
    url = GDELT_DOC_API_URL + '?' + urlencode({
        'query': gdelt_query,
        'mode': mode,
        'maxrecords': max(1, min(limit, 25)),
        'format': 'json',
        'sort': 'datedesc',
    })
    request = Request(url, headers={'Accept': 'application/json'})

    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        raise GdeltProviderUnavailable(f'GDELT request failed: {exc}') from exc

    articles = payload.get('articles', []) or []
    items = []
    for article in articles[:limit]:
        headline = article.get('title', '') or article.get('seendate', '')
        url = article.get('url', '')
        if not headline and not url:
            continue
        items.append({
            'headline': headline,
            'summary': article.get('socialimage', '') or '',
            'source': article.get('domain', '') or 'gdelt',
            'published_at': article.get('seendate', ''),
            'url': url,
            'provider': 'gdelt',
            'provider_payload': article,
            'provider_query': gdelt_query,
        })
    return items


def _normalize_gdelt_query(query: str) -> str:
    query = (query or '').strip()
    if not query:
        return ''
    replacements = [
        ("White House Correspondents' Dinner", 'White House Correspondents Dinner'),
        (' AND ', ' '),
        (' OR ', ' '),
        ('(', ' '),
        (')', ' '),
    ]
    for old, new in replacements:
        query = query.replace(old, new)
    query = ' '.join(query.split())
    return query
