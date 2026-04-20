from __future__ import annotations

from agents.mentions.services.intake.url_parser import parse_kalshi_url


def intake_market_input(user_input: str) -> dict:
    raw = (user_input or '').strip()
    parsed = parse_kalshi_url(raw)
    is_url = bool(parsed.get('is_kalshi_url'))
    ticker = parsed.get('ticker', '')
    speaker_info = parsed.get('speaker_info', {}) or {}

    return {
        'raw_input': raw,
        'input_type': 'kalshi_url' if is_url else 'text_or_ticker',
        'ticker': ticker,
        'series_slug': parsed.get('series_slug', ''),
        'pretty_slug': parsed.get('pretty_slug', ''),
        'speaker_slug': parsed.get('speaker_slug', ''),
        'speaker_info': speaker_info,
        'event_type': parsed.get('event_type', 'unknown'),
        'ticker_kind': parsed.get('ticker_kind', 'unknown'),
        'is_url': is_url,
        'is_direct_ticker': bool(ticker and not is_url),
        'has_explicit_url_ticker': bool(is_url and ticker),
    }
