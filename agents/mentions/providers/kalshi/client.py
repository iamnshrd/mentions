"""Kalshi API client."""
from __future__ import annotations

import json as _json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from mentions_core.base.net.rate_limit import TokenBucket

log = logging.getLogger('mentions')

_PROD_URL = 'https://trading-api.kalshi.com/trade-api/v2'
_DEMO_URL = 'https://demo-api.kalshi.co/trade-api/v2'
_LIMITER = TokenBucket(
    capacity=int(os.environ.get('KALSHI_RATE_CAPACITY', '10')),
    refill_per_sec=float(os.environ.get('KALSHI_RATE_LIMIT', '10.0')),
)
_TTL_LIVE = int(os.environ.get('KALSHI_CACHE_TTL_LIVE', '30'))
_TTL_STATIC = int(os.environ.get('KALSHI_CACHE_TTL_STATIC', '3600'))


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


class _HTTPStatusError(Exception):
    def __init__(self, status_code: int, url: str, body: str = ''):
        super().__init__(f'HTTP {status_code} from {url}')
        self.status_code = status_code
        self.url = url
        self.body = body


def _cache_key(path: str, params: dict | None) -> str:
    env = os.environ.get('KALSHI_ENV', 'demo').lower()
    p = urllib.parse.urlencode(sorted(params.items())) if params else ''
    return f'kalshi:{env}:GET:{path}?{p}'


def _cache_cm():
    try:
        from agents.mentions.db import connect
        return connect()
    except Exception as exc:
        log.debug('_cache_cm failed: %s', exc)
        return None


def _get(path: str, params: dict | None = None,
         timeout: int = 10,
         *, ttl: int | None = _TTL_LIVE,
         use_cache: bool = True) -> dict | list | None:
    from mentions_domain.llm.retry import with_retry
    from mentions_core.base.net import http_cache
    from mentions_core.base.obs import get_collector, trace_event

    metrics = get_collector()
    url = _base_url() + path
    if params:
        url += '?' + urllib.parse.urlencode(params)

    key = _cache_key(path, params) if use_cache else ''
    if key:
        cm = _cache_cm()
        if cm is not None:
            hit, value = False, None
            try:
                with cm as conn:
                    hit, value = http_cache.get(conn, key)
            except Exception as exc:
                log.debug('cache read failed: %s', exc)
            if hit:
                metrics.incr('kalshi.cache_hit', tags={'path': path})
                trace_event('kalshi.call', path=path, cache='hit', ok=True)
                return value
        metrics.incr('kalshi.cache_miss', tags={'path': path})

    waited = _LIMITER.acquire(1)
    if waited > 0:
        metrics.observe('kalshi.rate_limit_wait_ms', waited * 1000.0)

    def _do_request():
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8')
                return _json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = ''
            try:
                body = exc.read().decode('utf-8', errors='replace')[:512]
            except Exception:
                pass
            raise _HTTPStatusError(exc.code, url, body) from exc

    metrics.incr('kalshi.call_attempt', tags={'path': path})
    try:
        with metrics.timed('kalshi.latency_ms', tags={'path': path}):
            data = with_retry(
                _do_request,
                max_attempts=int(os.environ.get('KALSHI_MAX_ATTEMPTS', '3')),
                base_delay=float(os.environ.get('KALSHI_RETRY_BASE', '1.0')),
                on_retry=lambda n, e, d: metrics.incr('kalshi.retry', tags={'path': path}),
            )
    except _HTTPStatusError as exc:
        metrics.incr('kalshi.call_err', tags={'path': path, 'status': str(exc.status_code)})
        trace_event('kalshi.call', path=path, ok=False, status=exc.status_code)
        log.warning('Kalshi %s failed: HTTP %s (%s)', path, exc.status_code, exc.body[:120])
        return None
    except Exception as exc:
        metrics.incr('kalshi.call_err', tags={'path': path})
        trace_event('kalshi.call', path=path, ok=False, error=str(exc))
        log.warning('Kalshi API error [%s]: %s', path, exc)
        return None

    metrics.incr('kalshi.call_ok', tags={'path': path})
    trace_event('kalshi.call', path=path, ok=True, cache='miss')

    if key and ttl and ttl > 0 and data is not None:
        cm = _cache_cm()
        if cm is not None:
            try:
                with cm as conn:
                    http_cache.put(conn, key, data, ttl_seconds=ttl)
            except Exception as exc:
                log.debug('cache write failed: %s', exc)
    return data


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
    results: list[dict] = []
    seen: set[str] = set()
    for params in params_list:
        data = _get('/markets', params=params)
        markets = data.get('markets', []) if isinstance(data, dict) else []
        for market in markets:
            market_ticker = str((market or {}).get('ticker') or '').upper()
            if market_ticker != ticker or market_ticker in seen:
                continue
            seen.add(market_ticker)
            results.append(market)
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
    data = _get('/historical/markets', params=params)
    markets = data.get('markets', []) if isinstance(data, dict) else []
    return markets


def get_market(ticker: str) -> dict:
    """Fetch a single market by ticker. Returns market dict or {}."""
    if not ticker:
        return {}
    normalized = (ticker or '').strip().upper()
    data = _get(f'/markets/{normalized}')
    if isinstance(data, dict):
        market = data.get('market', data)
        if isinstance(market, dict) and market:
            return market
    fallbacks = _market_search_fallbacks(normalized)
    if fallbacks:
        return fallbacks[0]
    historical = get_historical_markets(tickers=normalized, limit=1)
    if historical:
        return historical[0]
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
    for params in _search_market_param_sets(query, limit):
        data = _get('/markets', params=params)
        markets = data.get('markets', []) if isinstance(data, dict) else []
        if markets:
            return markets
    historical = get_historical_markets(tickers=(query or '').strip().upper(), limit=limit)
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
