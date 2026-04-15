"""Core market analysis — summarize price, volume, and status from retrieved data."""
from __future__ import annotations

import logging

from agents.mentions.utils import get_threshold

log = logging.getLogger('mentions')


def analyze_market(market_retrieval: dict, frame: dict) -> str:
    """Produce a human-readable market summary from retrieved data.

    *market_retrieval* is the ``market`` key from the retrieval bundle.
    Returns a text summary string.
    """
    market_data = market_retrieval.get('market_data', {})
    history = market_retrieval.get('history', [])
    ticker = market_retrieval.get('ticker', '')
    cached = market_retrieval.get('cached_analysis', [])

    if not market_data and not history and not cached:
        return _no_data_summary(ticker, frame)

    parts = []

    # Live market snapshot
    if market_data and isinstance(market_data, dict):
        parts.append(_format_snapshot(market_data))

    # Price history summary
    if history and isinstance(history, list) and len(history) > 1:
        parts.append(_format_history_summary(history))

    # Search results (when no specific ticker)
    if isinstance(market_data, dict) and 'search_results' in market_data:
        results = market_data['search_results']
        if results:
            lines = [f'Found {len(results)} matching markets:']
            for m in results[:3]:
                t = m.get('ticker', '?')
                title = m.get('title', '?')
                yes = m.get('yes_bid', m.get('yes_price', '?'))
                lines.append(f'  • {t}: {title} — YES {yes}¢')
            parts.append('\n'.join(lines))

    # Cached analysis hint
    if cached:
        last = cached[0]
        if last.get('conclusion'):
            parts.append(f'Previous analysis: {last["conclusion"]}')

    return '\n'.join(p for p in parts if p) or _no_data_summary(ticker, frame)


def _format_snapshot(market: dict) -> str:
    ticker = market.get('ticker', '')
    title = market.get('title', ticker)
    yes_price = market.get('yes_bid', market.get('yes_price', None))
    no_price = market.get('no_bid', market.get('no_price', None))
    volume = market.get('volume', None)
    status = market.get('status', '')
    close_time = market.get('close_time', '')

    lines = []
    if title:
        lines.append(f'Market: {title}' + (f' ({ticker})' if ticker and ticker != title else ''))
    if yes_price is not None:
        lines.append(f'YES: {yes_price}¢  NO: {no_price}¢' if no_price else f'YES: {yes_price}¢')
    if volume is not None:
        lines.append(f'Volume: {volume:,}' if isinstance(volume, (int, float)) else f'Volume: {volume}')
    if status:
        lines.append(f'Status: {status}')
    if close_time:
        lines.append(f'Closes: {close_time}')
    return '\n'.join(lines)


def _format_history_summary(history: list) -> str:
    """Summarize recent price movement from history list."""
    prices = []
    for entry in history:
        if isinstance(entry, dict):
            p = entry.get('yes_price', entry.get('price', None))
            if p is not None:
                try:
                    prices.append(float(p))
                except (ValueError, TypeError):
                    pass

    if len(prices) < 2:
        return ''

    first = prices[0]
    last = prices[-1]
    low = min(prices)
    high = max(prices)
    change = last - first
    pct = (change / first * 100) if first else 0

    direction = 'up' if change > 0 else 'down' if change < 0 else 'flat'
    return (
        f'Price history ({len(prices)} points): '
        f'{first:.0f}¢ → {last:.0f}¢ '
        f'({direction} {abs(pct):.1f}%) | '
        f'range: {low:.0f}–{high:.0f}¢'
    )


def _no_data_summary(ticker: str, frame: dict) -> str:
    category = frame.get('category', 'general')
    if ticker:
        return f'No live data available for {ticker} (category: {category}). Kalshi API may be unavailable or key not configured.'
    return f'No market data retrieved (category: {category}). Try providing a specific ticker or check Kalshi API configuration.'
