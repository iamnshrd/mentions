"""Kalshi API client.

Wraps the Kalshi REST API for markets, orderbook, and price history.
All functions return plain dicts/lists; callers handle persistence.

Set KALSHI_API_KEY and KALSHI_API_URL (or KALSHI_ENV=demo) in environment.
"""
from __future__ import annotations

import logging
import os
import time

from agents.mentions.runtime.trace import trace_log

log = logging.getLogger('mentions')

_PROD_URL = 'https://api.elections.kalshi.com/trade-api/v2'
_DEMO_URL = 'https://demo-api.kalshi.co/trade-api/v2'


def _base_url() -> str:
    env = os.environ.get('KALSHI_ENV', 'demo').lower()
    explicit = os.environ.get('KALSHI_API_URL', '')
    if explicit:
        return explicit.rstrip('/')
    return _DEMO_URL if env == 'demo' else _PROD_URL


def _api_key() -> str:
    return os.environ.get('KALSHI_API_KEY', '')


def _headers() -> dict:
    key = _api_key()
    h = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if key:
        h['Authorization'] = f'Bearer {key}'
    return h


def _get(path: str, params: dict | None = None, timeout: int = 10) -> dict | list | None:
    """Make a GET request to the Kalshi API. Returns parsed JSON or None."""
    import urllib.request, urllib.parse, json as _json
    base_url = _base_url()
    url = base_url + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    trace_log('kalshi.http.request', base_url=base_url, path=path, params=params or {}, timeout=timeout)
    log.info('kalshi.http.request base_url=%s path=%s params=%s timeout=%s', base_url, path, params or {}, timeout)
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = _json.loads(resp.read().decode('utf-8'))
            size = len(payload) if isinstance(payload, list) else len(payload.keys()) if isinstance(payload, dict) else 0
            trace_log('kalshi.http.response', base_url=base_url, path=path, params=params or {}, ok=True, payload_type=type(payload).__name__, payload_size=size)
            log.info('kalshi.http.response ok=true base_url=%s path=%s params=%s payload_type=%s payload_size=%s', base_url, path, params or {}, type(payload).__name__, size)
            return payload
    except Exception as exc:
        trace_log('kalshi.http.response', base_url=base_url, path=path, params=params or {}, ok=False, error=str(exc))
        log.warning('kalshi.http.response ok=false base_url=%s path=%s params=%s error=%s', base_url, path, params or {}, exc)
        log.warning('Kalshi API error [%s]: %s', path, exc)
        return None


def _market_search_fallbacks(ticker: str) -> list[dict]:
    ticker = (ticker or '').strip().upper()
    if not ticker:
        return []
    params_list = [
        {'tickers': ticker, 'limit': 1, 'status': 'open'},
        {'tickers': ticker, 'limit': 1, 'status': 'settled'},
        {'tickers': ticker, 'limit': 1, 'status': 'closed'},
        {'tickers': ticker, 'limit': 1},
    ]
    trace_log('kalshi.get_market.live_fallbacks.start', ticker=ticker, attempts=params_list)
    results: list[dict] = []
    seen: set[str] = set()
    for params in params_list:
        data = _get('/markets', params=params)
        markets = data.get('markets', []) if isinstance(data, dict) else []
        trace_log('kalshi.get_market.live_fallbacks.attempt', ticker=ticker, params=params, hit_count=len(markets))
        for market in markets:
            market_ticker = str((market or {}).get('ticker') or '').upper()
            if market_ticker != ticker or market_ticker in seen:
                continue
            seen.add(market_ticker)
            results.append(market)
    trace_log('kalshi.get_market.live_fallbacks.finish', ticker=ticker, result_count=len(results))
    return results


def get_historical_markets(*, tickers: str = '', event_ticker: str = '',
                           series_ticker: str = '', limit: int = 20) -> list[dict]:
    params: dict = {'limit': limit}
    if tickers:
        params['tickers'] = tickers
    if event_ticker:
        params['event_ticker'] = event_ticker
    if series_ticker:
        params['series_ticker'] = series_ticker
    trace_log('kalshi.historical_markets.start', params=params)
    data = _get('/historical/markets', params=params)
    markets = data.get('markets', []) if isinstance(data, dict) else []
    trace_log('kalshi.historical_markets.finish', params=params, hit_count=len(markets))
    return markets


