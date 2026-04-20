from __future__ import annotations

from agents.mentions.fetch import kalshi as kalshi_fetch
from agents.mentions.runtime.trace import trace_log


def _bundle_status(payload, warning: str) -> tuple[str, list[str]]:
    ok = bool(payload)
    return ('ok' if ok else 'unavailable', [] if ok else [warning])


def get_event_bundle(event_ticker: str, with_nested_markets: bool = False) -> dict:
    payload = kalshi_fetch.get_event(event_ticker, with_nested_markets=with_nested_markets)
    event = payload.get('event', {}) if isinstance(payload, dict) else {}
    markets = payload.get('markets', []) if isinstance(payload, dict) else []
    status, warnings = _bundle_status(event, 'event-unavailable')
    return {
        'status': status,
        'event_ticker': event_ticker,
        'event': event,
        'markets': markets,
        'warnings': warnings,
    }


def get_market_bundle(ticker: str) -> dict:
    trace_log('kalshi.provider.market_bundle.start', ticker=ticker)
    trace_log('kalshi.provider.market_bundle.start', ticker=ticker)
    market = kalshi_fetch.get_market(ticker)
    status, warnings = _bundle_status(market, 'market-unavailable')
    market_status = str((market or {}).get('status') or '').lower()
    source = 'live-or-fallback' if market else 'unavailable'
    if market_status in {'closed', 'determined', 'finalized'}:
        source = 'historical-or-closed'
    bundle = {
        'status': status,
        'ticker': ticker,
        'market': market,
        'market_status': market_status,
        'market_source': source,
        'warnings': warnings,
    }
    trace_log('kalshi.provider.market_bundle.finish', ticker=ticker, status=status, market_status=market_status, market_source=source, warning_count=len(warnings))
    return bundle


def get_history_bundle(ticker: str, series_ticker: str = '', days: int = 30) -> dict:
    history = kalshi_fetch.get_history(ticker, series_ticker=series_ticker, days=days)
    status, warnings = _bundle_status(history, 'history-unavailable')
    return {
        'status': status,
        'ticker': ticker,
        'series_ticker': series_ticker,
        'days': days,
        'history': history,
        'warnings': warnings,
    }


def search_markets_bundle(query: str, limit: int = 10) -> dict:
    trace_log('kalshi.provider.search_bundle.start', query=query, limit=limit)
    markets = kalshi_fetch.search_markets(query, limit=limit)
    status, warnings = _bundle_status(markets, 'search-empty')
    bundle = {
        'status': status,
        'query': query,
        'limit': limit,
        'markets': markets,
        'search_contract': 'documented-market-filters-with-historical-ticker-fallback',
        'warnings': warnings,
    }
    trace_log('kalshi.provider.search_bundle.finish', query=query, limit=limit, status=status, hit_count=len(markets), warning_count=len(warnings), search_contract=bundle['search_contract'])
    return bundle


def get_markets_bundle(category: str = '', limit: int = 20, status: str = 'open', event_ticker: str = '') -> dict:
    trace_log('kalshi.provider.markets_bundle.start', category=category, event_ticker=event_ticker, limit=limit, market_status=status)
    markets = kalshi_fetch.get_markets(category=category, limit=limit, status=status, event_ticker=event_ticker)
    bundle_status, warnings = _bundle_status(markets, 'markets-empty')
    bundle = {
        'status': bundle_status,
        'category': category,
        'event_ticker': event_ticker,
        'limit': limit,
        'market_status': status,
        'markets': markets,
        'warnings': warnings,
    }
    trace_log('kalshi.provider.markets_bundle.finish', category=category, event_ticker=event_ticker, limit=limit, market_status=status, status_out=bundle_status, hit_count=len(markets), warning_count=len(warnings))
    return bundle


def get_top_movers_bundle(limit: int = 10) -> dict:
    markets = kalshi_fetch.get_top_movers(limit=limit)
    status, warnings = _bundle_status(markets, 'top-movers-empty')
    return {
        'status': status,
        'limit': limit,
        'markets': markets,
        'warnings': warnings,
    }
