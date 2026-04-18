"""Programmatic API for Mentions news/context capability."""
from __future__ import annotations

from agents.mentions.fetch.news import NewsProviderUnavailable, fetch_news_with_status
from agents.mentions.modules.news_context import build_news_context_bundle


def fetch_news(query: str, category: str = 'general', limit: int = 5,
               require_live: bool = False) -> tuple[list[dict], str]:
    return fetch_news_with_status(
        query,
        category=category,
        limit=limit,
        require_live=require_live,
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
        'news_summary': bundle['summary'],
        'event_context': bundle['event_context'],
        'direct_paths': bundle['paths']['direct'],
        'weak_paths': bundle['paths']['weak'],
        'late_paths': bundle['paths']['late'],
        'freshness': bundle['freshness'],
        'sufficiency': bundle['sufficiency'],
        'context_risks': bundle['context_risks'],
    }


__all__ = ['NewsProviderUnavailable', 'build_context', 'fetch_news']
