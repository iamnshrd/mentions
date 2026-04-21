"""Application service for building workspace payloads for web clients."""
from __future__ import annotations

from agents.mentions.config import get_default_store
from agents.mentions.module_registry import (
    get_analysis_engine,
    get_frame_selector,
    get_retrieval_bundle_builder,
    get_ticker_retriever,
)
from agents.mentions.presentation.workspace_payload import compose_workspace_payload
from agents.mentions.services.intake.url_parser import parse_kalshi_url
from agents.mentions.workflows.orchestrator import detect_mode, should_use_kb
from agents.mentions.workflows.synthesize_speaker import synthesize_speaker_market
from mentions_domain.normalize import ensure_dict, ensure_list


def build_workspace_payload_for_query(
    query: str,
    *,
    user_id: str = 'default',
    news_limit: int = 5,
    transcript_limit: int = 5,
) -> dict:
    del news_limit, transcript_limit  # retrieval flow owns these limits for now
    query = (query or '').strip()
    if not query:
        raise ValueError('query must be a non-empty string')

    if not should_use_kb(query):
        return compose_workspace_payload(
            query=query,
            analysis_result={
                'action': 'answer-directly',
                'reason': 'Query does not match known market routes.',
            },
            news_context={},
            transcript_hits=[],
        )

    store = get_default_store()
    frame = ensure_dict(get_frame_selector()(query, user_id=user_id, store=store))
    frame['mode'] = detect_mode(query)
    bundle = ensure_dict(get_retrieval_bundle_builder()(query, frame))
    synthesis = ensure_dict(get_analysis_engine()(query, frame, bundle))
    analysis_result = {
        'query': query,
        'action': 'respond-with-data',
        'confidence': synthesis.get('confidence', 'low'),
        'has_data': bundle.get('has_data', False),
        'sources': ensure_list(bundle.get('sources_used', [])),
        'synthesis': synthesis,
    }
    return compose_workspace_payload(
        query=query,
        analysis_result=analysis_result,
        news_context=ensure_dict(bundle.get('news_context', {})),
        transcript_hits=ensure_list(bundle.get('transcripts', [])),
    )


def build_workspace_payload_for_market_url(
    market_url: str,
    *,
    user_id: str = 'default',
    news_limit: int = 5,
    transcript_limit: int = 5,
) -> dict:
    del user_id, news_limit, transcript_limit  # current URL flow is stateless
    market_url = (market_url or '').strip()
    if not market_url:
        raise ValueError('market_url must be a non-empty string')

    url_info = ensure_dict(parse_kalshi_url(market_url))
    ticker = (url_info.get('ticker') or '').strip()
    if not ticker:
        raise ValueError('could not extract ticker from market_url')

    ticker_kind = url_info.get('ticker_kind', 'unknown')
    speaker_info = ensure_dict(url_info.get('speaker_info', {}))
    speaker_name = speaker_info.get('name', '') or url_info.get('speaker_slug', '')

    bundle = ensure_dict(
        get_ticker_retriever()(ticker, speaker=speaker_name, ticker_kind=ticker_kind)
    )
    market_payload = ensure_dict(bundle.get('market', {}))
    market_data = ensure_dict(market_payload.get('market_data', {}))
    transcript_bundle = ensure_dict(bundle.get('transcript_intelligence', {}))

    synthesis = ensure_dict(
        synthesize_speaker_market(
            ticker=ticker,
            market_data=market_data,
            transcripts=ensure_list(bundle.get('transcripts', [])),
            news=ensure_list(bundle.get('news', [])),
            url_info=url_info,
            transcript_bundle=transcript_bundle,
        )
    )
    synthesis['bundle_market'] = market_payload
    synthesis['news_bundle'] = ensure_dict(bundle.get('news_context', {}))
    synthesis['transcript_bundle'] = transcript_bundle

    analysis_result = {
        'url': market_url,
        'ticker': ticker,
        'action': 'respond-with-data',
        'confidence': synthesis.get('confidence', 'low'),
        'has_data': bundle.get('has_data', False),
        'sources': ensure_list(bundle.get('sources_used', [])),
        'synthesis': synthesis,
    }
    return compose_workspace_payload(
        query=market_url,
        analysis_result=analysis_result,
        news_context=ensure_dict(bundle.get('news_context', {})),
        transcript_hits=ensure_list(bundle.get('transcripts', [])),
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
