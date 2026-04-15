"""Kalshi API client.

Wraps the Kalshi REST API for markets, orderbook, and price history.
All functions return plain dicts/lists; callers handle persistence.

Set KALSHI_API_KEY and KALSHI_API_URL (or KALSHI_ENV=demo) in environment.
"""
from __future__ import annotations

import logging
import os
import time
from functools import lru_cache

log = logging.getLogger('mentions')

_PROD_URL = 'https://trading-api.kalshi.com/trade-api/v2'
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
    url = _base_url() + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        log.warning('Kalshi API error [%s]: %s', path, exc)
        return None


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
