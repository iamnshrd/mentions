"""Compatibility shim for legacy ``library._core.analysis.speaker_extract`` imports."""

from agents.mentions.analysis.speaker_extract import (
    analyse_speaker_tendency,
    extract_speaker,
    extract_speaker_from_ticker,
)

__all__ = [
    'analyse_speaker_tendency',
    'extract_speaker',
    'extract_speaker_from_ticker',
]
