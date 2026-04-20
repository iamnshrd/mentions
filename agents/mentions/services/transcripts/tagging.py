from __future__ import annotations

from mentions_domain.normalize import ensure_dict


TOPIC_FAMILY_MAP = {
    'iran': 'middle-east',
    'oil': 'energy',
    'inflation': 'macro',
    'rates': 'macro',
    'fed': 'macro',
}

FORMAT_ALIASES = {
    'press conference': 'press-conference',
    'prepared remarks': 'prepared-remarks',
    'q&a': 'q-and-a',
}


def build_transcript_tags(query: str, transcript_bundle: dict, user_tags: dict | None = None) -> dict:
    transcript_bundle = ensure_dict(transcript_bundle)
    user_tags = ensure_dict(user_tags)
    speaker = (transcript_bundle.get('speaker') or '').strip()
    summary = (transcript_bundle.get('summary') or '').lower()
    query_lower = (query or '').lower()

    user_topic_tags = _normalize_tag_list(user_tags.get('topic_tags', []))
    user_format_tags = _normalize_tag_list(user_tags.get('format_tags', []), alias_map=FORMAT_ALIASES)
    user_event_tags = _normalize_tag_list(user_tags.get('event_tags', []))
    user_mention_tags = _normalize_tag_list(user_tags.get('mention_tags', []))
    user_quality_tags = _normalize_tag_list(user_tags.get('quality_tags', []))

    topic_tags = []
    topic_family_tags = []
    for topic, family in TOPIC_FAMILY_MAP.items():
        if topic in query_lower or topic in summary:
            topic_tags.append(topic)
            if family not in topic_family_tags:
                topic_family_tags.append(family)

    format_tags = []
    for fmt in ['speech', 'interview', 'press conference', 'q&a', 'prepared remarks']:
        if fmt in query_lower or fmt in summary:
            normalized = FORMAT_ALIASES.get(fmt, fmt.replace(' ', '-'))
            if normalized not in format_tags:
                format_tags.append(normalized)

    mention_tags = []
    if 'mention' in query_lower:
        mention_tags.append('mention-market-relevant')
    if topic_tags:
        mention_tags.append('topic-discussion')

    quality_tags = ['runtime-generated-tags']
    if transcript_bundle.get('status') == 'ok':
        quality_tags.append('transcript-backed')

    return {
        'speaker_primary': speaker,
        'speaker_aliases': [speaker] if speaker else [],
        'speaker_family': [speaker.lower()] if speaker else [],
        'topic_tags': topic_tags,
        'topic_family_tags': topic_family_tags,
        'format_tags': format_tags,
        'event_tags': [],
        'mention_tags': mention_tags,
        'quality_tags': quality_tags,
        'user_topic_tags': user_topic_tags,
        'user_format_tags': user_format_tags,
        'user_event_tags': user_event_tags,
        'user_mention_tags': user_mention_tags,
        'user_quality_tags': user_quality_tags,
        'suggested_topic_tags': topic_tags,
        'suggested_format_tags': format_tags,
        'suggested_event_tags': [],
        'suggested_mention_tags': mention_tags,
        'suggested_quality_tags': quality_tags,
        'tagging_confidence': 0.6 if topic_tags or format_tags else 0.3,
        'tagging_source': 'schema_first_runtime_v1',
    }


def _normalize_tag_list(values: list[str] | None, alias_map: dict[str, str] | None = None) -> list[str]:
    alias_map = alias_map or {}
    normalized = []
    for value in values or []:
        item = (value or '').strip().lower()
        if not item:
            continue
        item = alias_map.get(item, item.replace(' ', '-'))
        if item not in normalized:
            normalized.append(item)
    return normalized
