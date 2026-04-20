from __future__ import annotations

from agents.mentions.module_contracts import ensure_dict, ensure_list
from agents.mentions.modules.market_resolution.extraction import extract_market_entities
from agents.mentions.storage.runtime_query import search_transcript_tags_runtime, search_transcripts_runtime


TOPIC_EXPANSIONS = {
    'iran': ['iran', 'tehran', 'middle east', 'nuclear', 'deal'],
    'oil': ['oil', 'energy', 'gas', 'prices'],
    'inflation': ['inflation', 'prices', 'fed', 'rates'],
}


def retrieve_relevant_speaker_events(query: str, transcript_bundle: dict, market: dict, limit: int = 5) -> dict:
    transcript_bundle = ensure_dict(transcript_bundle)
    market = ensure_dict(market)

    entities = extract_market_entities(query)
    speakers = entities.get('speakers', []) or []
    topics = [topic.lower() for topic in (entities.get('topics', []) or [])]
    speaker = transcript_bundle.get('speaker', '') or (speakers[0] if speakers else '')
    if not speaker:
        return {
            'speaker': '',
            'status': 'empty',
            'events': [],
            'rejection_reasons': ['no-speaker-match'],
        }

    topic_queries = _topic_expansion_queries(topics)
    format_tags = _format_hints(query)
    rejected_pairs = set()
    tag_rows = search_transcript_tags_runtime(
        speaker=speaker,
        topic_tags=topics,
        format_tags=format_tags,
        limit=limit * 3,
    )

    rows = []
    for search_query in [speaker] + topic_queries:
        rows.extend(search_transcripts_runtime(query=search_query, speaker=speaker, limit=limit * 5))

    transcript_by_event = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_title = (row.get('event_title') or row.get('event') or '').strip()
        text = (row.get('text') or '').strip()
        if event_title and text and event_title not in transcript_by_event:
            transcript_by_event[event_title] = row

    candidates = []
    rejections = []
    seen_events = set()

    for tag_row in tag_rows:
        event_title = (tag_row.get('event_title') or tag_row.get('event_key') or '').strip()
        if not event_title or event_title in seen_events:
            continue
        topic_matches = [
            topic for topic in topics
            if topic in ensure_list(tag_row.get('topic_tags', []))
            or topic in ensure_list(tag_row.get('topic_family_tags', []))
        ]
        if topics and not topic_matches:
            _add_rejection(rejections, rejected_pairs, event_title, 'tag-topic-mismatch')
            continue
        format_matches = [fmt for fmt in format_tags if fmt in ensure_list(tag_row.get('format_tags', []))]
        if format_tags and not format_matches:
            _add_rejection(rejections, rejected_pairs, event_title, 'tag-format-mismatch')
            continue
        transcript_row = transcript_by_event.get(event_title)
        if not transcript_row:
            _add_rejection(rejections, rejected_pairs, event_title, 'missing-transcript-backing')
            continue
        seen_events.add(event_title)
        relevance_score = 2.0 + len(topic_matches) * 1.0 + len(format_matches) * 0.75 + float(tag_row.get('tagging_confidence', 0) or 0)
        candidates.append({
            'event_title': event_title,
            'speaker': speaker,
            'topic_matches': topic_matches,
            'format_matches': format_matches,
            'transcript_excerpt': (transcript_row.get('text') or '')[:240],
            'source': 'runtime_transcript_tags+corpus',
            'relevance_score': round(relevance_score, 3),
            'tagging_confidence': tag_row.get('tagging_confidence', 0),
        })

    shortlisted_titles = {item['event_title'] for item in candidates}
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_title = (row.get('event_title') or row.get('event') or '').strip()
        text = (row.get('text') or '').strip()
        if not event_title or not text:
            if event_title not in shortlisted_titles:
                _add_rejection(rejections, rejected_pairs, event_title or 'unknown', 'missing-transcript-backing')
            continue
        if event_title in seen_events or event_title in shortlisted_titles:
            continue
        text_blob = f"{event_title} {text}".lower()
        topic_matches = _topic_matches(text_blob, topics)
        if topics and not topic_matches:
            _add_rejection(rejections, rejected_pairs, event_title, 'topic-mismatch')
            continue
        format_matches = _format_matches(text_blob, format_tags)
        if format_tags and not format_matches:
            _add_rejection(rejections, rejected_pairs, event_title, 'format-mismatch')
            continue
        seen_events.add(event_title)
        candidates.append({
            'event_title': event_title,
            'speaker': speaker,
            'topic_matches': topic_matches,
            'format_matches': format_matches,
            'transcript_excerpt': text[:240],
            'source': 'runtime_transcript_corpus',
            'relevance_score': round(1.0 + len(topic_matches) * 1.0 + len(format_matches) * 0.5 + (0.5 if speaker else 0), 3),
        })

    candidates.sort(key=lambda item: item.get('relevance_score', 0), reverse=True)
    shortlisted = candidates[:limit]
    status = 'ok' if shortlisted else 'empty'
    return {
        'speaker': speaker,
        'status': status,
        'events': shortlisted,
        'rejection_reasons': rejections[:10],
    }


def _topic_expansion_queries(topics: list[str]) -> list[str]:
    queries = []
    for topic in topics:
        for expanded in TOPIC_EXPANSIONS.get(topic, [topic]):
            if expanded not in queries:
                queries.append(expanded)
    return queries[:6]


def _format_hints(query: str) -> list[str]:
    query = (query or '').lower()
    hints = []
    mapping = {
        'speech': ['speech', 'prepared-remarks'],
        'interview': ['interview'],
        'press conference': ['press-conference', 'q-and-a'],
        'q&a': ['q-and-a'],
        'prepared remarks': ['prepared-remarks', 'speech'],
        'rally': ['rally'],
    }
    for needle, tags in mapping.items():
        if needle in query:
            for tag in tags:
                if tag not in hints:
                    hints.append(tag)
    return hints


def _add_rejection(rejections: list[dict], rejected_pairs: set[tuple[str, str]], event_title: str, reason: str) -> None:
    key = (event_title, reason)
    if key in rejected_pairs:
        return
    rejected_pairs.add(key)
    rejections.append({'event_title': event_title, 'reason': reason})


def _topic_matches(text_blob: str, topics: list[str]) -> list[str]:
    matches = []
    for topic in topics:
        candidates = TOPIC_EXPANSIONS.get(topic, [topic])
        if any(candidate in text_blob for candidate in candidates):
            matches.append(topic)
    return matches


def _format_matches(text_blob: str, format_tags: list[str]) -> list[str]:
    if not format_tags:
        return []
    aliases = {
        'press-conference': ['press conference', 'briefing', 'presser'],
        'q-and-a': ['q&a', 'question', 'questions', 'asked'],
        'prepared-remarks': ['prepared remarks', 'remarks', 'speech'],
        'speech': ['speech', 'address', 'remarks'],
        'interview': ['interview'],
        'rally': ['rally'],
    }
    matches = []
    for fmt in format_tags:
        needles = aliases.get(fmt, [fmt.replace('-', ' ')])
        if any(needle in text_blob for needle in needles):
            matches.append(fmt)
    return matches
