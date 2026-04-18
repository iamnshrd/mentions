"""Compatibility shim for legacy ``library._core.fetch.kalshi`` imports."""

from agents.mentions.fetch.kalshi import (
    get_event,
    get_history,
    get_market,
    get_markets,
    get_orderbook,
    get_top_movers,
    search_markets,
)

__all__ = [
    'get_event',
    'get_history',
    'get_market',
    'get_markets',
    'get_orderbook',
    'get_top_movers',
    'search_markets',
]
