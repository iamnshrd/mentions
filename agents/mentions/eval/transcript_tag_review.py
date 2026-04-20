from __future__ import annotations

from agents.mentions.storage.runtime_db import connect_runtime_db, upsert_transcript_tags
from agents.mentions.storage.runtime_query import search_transcript_tags_runtime


TAG_FIELDS = ['topic_tags', 'format_tags', 'event_tags', 'mention_tags', 'quality_tags']


def review_transcript_tags(transcript_id: int, accept: dict | None = None, reject: dict | None = None) -> dict:
    accept = accept or {}
    reject = reject or {}
    current = _get_transcript_tag_row(transcript_id)
    if not current:
        return {'status': 'error', 'error': f'transcript_tags not found for transcript_id={transcript_id}'}

    payload = {
        'speaker_primary': current.get('speaker_primary', ''),
        'speaker_aliases': current.get('speaker_aliases', []),
        'speaker_family': current.get('speaker_family', []),
        'topic_family_tags': current.get('topic_family_tags', []),
        'user_topic_tags': current.get('user_topic_tags', []),
        'user_format_tags': current.get('user_format_tags', []),
        'user_event_tags': current.get('user_event_tags', []),
        'user_mention_tags': current.get('user_mention_tags', []),
        'user_quality_tags': current.get('user_quality_tags', []),
        'suggested_topic_tags': current.get('suggested_topic_tags', []),
        'suggested_format_tags': current.get('suggested_format_tags', []),
        'suggested_event_tags': current.get('suggested_event_tags', []),
        'suggested_mention_tags': current.get('suggested_mention_tags', []),
        'suggested_quality_tags': current.get('suggested_quality_tags', []),
        'accepted_suggested_topic_tags': _resolve_accepts(current.get('suggested_topic_tags', []), accept.get('topic_tags', []), reject.get('topic_tags', [])),
        'accepted_suggested_format_tags': _resolve_accepts(current.get('suggested_format_tags', []), accept.get('format_tags', []), reject.get('format_tags', [])),
        'accepted_suggested_event_tags': _resolve_accepts(current.get('suggested_event_tags', []), accept.get('event_tags', []), reject.get('event_tags', [])),
        'accepted_suggested_mention_tags': _resolve_accepts(current.get('suggested_mention_tags', []), accept.get('mention_tags', []), reject.get('mention_tags', [])),
        'accepted_suggested_quality_tags': _resolve_accepts(current.get('suggested_quality_tags', []), accept.get('quality_tags', []), reject.get('quality_tags', [])),
        'rejected_suggested_topic_tags': _unique((current.get('rejected_suggested_topic_tags', []) + reject.get('topic_tags', []))),
        'rejected_suggested_format_tags': _unique((current.get('rejected_suggested_format_tags', []) + reject.get('format_tags', []))),
        'rejected_suggested_event_tags': _unique((current.get('rejected_suggested_event_tags', []) + reject.get('event_tags', []))),
        'rejected_suggested_mention_tags': _unique((current.get('rejected_suggested_mention_tags', []) + reject.get('mention_tags', []))),
        'rejected_suggested_quality_tags': _unique((current.get('rejected_suggested_quality_tags', []) + reject.get('quality_tags', []))),
        'tagging_confidence': current.get('tagging_confidence', 0),
        'tagging_source': current.get('tagging_source', ''),
        'review_status': 'reviewed',
    }
    upsert_transcript_tags(transcript_id, payload)
    return {
        'status': 'reviewed',
        'transcript_id': transcript_id,
        'accepted': {
            field: payload[f'accepted_suggested_{field}'] for field in TAG_FIELDS
        },
        'rejected': {
            field: payload[f'rejected_suggested_{field}'] for field in TAG_FIELDS
        },
    }


def _get_transcript_tag_row(transcript_id: int) -> dict:
    with connect_runtime_db() as conn:
        row = conn.execute('SELECT * FROM transcript_tags WHERE transcript_id = ?', (transcript_id,)).fetchone()
    if not row:
        return {}
    item = dict(row)
    parsed = {}
    import json
    for key, value in item.items():
        if key.endswith('_json'):
            parsed[key[:-5]] = json.loads(value or '[]')
        else:
            parsed[key] = value
    return parsed


def _resolve_accepts(suggested: list[str], explicit_accept: list[str], explicit_reject: list[str]) -> list[str]:
    if explicit_accept:
        return _unique([tag for tag in explicit_accept if tag not in explicit_reject])
    return _unique([tag for tag in suggested if tag not in explicit_reject])


def _unique(values: list[str]) -> list[str]:
    seen = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen
