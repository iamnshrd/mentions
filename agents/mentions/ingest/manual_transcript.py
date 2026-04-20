from __future__ import annotations

from pathlib import Path

from agents.mentions.ingest.transcript import _chunk_text, _chunk_text_structured, _extract_text
from agents.mentions.services.transcripts.tagging import build_transcript_tags
from agents.mentions.storage.runtime_db import (
    bootstrap_runtime_db,
    replace_transcript_segments,
    upsert_transcript,
    upsert_transcript_tags,
)


REQUIRED_QUALITY_TAGS = ['manual-transcript']


def ingest_manual_transcript(source_file: str, speaker: str, event: str,
                             event_date: str = '', format_tags: list[str] | None = None,
                             topic_tags: list[str] | None = None,
                             event_tags: list[str] | None = None,
                             mention_tags: list[str] | None = None,
                             quality_tags: list[str] | None = None,
                             notes: str = '') -> dict:
    bootstrap_runtime_db()
    speaker = (speaker or '').strip()
    event = (event or '').strip()
    if not speaker:
        return {'status': 'error', 'error': 'speaker is required'}
    if not event:
        return {'status': 'error', 'error': 'event is required'}

    path = Path(source_file)
    if not path.exists():
        return {'status': 'error', 'error': f'File not found: {path}'}

    raw_text = _extract_text(path)
    if not raw_text:
        return {'status': 'error', 'error': 'Could not extract text from file'}

    transcript_id = upsert_transcript(
        source='manual-intake',
        source_ref=str(path),
        title=event or path.stem,
        speaker_name=speaker,
        event_key=event,
        event_title=event,
        event_date=event_date,
        raw_text=raw_text,
        metadata={'notes': notes, 'intake_mode': 'manual-user-first'},
    )

    chunks = _chunk_text(raw_text)
    structured_chunks = _chunk_text_structured(raw_text)
    replace_transcript_segments(
        transcript_id,
        [
            {
                'segment_index': idx,
                'speaker': speaker,
                'text': chunk.get('text', ''),
                'metadata': {
                    'event': event,
                    'notes': notes,
                    'section_title': chunk.get('section_title', ''),
                    'chunk_kind': chunk.get('chunk_kind', ''),
                    'source_boundary': chunk.get('source_boundary', ''),
                },
            }
            for idx, chunk in enumerate(structured_chunks)
        ],
    )

    transcript_bundle = {
        'speaker': speaker,
        'status': 'ok',
        'summary': raw_text[:500],
    }
    quality_tags = _merge_unique((quality_tags or []) + REQUIRED_QUALITY_TAGS)
    user_tags = {
        'topic_tags': topic_tags or [],
        'format_tags': format_tags or [],
        'event_tags': event_tags or [],
        'mention_tags': mention_tags or [],
        'quality_tags': quality_tags,
    }
    tags = build_transcript_tags(event or path.stem, transcript_bundle, user_tags=user_tags)
    upsert_transcript_tags(transcript_id, tags)

    return {
        'status': 'indexed',
        'transcript_id': transcript_id,
        'file': str(path),
        'speaker': speaker,
        'event': event,
        'event_date': event_date,
        'chunks': len(chunks),
        'user_tags': user_tags,
        'suggested_tags': {
            'topic_tags': tags.get('suggested_topic_tags', []),
            'format_tags': tags.get('suggested_format_tags', []),
            'event_tags': tags.get('suggested_event_tags', []),
            'mention_tags': tags.get('suggested_mention_tags', []),
            'quality_tags': tags.get('suggested_quality_tags', []),
        },
        'effective_tags': {
            'topic_tags': _merge_unique(tags.get('user_topic_tags', []) + tags.get('suggested_topic_tags', [])),
            'format_tags': _merge_unique(tags.get('user_format_tags', []) + tags.get('suggested_format_tags', [])),
            'event_tags': _merge_unique(tags.get('user_event_tags', []) + tags.get('suggested_event_tags', [])),
            'mention_tags': _merge_unique(tags.get('user_mention_tags', []) + tags.get('suggested_mention_tags', [])),
            'quality_tags': _merge_unique(tags.get('user_quality_tags', []) + tags.get('suggested_quality_tags', [])),
        },
    }


def _merge_unique(values: list[str]) -> list[str]:
    merged = []
    for value in values:
        if value and value not in merged:
            merged.append(value)
    return merged
