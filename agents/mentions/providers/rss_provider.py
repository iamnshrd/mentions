from __future__ import annotations

from agents.mentions.fetch.rss import RssProviderUnavailable, fetch_rss_feed
from agents.mentions.module_contracts import ensure_list
from agents.mentions.utils import load_json
from agents.mentions.config import ASSETS


def fetch_rss_news_bundle(category: str = 'general', limit_per_feed: int = 5, max_feeds: int = 10) -> dict:
    sources = load_json(ASSETS / 'rss_sources.json', default=[])
    selected = []
    for source in ensure_list(sources):
        if not isinstance(source, dict):
            continue
        source_category = (source.get('category') or '').strip().lower()
        if category != 'general' and source_category and source_category != category:
            continue
        selected.append(source)
        if len(selected) >= max_feeds:
            break

    items = []
    feed_reports = []
    seen = set()
    for source in selected:
        name = source.get('name', '')
        feed_url = source.get('feed_url', '')
        try:
            fetched = fetch_rss_feed(feed_url, source_name=name, limit=limit_per_feed)
            accepted = 0
            for item in fetched:
                key = (item.get('headline', ''), item.get('url', ''))
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
                accepted += 1
            feed_reports.append({
                'source': name,
                'feed_url': feed_url,
                'status': 'ok',
                'fetched_count': len(fetched),
                'accepted_count': accepted,
            })
        except RssProviderUnavailable as exc:
            feed_reports.append({
                'source': name,
                'feed_url': feed_url,
                'status': 'error',
                'error': str(exc),
                'fetched_count': 0,
                'accepted_count': 0,
            })

    return {
        'provider': 'rss',
        'category': category,
        'raw_items': items,
        'provider_status': 'ok' if items else 'unavailable',
        'feed_reports': feed_reports,
        'selected_sources': selected,
    }
