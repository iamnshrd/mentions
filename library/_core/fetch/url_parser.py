"""Compatibility shim for legacy ``library._core.fetch.url_parser`` imports."""

from agents.mentions.fetch.url_parser import parse_kalshi_url

__all__ = [
    'parse_kalshi_url',
]
