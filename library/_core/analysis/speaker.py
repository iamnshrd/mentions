"""Compatibility shim for legacy ``library._core.analysis.speaker`` imports."""

from agents.mentions.analysis.speaker import extract_speaker_context

__all__ = [
    'extract_speaker_context',
]
