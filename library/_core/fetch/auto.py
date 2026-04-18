"""Compatibility shim for legacy ``library._core.fetch.auto`` imports."""

from agents.mentions.fetch.auto import fetch_all

__all__ = [
    'fetch_all',
]
