"""Canonical transcripts capability API entrypoint."""
from __future__ import annotations

from agents.mentions.ingest.auto import ingest as ingest_auto_impl
from agents.mentions.ingest.manual_transcript import ingest_manual_transcript as ingest_manual_transcript_impl
from agents.mentions.ingest.transcript import register as register_transcript
from agents.mentions.services.knowledge import build as build_kb_impl
from agents.mentions.services.knowledge import query_transcripts as raw_query_transcripts
from agents.mentions.utils import fts_query


def ingest_auto(dry_run: bool = False) -> dict:
    return ingest_auto_impl(dry_run=dry_run)


def ingest_transcript(source_file: str, speaker: str = '', event: str = '',
                      event_date: str = '') -> dict:
    return register_transcript(source_file, speaker=speaker, event=event, event_date=event_date)


def ingest_manual_transcript(source_file: str, speaker: str = '', event: str = '',
                             event_date: str = '', format_tags: list[str] | None = None,
                             topic_tags: list[str] | None = None,
                             event_tags: list[str] | None = None,
                             mention_tags: list[str] | None = None,
                             quality_tags: list[str] | None = None,
                             notes: str = '') -> dict:
    return ingest_manual_transcript_impl(
        source_file,
        speaker=speaker,
        event=event,
        event_date=event_date,
        format_tags=format_tags,
        topic_tags=topic_tags,
        event_tags=event_tags,
        mention_tags=mention_tags,
        quality_tags=quality_tags,
        notes=notes,
    )


def build_kb() -> dict:
    return build_kb_impl()


def search_transcripts(query: str, limit: int = 5, speaker: str = '') -> list[dict]:
    search = fts_query(query)
    if not search:
        return []
    return raw_query_transcripts(search, limit=limit, speaker=speaker)


__all__ = [
    'build_kb',
    'ingest_auto',
    'ingest_manual_transcript',
    'ingest_transcript',
    'search_transcripts',
]
