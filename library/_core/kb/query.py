"""Compatibility shim for legacy ``library._core.kb.query`` imports."""

from agents.mentions.kb.query import (
    query,
    query_analysis_cache,
    query_markets,
    query_transcripts,
    save_analysis,
)

__all__ = [
    'query',
    'query_analysis_cache',
    'query_markets',
    'query_transcripts',
    'save_analysis',
]
