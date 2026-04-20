"""Transcripts capability interface."""

from agents.mentions.interfaces.capabilities.transcripts.api import (
    build_kb,
    ingest_auto,
    ingest_manual_transcript,
    ingest_transcript,
    search_transcripts,
)
from agents.mentions.interfaces.capabilities.transcripts.service import TranscriptsCapabilityService

__all__ = [
    'TranscriptsCapabilityService',
    'build_kb',
    'ingest_auto',
    'ingest_manual_transcript',
    'ingest_transcript',
    'search_transcripts',
]
