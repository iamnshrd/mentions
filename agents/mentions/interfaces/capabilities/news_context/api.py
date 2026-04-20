"""Canonical news-context capability API entrypoint."""
from __future__ import annotations

from agents.mentions.services.news.context_builder import build_news_context_bundle


def fetch_news(query: str, category: str = 'general', limit: int = 5,
               require_live: bool = False) -> tuple[list[dict], str]:
    bundle = build_news_context_bundle(
        query,
        category=category,
        limit=limit,
        require_live=require_live,
    )
    return (
        bundle.get('news', []),
        bundle.get('status', 'unavailable'),
    )


def build_context(query: str, category: str = 'general',
                  market_data: dict | None = None,
                  speaker_info: dict | None = None,
                  limit: int = 5,
                  require_live: bool = False) -> dict:
    bundle = build_news_context_bundle(
        query,
        category=category,
        market_data=market_data,
        speaker_info=speaker_info,
        limit=limit,
        require_live=require_live,
    )
    return {
        'query': query,
        'category': category,
        'news_status': bundle['status'],
        'news': bundle['news'],
        'direct_event_news': bundle.get('direct_event_news', []),
        'background_news': bundle.get('background_news', []),
        'news_summary': bundle['summary'],
        'summary_sections': bundle.get('summary_sections', {}),
        'event_context': bundle['event_context'],
        'direct_paths': bundle['paths']['direct'],
        'weak_paths': bundle['paths']['weak'],
        'late_paths': bundle['paths']['late'],
        'freshness': bundle['freshness'],
        'sufficiency': bundle['sufficiency'],
        'context_risks': bundle.get('context_risks', []),
        'ranking_debug': bundle.get('ranking_debug', {}),
    }

__all__ = ['build_context', 'fetch_news']
