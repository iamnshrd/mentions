"""Application service for building workspace payloads for web clients."""
from __future__ import annotations

from agents.mentions.presentation.workspace_payload import build_workspace_payload
from mentions_domain.normalize import ensure_dict


def build_workspace_payload_for_query(
    query: str,
    *,
    user_id: str = 'default',
    news_limit: int = 5,
    transcript_limit: int = 5,
) -> dict:
    query = (query or '').strip()
    if not query:
        raise ValueError('query must be a non-empty string')
    return ensure_dict(
        build_workspace_payload(
            query,
            user_id=user_id,
            mode='query',
            news_limit=news_limit,
            transcript_limit=transcript_limit,
        )
    )


def build_workspace_payload_for_market_url(
    market_url: str,
    *,
    user_id: str = 'default',
    news_limit: int = 5,
    transcript_limit: int = 5,
) -> dict:
    market_url = (market_url or '').strip()
    if not market_url:
        raise ValueError('market_url must be a non-empty string')
    return ensure_dict(
        build_workspace_payload(
            market_url,
            user_id=user_id,
            mode='url',
            news_limit=news_limit,
            transcript_limit=transcript_limit,
        )
    )


def build_workspace_payload_for_input(
    *,
    query: str | None = None,
    market_url: str | None = None,
    user_id: str = 'default',
    news_limit: int = 5,
    transcript_limit: int = 5,
) -> dict:
    query = (query or '').strip()
    market_url = (market_url or '').strip()
    if bool(query) == bool(market_url):
        raise ValueError('provide exactly one of query or market_url')
    if market_url:
        return build_workspace_payload_for_market_url(
            market_url,
            user_id=user_id,
            news_limit=news_limit,
            transcript_limit=transcript_limit,
        )
    return build_workspace_payload_for_query(
        query,
        user_id=user_id,
        news_limit=news_limit,
        transcript_limit=transcript_limit,
    )
