"""Programmatic API for the transcripts capability."""
from __future__ import annotations

from agents.mentions.ingest.auto import ingest as ingest_auto_impl
from agents.mentions.ingest.transcript import register as register_transcript
from agents.mentions.kb.build import build as build_kb_impl
from agents.mentions.kb.query import query_transcripts as raw_query_transcripts
from agents.mentions.utils import fts_query


def ingest_auto(dry_run: bool = False) -> dict:
    return ingest_auto_impl(dry_run=dry_run)


def ingest_transcript(source_file: str, speaker: str = '', event: str = '',
                      event_date: str = '') -> dict:
    return register_transcript(source_file, speaker=speaker, event=event, event_date=event_date)


def build_kb() -> dict:
    return build_kb_impl()


def search_transcripts(query: str, limit: int = 5, speaker: str = '') -> list[dict]:
    search = fts_query(query)
    if not search:
        return []
    return raw_query_transcripts(search, limit=limit, speaker=speaker)
