from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import quote
from urllib.request import Request, urlopen


class GoogleNewsRssUnavailable(RuntimeError):
    pass


def fetch_google_news_rss(query: str, limit: int = 10, hl: str = 'en-US', gl: str = 'US', ceid: str = 'US:en') -> list[dict]:
    query = ' '.join((query or '').split()).strip()
    if not query:
        return []
    url = f'https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}'
    request = Request(url, headers={
        'User-Agent': 'mentions-google-news-rss/1.0',
        'Accept': 'application/rss+xml, application/xml, text/xml',
    })
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read()
    except Exception as exc:
        raise GoogleNewsRssUnavailable(f'Google News RSS request failed: {exc}') from exc

    try:
        root = ET.fromstring(raw)
    except Exception as exc:
        raise GoogleNewsRssUnavailable(f'Google News RSS parse failed: {exc}') from exc

    items = []
    for item in root.findall('.//item')[:limit]:
        headline = (item.findtext('title') or '').strip()
        url = (item.findtext('link') or '').strip()
        published_at = (item.findtext('pubDate') or '').strip()
        source = _extract_source_name(headline)
        if not headline and not url:
            continue
        items.append({
            'headline': headline,
            'summary': '',
            'source': source or 'Google News',
            'published_at': published_at,
            'url': url,
            'provider': 'google-news-rss',
            'provider_payload': {
                'query': query,
                'feed_url': url,
            },
        })
    return items



def _extract_source_name(headline: str) -> str:
    headline = (headline or '').strip()
    if ' - ' not in headline:
        return ''
    return headline.rsplit(' - ', 1)[-1].strip()