def get_market(ticker: str) -> dict:
    """Fetch a single market by ticker. Returns market dict or {}."""
    if not ticker:
        return {}
    normalized = (ticker or '').strip().upper()
    trace_log('kalshi.get_market.start', ticker=normalized, base_url=_base_url())
    log.info('kalshi.get_market.start ticker=%s base_url=%s', normalized, _base_url())
    data = _get(f'/markets/{normalized}')
    if isinstance(data, dict):
        market = data.get('market', data)
        if isinstance(market, dict) and market:
            trace_log('kalshi.get_market.finish', ticker=normalized, source='direct', found=True, market_status=market.get('status', ''))
            log.info('kalshi.get_market.finish ticker=%s source=direct found=true market_status=%s', normalized, market.get('status', ''))
            return market
    fallbacks = _market_search_fallbacks(normalized)
    if fallbacks:
        trace_log('kalshi.get_market.finish', ticker=normalized, source='live_list_fallback', found=True, market_status=(fallbacks[0] or {}).get('status', ''))
        log.info('kalshi.get_market.finish ticker=%s source=live_list_fallback found=true market_status=%s', normalized, (fallbacks[0] or {}).get('status', ''))
        return fallbacks[0]
    historical = get_historical_markets(tickers=normalized, limit=1)
    if historical:
        trace_log('kalshi.get_market.finish', ticker=normalized, source='historical_fallback', found=True, market_status=(historical[0] or {}).get('status', ''))
        log.info('kalshi.get_market.finish ticker=%s source=historical_fallback found=true market_status=%s', normalized, (historical[0] or {}).get('status', ''))
        return historical[0]
    trace_log('kalshi.get_market.finish', ticker=normalized, source='unavailable', found=False)
    log.warning('kalshi.get_market.finish ticker=%s source=unavailable found=false', normalized)
    return {}


def get_markets(category: str = '', limit: int = 20,
                status: str = 'open', event_ticker: str = '') -> list[dict]:
    """Fetch a list of markets, optionally filtered by series or event."""
    params: dict = {'limit': limit}
    if status:
        params['status'] = status
    if category:
        params['series_ticker'] = category
    if event_ticker:
        params['event_ticker'] = event_ticker
    data = _get('/markets', params=params)
    if isinstance(data, dict):
        return data.get('markets', [])
    return []


def get_orderbook(ticker: str) -> dict:
    """Fetch the current orderbook for a market."""
    if not ticker:
        return {}
    data = _get(f'/markets/{ticker}/orderbook')
    if isinstance(data, dict):
        return data.get('orderbook', data)
    return {}


def get_history(ticker: str, series_ticker: str = '', days: int = 30) -> list[dict]:
    """Fetch market candlesticks/history for a market.

    Docs path is `/series/{series_ticker}/markets/{ticker}/candlesticks` and
    requires start/end timestamps plus period interval.
    """
    if not ticker:
        return []
    if not series_ticker:
        market = get_market(ticker)
        event_ticker = market.get('event_ticker', '') if isinstance(market, dict) else ''
        if event_ticker:
            event_payload = get_event(event_ticker, with_nested_markets=False)
            event = event_payload.get('event', {}) if isinstance(event_payload, dict) else {}
            series_ticker = event.get('series_ticker', '') if isinstance(event, dict) else ''
    if not series_ticker:
        return []

    end_ts = int(time.time())
    start_ts = end_ts - max(days, 1) * 86400
    params = {
        'start_ts': start_ts,
        'end_ts': end_ts,
        'period_interval': 1440,
    }
    data = _get(f'/series/{series_ticker}/markets/{ticker}/candlesticks', params=params) or {}
    history = data.get('candlesticks', [])
    if not isinstance(history, list):
        return []
    return history


def _search_market_param_sets(query: str, limit: int) -> list[dict]:
    normalized = (query or '').strip()
    upper = normalized.upper()
    return [
        {'limit': limit, 'status': 'open', 'tickers': normalized},
        {'limit': limit, 'status': 'closed', 'tickers': normalized},
        {'limit': limit, 'status': 'settled', 'tickers': normalized},
        {'limit': limit, 'series_ticker': upper},
        {'limit': limit, 'event_ticker': upper},
    ]


def search_markets(query: str, limit: int = 10) -> list[dict]:
    """Search markets using documented Kalshi market filters only.

    Canonical search is now limited to documented filters like `tickers`,
    `event_ticker`, `series_ticker`, and `status`. Historical fallback belongs
    to separate historical lookup paths rather than undocumented keyword search.
    """
    if not query:
        return []
    trace_log('kalshi.search_markets.start', query=query, limit=limit, attempts=_search_market_param_sets(query, limit))
    for params in _search_market_param_sets(query, limit):
        data = _get('/markets', params=params)
        markets = data.get('markets', []) if isinstance(data, dict) else []
        trace_log('kalshi.search_markets.attempt', query=query, params=params, hit_count=len(markets))
        if markets:
            trace_log('kalshi.search_markets.finish', query=query, source='live_documented_filters', hit_count=len(markets))
            return markets
    historical = get_historical_markets(tickers=(query or '').strip().upper(), limit=limit)
    trace_log('kalshi.search_markets.finish', query=query, source='historical_ticker_fallback', hit_count=len(historical))
    return historical


def get_event(event_ticker: str, with_nested_markets: bool = False) -> dict:
    if not event_ticker:
        return {}
    data = _get(f'/events/{event_ticker}', params={'with_nested_markets': str(with_nested_markets).lower()})
    if isinstance(data, dict):
        return data
    return {}


def get_top_movers(limit: int = 10) -> list[dict]:
    """Fetch the most active/moved markets by volume."""
    params = {'limit': limit, 'status': 'open'}
    data = _get('/markets', params=params)
    markets = []
    if isinstance(data, dict):
        markets = data.get('markets', [])
    markets = sorted(markets, key=lambda m: m.get('volume', 0), reverse=True)
    return markets[:limit]
