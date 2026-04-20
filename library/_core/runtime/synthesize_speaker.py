"""Compatibility shim for legacy ``library._core.runtime.synthesize_speaker`` imports."""

from agents.mentions.runtime.synthesize_speaker import synthesize_speaker_market

__all__ = [
    'synthesize_speaker_market',
]
