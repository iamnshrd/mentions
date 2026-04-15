"""Programmatic API for Mentions news/context capability."""
from __future__ import annotations

import re

from agents.mentions.analysis.event_context import analyze_event_context
from agents.mentions.fetch.news import (
    NewsProviderUnavailable,
    fetch_news_with_status,
)


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
    market_data = market_data or {}
    speaker_info = speaker_info or {}

    news, status = fetch_news(
        query,
        category=category,
        limit=limit,
        require_live=require_live,
    )
    event_context = analyze_event_context(market_data, news, speaker_info)
    direct_paths, weak_paths, late_paths = _build_path_map(query, event_context, news)
    headlines = [item.get('headline', '') for item in news[:3] if item.get('headline')]

    return {
        'query': query,
        'category': category,
        'news_status': status,
        'news': news,
        'news_summary': '; '.join(headlines),
        'event_context': event_context,
        'direct_paths': direct_paths,
        'weak_paths': weak_paths,
        'late_paths': late_paths,
    }


def _build_path_map(query: str, event_context: dict, news: list[dict]) -> tuple[list[str], list[str], list[str]]:
    topics = [topic for topic in event_context.get('likely_topics', []) if topic]
    qa_likelihood = event_context.get('qa_likelihood', 'medium')
    headline_phrases = []
    for item in news[:5]:
        headline = item.get('headline', '')
        for phrase in re.findall(r'[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*', headline):
            if len(phrase) > 4 and phrase not in headline_phrases:
                headline_phrases.append(phrase)

    direct = topics[:3] or _query_topics(query)[:3]
    late = []
    if qa_likelihood in {'high', 'medium'}:
        late = topics[3:6] or headline_phrases[:2]

    weak = [
        phrase for phrase in headline_phrases
        if phrase not in direct and phrase not in late
    ][:3]
    return direct, weak, late


def _query_topics(query: str) -> list[str]:
    return [
        word for word in re.findall(r'[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9-]{3,}', query)
        if len(word) > 3
    ]


__all__ = ['NewsProviderUnavailable', 'build_context', 'fetch_news']
