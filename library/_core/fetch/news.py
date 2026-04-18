"""Compatibility shim for legacy ``library._core.fetch.news`` imports."""

from agents.mentions.fetch.news import fetch_news, fetch_news_with_status

__all__ = [
    'fetch_news',
    'fetch_news_with_status',
]
