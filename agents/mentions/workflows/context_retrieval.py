from __future__ import annotations

import logging

from mentions_domain.normalize import ensure_dict, ensure_list
from agents.mentions.workflows.retrieval_fallbacks import empty_news_context, empty_transcript_context
from agents.mentions.utils import get_threshold

log = logging.getLogger('mentions')


def _runtime_health_payload(contract_name: str) -> dict:
    try:
        from agents.mentions.storage.runtime_db import get_runtime_health

        health = get_runtime_health()
        return {
            'status': health.get('status', 'unknown'),
            'contract': contract_name,
            'details': (health.get('contracts') or {}).get(contract_name, {}),
            'path': health.get('path', ''),
        }
    except Exception as exc:
        log.debug('Runtime health lookup failed for %s: %s', contract_name, exc)
        return {
            'status': 'unknown',
            'contract': contract_name,
            'details': {'health_lookup': [str(exc)]},
            'path': '',
        }


def retrieve_market_context(query: str) -> dict:
    market_data = {}
    history = []
    cached_analysis = []

    from agents.mentions.services.intake.intake import intake_market_input
    from agents.mentions.services.intake.resolution import recover_canonical_ticker
    intake = intake_market_input(query)
    intake = recover_canonical_ticker(intake)
    ticker = intake.get('ticker', '') or _extract_ticker(query)

    bundle = {}
    try:
        from agents.mentions.services.markets.market_data import build_market_data_bundle
        bundle = build_market_data_bundle(
            query=query,
            ticker=ticker,
            history_days=get_threshold('history_days_default', 30),
        )
        market_data = bundle.get('market', {}) or {}
        history = bundle.get('history', []) or []
        if bundle.get('resolved_market'):
            market_data = dict(market_data)
            market_data['resolved_market'] = bundle['resolved_market']
            market_data['sourcing'] = bundle.get('sourcing', {})
            market_data['provider_status'] = bundle.get('provider_status', {})
    except Exception as exc:
        log.warning('Kalshi market-data build failed: %s', exc)

    try:
        from agents.mentions.services.knowledge import query_analysis_cache
        cached_analysis = query_analysis_cache(query, limit=3)
    except Exception as exc:
        log.debug('Analysis cache query failed: %s', exc)

    resolved_market = ensure_dict(market_data.get('resolved_market', {})) if isinstance(market_data, dict) else {}
    normalized_ticker = ticker or resolved_market.get('ticker', '') or ensure_dict(bundle.get('resolved_market', {})).get('ticker', '')

    return {
        'ticker': normalized_ticker,
        'market_data': market_data,
        'history': history,
        'cached_analysis': cached_analysis,
        'input_intake': intake,
        'raw_market_bundle': bundle,
        'resolved_market': resolved_market or ensure_dict(bundle.get('resolved_market', {})),
    }


def retrieve_transcript_context(frame: dict) -> dict:
    if not frame.get('needs_transcript', False):
        return empty_transcript_context(frame.get('query', ''), status='skipped', risk='transcript-not-needed')

    query = frame.get('query', '')
    limit = get_threshold('fts_chunk_limit', 5)

    try:
        from agents.mentions.services.transcripts.intelligence import build_transcript_intelligence_bundle
        from agents.mentions.storage.runtime_query import search_transcripts_runtime
        bundle = build_transcript_intelligence_bundle(query, limit=limit)
        if not bundle.get('chunks'):
            stored = search_transcripts_runtime(query=query, speaker=bundle.get('speaker', ''), limit=limit)
            bundle['runtime_health'] = _runtime_health_payload('transcript_search')
            if stored:
                bundle['chunks'] = stored
                bundle['status'] = 'ok'
                bundle['summary'] = ' | '.join([(row.get('text') or '')[:180] for row in stored[:3]])
                bundle['top_speakers'] = [row.get('speaker', '') for row in stored[:3] if row.get('speaker')]
                bundle['top_events'] = [row.get('event_title', '') for row in stored[:3] if row.get('event_title')]
                bundle['context_risks'] = ['runtime-db-transcript-fallback']
        return bundle
    except Exception as exc:
        log.warning('Transcript FTS failed: %s', exc)
        return empty_transcript_context(query, status='error', risk='transcript-fetch-failed')


def retrieve_news_context(frame: dict, market_data: dict | None = None) -> dict:
    category = frame.get('category', 'general')
    query = frame.get('query', '')

    try:
        from agents.mentions.services.news.context_builder import build_news_context_bundle
        from agents.mentions.storage.runtime_query import search_news_runtime
        bundle = build_news_context_bundle(
            query,
            category=category,
            market_data=market_data,
            limit=get_threshold('news_fetch_limit', 5),
            require_live=False,
        )
        if not bundle.get('news'):
            stored = search_news_runtime(query=query, limit=get_threshold('news_fetch_limit', 5))
            bundle['runtime_health'] = _runtime_health_payload('news_search')
            if stored:
                bundle['news'] = stored
                bundle['status'] = 'ok'
                bundle['freshness'] = 'stored'
                bundle['sufficiency'] = 'partial'
                bundle['summary'] = '; '.join([row.get('headline', '') for row in stored[:3] if row.get('headline')])
                bundle['context_risks'] = ['runtime-db-news-fallback']
        return bundle
    except Exception as exc:
        log.debug('News fetch failed: %s', exc)
        return empty_news_context(query, category)


def _extract_ticker(query: str) -> str:
    import re
    pattern = r'\b([A-Z]{2,10}-[A-Z0-9]{2,10}(?:-[A-Z0-9]{2,10})*)\b'
    matches = re.findall(pattern, query.upper())
    return matches[0] if matches else ''
