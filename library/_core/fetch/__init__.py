"""Legacy compatibility barrel for historical ``library._core.fetch`` imports.

Current code should prefer `agents.mentions.fetch.*` or the higher-level
provider/module surfaces in `agents.mentions.modules.*`.

This barrel should stay as a thin re-export surface only. Do not add new fetch
logic here.
"""

from agents.mentions.fetch.auto import fetch_all
from agents.mentions.fetch.kalshi import (
    get_history,
    get_market,
    get_markets,
    get_orderbook,
    get_top_movers,
    search_markets,
)
from agents.mentions.fetch.news import fetch_news, fetch_news_with_status
from agents.mentions.fetch.url_parser import parse_kalshi_url

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
