"""Kalshi API client.

Wraps the Kalshi REST API for markets, orderbook, and price history.
All functions return plain dicts/lists; callers handle persistence.

Production hardening (v0.12):

* **Rate limit** — a module-global :class:`TokenBucket` paces calls at
  ``KALSHI_RATE_LIMIT`` req/s (default 10, matches the Kalshi public
  ceiling). ``acquire()`` blocks when the bucket is empty.
* **Response cache** — successful GETs are cached in SQLite with a
  configurable TTL (``live_ttl=30s`` for market data,
  ``static_ttl=3600s`` for metadata). Misses + bypass queries never
  pay cache overhead.
* **Retry** — transient failures (429, 5xx, connection errors) are
  retried with exponential backoff using :func:`with_retry` from the
  LLM retry layer.
* **Metrics + trace** — every call emits ``kalshi.call_attempt``,
  ``kalshi.call_ok`` / ``kalshi.call_err``, ``kalshi.cache_hit`` /
  ``kalshi.cache_miss``, ``kalshi.latency_ms``, and a
  ``kalshi.call`` trace event.

Set ``KALSHI_API_KEY`` and ``KALSHI_API_URL`` (or ``KALSHI_ENV=demo``)
in environment.
"""
from __future__ import annotations

import json as _json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

from library._core.fetch.rate_limit import TokenBucket

log = logging.getLogger('mentions')

_PROD_URL = 'https://trading-api.kalshi.com/trade-api/v2'
_DEMO_URL = 'https://demo-api.kalshi.co/trade-api/v2'

# Module-global rate limiter. Configurable via env for tests / lower tiers.
_LIMITER = TokenBucket(
    capacity=int(os.environ.get('KALSHI_RATE_CAPACITY', '10')),
    refill_per_sec=float(os.environ.get('KALSHI_RATE_LIMIT', '10.0')),
)

# Default TTLs (seconds). Callers that want static behaviour pass
# ``ttl=...`` to :func:`_get` directly; these are just defaults.
_TTL_LIVE   = int(os.environ.get('KALSHI_CACHE_TTL_LIVE',   '30'))
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
    """Wraps a non-2xx HTTP response so :func:`is_retryable` can classify it."""

    def __init__(self, status_code: int, url: str, body: str = ''):
        super().__init__(f'HTTP {status_code} from {url}')
        self.status_code = status_code
        self.url         = url
        self.body        = body


def _cache_key(path: str, params: dict | None) -> str:
    env = os.environ.get('KALSHI_ENV', 'demo').lower()
    if params:
        p = urllib.parse.urlencode(sorted(params.items()))
    else:
        p = ''
    return f'kalshi:{env}:GET:{path}?{p}'


def _cache_cm():
    """Return a context-manager yielding a SQLite connection, or None.

    Wraps :func:`library.db.connect` so callers can ``with _cache_cm() as c:``.
    Returns None if the DB layer is unavailable (e.g. import errors in tests).
    """
    try:
        from library.db import connect
        return connect()
    except Exception as exc:  # pragma: no cover — bare safety net
        log.debug('_cache_cm failed: %s', exc)
        return None


def _get(path: str, params: dict | None = None,
         timeout: int = 10,
         *, ttl: int | None = _TTL_LIVE,
         use_cache: bool = True) -> dict | list | None:
    """GET a Kalshi API path. Returns parsed JSON or ``None`` on failure.

    ``ttl`` controls the response cache (``None`` disables writes for
    this call; reads still happen unless ``use_cache=False``).
    """
    from library._core.llm.retry import with_retry
    from library._core.obs import get_collector, trace_event
    from library._core.fetch import http_cache

    metrics = get_collector()
    url = _base_url() + path
    if params:
        url += '?' + urllib.parse.urlencode(params)

    key = _cache_key(path, params) if use_cache else ''

    # ── Cache read ─────────────────────────────────────────────────────────
    if key:
        cm = _cache_cm()
        if cm is not None:
            hit, value = False, None
            try:
                with cm as conn:
                    hit, value = http_cache.get(conn, key)
            except Exception as exc:  # pragma: no cover
                log.debug('cache read failed: %s', exc)
            if hit:
                metrics.incr('kalshi.cache_hit', tags={'path': path})
                trace_event('kalshi.call', path=path, cache='hit', ok=True)
                return value

    if key:
        metrics.incr('kalshi.cache_miss', tags={'path': path})

    # ── Rate-limit + HTTP ──────────────────────────────────────────────────
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
                on_retry=lambda n, e, d: metrics.incr(
                    'kalshi.retry', tags={'path': path}),
            )
    except _HTTPStatusError as exc:
        log.warning('Kalshi %s failed: HTTP %s (%s)',
                    path, exc.status_code, exc.body[:120])
        metrics.incr('kalshi.call_err',
                     tags={'path': path, 'status': str(exc.status_code)})
        trace_event('kalshi.call', path=path, ok=False,
                    status=exc.status_code)
        return None
    except Exception as exc:
        log.warning('Kalshi API error [%s]: %s', path, exc)
        metrics.incr('kalshi.call_err', tags={'path': path})
        trace_event('kalshi.call', path=path, ok=False, error=str(exc))
        return None

    metrics.incr('kalshi.call_ok', tags={'path': path})
    trace_event('kalshi.call', path=path, ok=True, cache='miss')

    # ── Cache write ───────────────────────────────────────────────────────
    if key and ttl and ttl > 0 and data is not None:
        cm = _cache_cm()
        if cm is not None:
            try:
                with cm as conn:
                    http_cache.put(conn, key, data, ttl_seconds=ttl)
            except Exception as exc:  # pragma: no cover
                log.debug('cache write failed: %s', exc)
    return data


def get_market(ticker: str) -> dict:
    """Fetch a single market by ticker. Returns market dict or {}."""
    if not ticker:
        return {}
    data = _get(f'/markets/{ticker}')
    if isinstance(data, dict):
        return data.get('market', data)
    return {}


def get_markets(category: str = '', limit: int = 20,
                status: str = 'open') -> list[dict]:
    """Fetch a list of markets, optionally filtered by category."""
    params: dict = {'limit': limit, 'status': status}
    if category:
        params['series_ticker'] = category
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


def get_history(ticker: str, days: int = 30) -> list[dict]:
    """Fetch price history for a market.

    Returns a list of {ts, yes_price, volume} dicts, newest last.
    """
    if not ticker:
        return []
    # Kalshi history endpoint uses series/candlesticks
    params = {'series_ticker': ticker, 'period_interval': 1440}  # daily candles
    data = _get(f'/series/{ticker}/markets/history', params=params)
    if not isinstance(data, dict):
        # Try alternate endpoint
        data = _get(f'/markets/{ticker}/history', params={'limit': days}) or {}

    history = data.get('history', data.get('candles', []))
    if not isinstance(history, list):
        return []
    return history


def search_markets(query: str, limit: int = 10) -> list[dict]:
    """Search markets by keyword."""
    if not query:
        return []
    params = {'limit': limit, 'keyword': query, 'status': 'open'}
    data = _get('/markets', params=params)
    if isinstance(data, dict):
        return data.get('markets', [])
    return []


def get_top_movers(limit: int = 10) -> list[dict]:
    """Fetch the most active/moved markets by volume."""
    params = {'limit': limit, 'status': 'open'}
    data = _get('/markets', params=params)
    markets = []
    if isinstance(data, dict):
        markets = data.get('markets', [])
    # Sort by volume descending
    markets = sorted(markets, key=lambda m: m.get('volume', 0), reverse=True)
    return markets[:limit]
