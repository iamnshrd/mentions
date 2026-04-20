from __future__ import annotations

from mentions_domain.normalize import ensure_dict, ensure_list, normalize_confidence, normalize_status
from agents.mentions.providers.kalshi import (
    build_candidate_market_pool,
    get_history_bundle,
    get_market_bundle,
)
from agents.mentions.services.markets.resolution import build_search_queries, resolve_market_from_query


def build_market_data_bundle(query: str, ticker: str = '', history_days: int = 30) -> dict:
    if ticker:
        market_bundle = get_market_bundle(ticker)
        market = ensure_dict(market_bundle.get('market', {}))
        series_ticker = market.get('series_ticker', '') if isinstance(market, dict) else ''
        history_bundle = get_history_bundle(ticker, series_ticker=series_ticker, days=history_days)
        return {
            'query': query,
            'ticker': ticker,
            'mode': 'direct-ticker',
            'market': market,
            'history': ensure_list(history_bundle.get('history', [])),
            'resolved_market': {
                'ticker': market.get('ticker', ticker),
                'title': market.get('title', ''),
                'confidence': normalize_confidence('high' if market else 'low'),
                'rationale': 'direct-ticker',
                'search_queries': [ticker],
            },
            'sourcing': {
                'diagnostics': ['direct-ticker'],
                'raw_market_count': 1 if market else 0,
                'filtered_market_count': 1 if market else 0,
            },
            'provider_status': {
                'market': normalize_status(market_bundle.get('status', 'unavailable')),
                'history': normalize_status(history_bundle.get('status', 'unavailable')),
            },
        }

    pool = build_candidate_market_pool(query, limit_per_call=12)
    markets = pool.get('markets', [])
    resolved = resolve_market_from_query(query, markets)
    resolved_market = _resolved_market_payload(resolved, query)

    market_payload = {}
    history = []
    provider_status = {'market': 'unavailable', 'history': 'unavailable'}
    if resolved.ticker:
        market_bundle = get_market_bundle(resolved.ticker)
        market_payload = ensure_dict(market_bundle.get('market', {}))
        provider_status['market'] = normalize_status(market_bundle.get('status', 'unavailable'))
        series_ticker = market_payload.get('series_ticker', '') if isinstance(market_payload, dict) else ''
        history_bundle = get_history_bundle(resolved.ticker, series_ticker=series_ticker, days=history_days)
        history = ensure_list(history_bundle.get('history', []))
        provider_status['history'] = normalize_status(history_bundle.get('status', 'unavailable'))

    return {
        'query': query,
        'ticker': resolved.ticker,
        'mode': 'resolved-query',
        'market': market_payload,
        'history': history,
        'resolved_market': resolved_market,
        'sourcing': {
            'diagnostics': pool.get('diagnostics', []),
            'raw_market_count': pool.get('raw_market_count', len(markets)),
            'filtered_market_count': pool.get('filtered_market_count', len(markets)),
        },
        'provider_status': provider_status,
    }


def _resolved_market_payload(resolved, query: str) -> dict:
    return {
        'ticker': resolved.ticker,
        'title': resolved.title,
        'confidence': normalize_confidence(resolved.confidence),
        'rationale': resolved.rationale,
        'search_queries': build_search_queries(query),
        'candidates': [
            {
                'ticker': c.ticker,
                'title': c.title,
                'score': c.score,
                'rationale': c.rationale,
            }
            for c in resolved.candidates
        ],
        'score_margin': resolved.meta.get('score_margin', 0) if isinstance(resolved.meta, dict) else 0,
    }
