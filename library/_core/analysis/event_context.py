"""Compatibility shim for legacy ``library._core.analysis.event_context`` imports."""

from agents.mentions.analysis.event_context import analyze_event_context

__all__ = [
    'analyze_event_context',
]
