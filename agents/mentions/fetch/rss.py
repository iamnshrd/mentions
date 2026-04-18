from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

log = logging.getLogger('mentions')


class RssProviderUnavailable(RuntimeError):
    pass


def fetch_rss_feed(feed_url: str, source_name: str = '', limit: int = 10) -> list[dict]:
    request = Request(feed_url, headers={'User-Agent': 'mentions-rss/1.0', 'Accept': 'application/rss+xml, application/xml, text/xml'})
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read()
    except Exception as exc:
        raise RssProviderUnavailable(f'RSS request failed: {exc}') from exc

    try:
        root = ET.fromstring(raw)
    except Exception as exc:
        raise RssProviderUnavailable(f'RSS parse failed: {exc}') from exc

    items = []
    for item in root.findall('.//item')[:limit]:
        headline = _text(item.find('title'))
        summary = _text(item.find('description'))
        url = _text(item.find('link'))
        published_at = _text(item.find('pubDate'))
        if not headline and not url:
            continue
        items.append({
            'headline': headline,
            'summary': summary,
            'source': source_name or _infer_channel_title(root),
            'published_at': published_at,
            'url': url,
            'provider': 'rss',
            'provider_payload': {
                'feed_url': feed_url,
            },
        })
    return items


def _infer_channel_title(root) -> str:
    title = root.find('.//channel/title')
    return _text(title)


def _text(node) -> str:
    if node is None or node.text is None:
        return ''
    return node.text.strip()
