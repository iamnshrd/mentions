"""Legacy fetch facade for package-level compatibility imports."""

from library._core.fetch.auto import fetch_all
from library._core.fetch.kalshi import (
    get_history,
    get_market,
    get_markets,
    get_orderbook,
    get_top_movers,
    search_markets,
)
from library._core.fetch.news import fetch_news, fetch_news_with_status
from library._core.fetch.url_parser import parse_kalshi_url

__all__ = [
    'fetch_all',
    'fetch_news',
    'fetch_news_with_status',
    'get_history',
    'get_market',
    'get_markets',
    'get_orderbook',
    'get_top_movers',
    'parse_kalshi_url',
    'search_markets',
]
