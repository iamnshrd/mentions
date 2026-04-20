from __future__ import annotations

import logging

from agents.mentions.interfaces.capabilities.transcripts.api import search_transcripts
from mentions_domain.normalize import ensure_list, normalize_status
from mentions_domain.market_resolution import extract_market_entities
from agents.mentions.storage.runtime_query import search_transcript_tags_runtime, search_transcripts_runtime, get_transcript_segment_window, get_transcript_segments
from agents.mentions.utils import fts_query

log = logging.getLogger('mentions')


TOPIC_QUERY_EXPANSIONS = {
    'iran': ['iran', 'tehran', 'middle east', 'nuclear', 'deal'],
    'oil': ['oil', 'energy', 'gas'],
    'inflation': ['inflation', 'prices', 'fed', 'rates'],
    'tax': ['tax', 'taxes', 'ratepayer'],
    'tips': ['tips', 'service workers'],
}

PHRASE_TOPICS = {
    'no tax on tips': ['no tax on tips'],
}


def build_transcript_intelligence_bundle(query: str, limit: int = 5, speaker: str = '') -> dict:
    if not fts_query(query):
        return _empty_bundle(query, speaker=speaker, reason='empty-search')

    entities = extract_market_entities(query)
    inferred_speaker = speaker or _infer_speaker(entities)
    effective_query = _build_effective_query(query, entities)
    chunks = _search_transcript_candidates(effective_query, entities, inferred_speaker, limit=limit)

    transcript_knowledge = {}
    try:
        from agents.mentions.services.transcripts.knowledge_extraction import extract_transcript_knowledge_bundle
        transcript_knowledge = extract_transcript_knowledge_bundle(query, {'chunks': chunks})
    except Exception as exc:
        log.debug('extract_transcript_knowledge_bundle failed: %s', exc)
        transcript_knowledge = {}

    format_hints = _format_hints(effective_query)
    topics = [topic.lower() for topic in (entities.get('topics', []) or [])]
    top_candidates = [_candidate_view(chunk, inferred_speaker, format_hints, topics) for chunk in chunks[:limit]]
    same_speaker_hits = sum(1 for item in top_candidates if item.get('speaker_match'))
    same_format_hits = sum(1 for item in top_candidates if item.get('format_match'))
    same_topic_hits = sum(1 for item in top_candidates if item.get('topic_match'))
    support_strength = _support_strength(same_speaker_hits, same_format_hits, same_topic_hits)

    return {
        'query': query,
        'effective_query': effective_query,
        'speaker': inferred_speaker,
        'status': normalize_status('ok' if chunks else 'empty', default='empty'),
        'chunks': chunks,
        'summary': _summarize_chunks(chunks),
        'top_speakers': _top_values(chunks, 'speaker'),
        'top_events': _top_values(chunks, 'event'),
        'context_risks': _context_risks(chunks, inferred_speaker),
        'knowledge_bundle': transcript_knowledge,
        'query_target': {
            'speaker': inferred_speaker,
            'event_format': format_hints[:1],
            'topic_candidates': topics[:5],
        },
        'speaker_context': {
            'speaker': inferred_speaker,
            'same_speaker_hits': same_speaker_hits,
            'support_strength': support_strength,
            'tendency_summary': _tendency_summary(top_candidates, inferred_speaker),
        },
        'format_analogs': [item for item in top_candidates if item.get('format_match')][:3],
        'topic_analogs': [item for item in top_candidates if item.get('topic_match')][:3],
        'counterevidence': [item for item in top_candidates if item.get('speaker_match') and not item.get('topic_match')][:3],
        'top_candidates': top_candidates,
        'retrieval_summary': _retrieval_summary(top_candidates, inferred_speaker),
    }


def _infer_speaker(entities: dict) -> str:
    speakers = entities.get('speakers', []) or []
    return speakers[0] if speakers else ''


def _summarize_chunks(chunks: list[dict]) -> str:
    snippets = []
    for chunk in chunks[:3]:
        text = (chunk.get('text') or chunk.get('content') or '').strip()
        if text:
            snippets.append(text[:180].replace('\n', ' '))
    return ' | '.join(snippets)


def _top_values(chunks: list[dict], key: str) -> list[str]:
    seen = []
    for chunk in chunks:
        value = (chunk.get(key) or '').strip()
        if value and value not in seen:
            seen.append(value)
    return seen[:3]


def _context_risks(chunks: list[dict], speaker: str) -> list[str]:
    risks = []
    if not chunks:
        risks.append('no-transcript-hits')
    if speaker and not any((chunk.get('speaker') or '').strip() == speaker for chunk in chunks):
        risks.append('speaker-not-confirmed-in-results')
    return risks


def _search_transcript_candidates(effective_query: str, entities: dict, speaker: str, limit: int = 5) -> list[dict]:
    queries = []
    if effective_query:
        queries.append(effective_query)
    for candidate in _expanded_queries(entities):
        if candidate not in queries:
            queries.append(candidate)

    topics = [topic.lower() for topic in (entities.get('topics', []) or [])]
    format_hints = _format_hints(effective_query)
    event_hints = _event_hints(effective_query)
    phrase_topics = _phrase_topics(effective_query)
    chunks = []

    tag_rows = _safe_search_transcript_tags_runtime(
        speaker=speaker,
        topic_tags=topics,
        format_tags=format_hints,
        limit=limit * 6,
    )
    if format_hints:
        format_only_rows = _safe_search_transcript_tags_runtime(
            speaker=speaker,
            topic_tags=[],
            format_tags=format_hints,
            limit=limit * 6,
        )
        seen_tag_ids = {row.get('transcript_id') for row in tag_rows}
        for row in format_only_rows:
            if row.get('transcript_id') not in seen_tag_ids:
                tag_rows.append(row)
                seen_tag_ids.add(row.get('transcript_id'))
    runtime_rows = []
    if speaker:
        runtime_rows = _search_runtime_rows(query=speaker, speaker=speaker, limit=limit * 10)
    explicit_rows = []
    if speaker and format_hints:
        for fmt in format_hints:
            explicit_rows.extend(_search_runtime_rows(speaker=speaker, title_query=fmt, limit=limit * 10))
    for hint in event_hints:
        if speaker:
            explicit_rows.extend(_search_runtime_rows(speaker=speaker, title_query=hint, limit=limit * 10))
    runtime_by_event = {}
    for row in runtime_rows + explicit_rows:
        event_title = row.get('event_title') or row.get('event_key') or row.get('event') or ''
        if event_title and event_title not in runtime_by_event:
            runtime_by_event[event_title] = row

    scored_by_id = {}

    def merge_scored(item: dict):
        row_id = item.get('id') or item.get('transcript_id') or f"{item.get('event','')}::{(item.get('text','') or '')[:60]}"
        existing = scored_by_id.get(row_id)
        if not existing or item.get('retrieval_score', 0) > existing.get('retrieval_score', 0):
            scored_by_id[row_id] = item

    for tag_row in tag_rows:
        event_title = tag_row.get('event_title') or tag_row.get('event_key') or ''
        runtime_row = runtime_by_event.get(event_title)
        if not runtime_row:
            continue
        topic_matches = [topic for topic in topics if topic in ensure_list(tag_row.get('topic_tags', [])) or topic in ensure_list(tag_row.get('topic_family_tags', []))]
        format_matches = [fmt for fmt in format_hints if fmt in ensure_list(tag_row.get('format_tags', []))]
        event_title_lower = event_title.lower()
        event_match_bonus = _event_match_bonus(event_title_lower, event_hints)
        phrase_matches = _phrase_matches(event_title_lower, phrase_topics)
        if format_hints and not format_matches and event_match_bonus <= 0 and not phrase_matches:
            continue
        title_topic_matches = _title_topic_matches(event_title_lower, topics)
        score = 2.0 + len(phrase_matches) * 3.0 + len(title_topic_matches) * 1.5 + len(topic_matches) * 0.25 + len(format_matches) * 1.8 + event_match_bonus + float(tag_row.get('tagging_confidence', 0) or 0)
        merge_scored({
            'id': runtime_row.get('transcript_id'),
            'text': runtime_row.get('text', ''),
            'speaker': runtime_row.get('speaker', ''),
            'event': event_title,
            'tag_topic_matches': phrase_matches or title_topic_matches or topic_matches,
            'tag_format_matches': format_matches,
            'tagging_confidence': tag_row.get('tagging_confidence', 0),
            'retrieval_source': 'runtime_transcript_tags+corpus',
            'retrieval_score': round(score, 3),
        })

    for candidate in queries[:8]:
        for row in ensure_list(search_transcripts(candidate, limit=limit, speaker=speaker)):
            row = dict(row)
            event_title_lower = (row.get('event', '') or '').lower()
            text_blob = f"{row.get('event', '')} {row.get('text', '')}".lower()
            phrase_matches = _phrase_matches(event_title_lower, phrase_topics) or _phrase_matches(text_blob, phrase_topics)
            title_topic_matches = _title_topic_matches(event_title_lower, topics)
            topic_matches = phrase_matches or title_topic_matches or _topic_matches_precise(text_blob, topics)
            format_matches = _format_matches(event_title_lower, format_hints) or _format_matches(text_blob, format_hints)
            event_match_bonus = _event_match_bonus(event_title_lower, event_hints)
            if topics and not phrase_matches and not title_topic_matches and not topic_matches and event_match_bonus <= 0 and not format_matches:
                continue
            row['retrieval_source'] = 'fts'
            row['tag_topic_matches'] = topic_matches
            row['tag_format_matches'] = format_matches
            row['retrieval_score'] = round(1.0 + len(phrase_matches) * 3.0 + len(title_topic_matches) * 1.5 + len(_topic_matches_precise(text_blob, topics)) * 0.2 + len(format_matches) * 1.8 + event_match_bonus + (0.5 if speaker else 0.0), 3)
            merge_scored(row)

    for row in runtime_rows + explicit_rows:
        event_title = row.get('event_title') or row.get('event_key', '')
        event_title_lower = (event_title or '').lower()
        text_blob = f"{event_title} {row.get('text', '')}".lower()
        phrase_matches = _phrase_matches(event_title_lower, phrase_topics) or _phrase_matches(text_blob, phrase_topics)
        title_topic_matches = _title_topic_matches(event_title_lower, topics)
        body_topic_matches = _topic_matches_precise(text_blob, topics)
        topic_matches = phrase_matches or title_topic_matches or body_topic_matches
        format_matches = _format_matches(event_title_lower, format_hints) or _format_matches(text_blob, format_hints)
        event_match_bonus = _event_match_bonus(event_title_lower, event_hints)
        if topics and not phrase_matches and not title_topic_matches and not body_topic_matches and event_match_bonus <= 0 and not format_matches:
            continue
        merge_scored({
            'id': row.get('transcript_id'),
            'text': row.get('text', ''),
            'speaker': row.get('speaker', ''),
            'event': event_title,
            'retrieval_source': 'runtime-db-fallback',
            'tag_topic_matches': topic_matches,
            'tag_format_matches': format_matches,
            'retrieval_score': round(0.75 + len(phrase_matches) * 3.0 + len(title_topic_matches) * 1.5 + len(body_topic_matches) * 0.2 + len(format_matches) * 1.8 + event_match_bonus + (0.4 if speaker else 0.0), 3),
        })

    scored_chunks = list(scored_by_id.values())
    scored_chunks.sort(key=lambda row: row.get('retrieval_score', 0), reverse=True)
    chunks.extend(scored_chunks[:limit])
    return chunks[:limit]


def _safe_search_transcript_tags_runtime(*, speaker: str = '', topic_tags: list[str] | None = None,
                                         format_tags: list[str] | None = None, limit: int = 10) -> list[dict]:
    try:
        return ensure_list(
            search_transcript_tags_runtime(
                speaker=speaker,
                topic_tags=topic_tags,
                format_tags=format_tags,
                limit=limit,
            )
        )
    except Exception as exc:
        log.debug('search_transcript_tags_runtime failed: %s', exc)
        return []


def _search_runtime_rows(*, query: str = '', speaker: str = '', title_query: str = '', limit: int = 10) -> list[dict]:
    try:
        if title_query:
            return ensure_list(
                search_transcripts_runtime(
                    speaker=speaker,
                    title_query=title_query,
                    limit=limit,
                )
            )
        return ensure_list(search_transcripts_runtime(query=query, speaker=speaker, limit=limit))
    except TypeError:
        fallback_query = title_query or query
        try:
            return ensure_list(search_transcripts_runtime(query=fallback_query, speaker=speaker, limit=limit))
        except Exception as exc:
            log.debug('search_transcripts_runtime fallback failed: %s', exc)
            return []
    except Exception as exc:
        log.debug('search_transcripts_runtime failed: %s', exc)
        return []


def _phrase_topics(query: str) -> list[str]:
    query = (query or '').lower()
    matches = []
    for phrase in PHRASE_TOPICS:
        if phrase in query:
            matches.append(phrase)
    return matches


def _phrase_matches(text_blob: str, phrase_topics: list[str]) -> list[str]:
    return [phrase for phrase in phrase_topics if phrase in (text_blob or '')]


def _topic_matches_precise(text_blob: str, topics: list[str]) -> list[str]:
    matches = []
    for topic in topics:
        candidates = TOPIC_QUERY_EXPANSIONS.get(topic, [topic])
        for candidate in candidates:
            if f' {candidate} ' in f' {text_blob} ':
                matches.append(topic)
                break
    return matches


def _expanded_queries(entities: dict) -> list[str]:
    speakers = entities.get('speakers', []) or []
    topics = [topic.lower() for topic in (entities.get('topics', []) or [])]
    event_types = entities.get('event_types', []) or []
    queries = []
    speaker = speakers[0] if speakers else ''
    for topic in topics[:3]:
        expansions = TOPIC_QUERY_EXPANSIONS.get(topic, [topic])
        for expanded in expansions:
            parts = [speaker, expanded]
            if event_types:
                parts.append(event_types[0])
            candidate = ' '.join(part for part in parts if part).strip()
            if candidate and candidate not in queries:
                queries.append(candidate)
    return queries[:8]


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
        'roundtable': ['roundtable'],
        'meeting': ['meeting'],
        'announcement': ['announcement'],
    }
    for needle, tags in mapping.items():
        if needle in query:
            for tag in tags:
                if tag not in hints:
                    hints.append(tag)
    return hints


def _event_hints(query: str) -> list[str]:
    query = (query or '').lower()
    hints = []
    for needle in ['roundtable', 'ratepayer', 'tips', 'tax', 'economy', 'energy', 'iran', 'no tax on tips']:
        if needle in query and needle not in hints:
            hints.append(needle)
    return hints


def _event_match_bonus(event_title_lower: str, event_hints: list[str]) -> float:
    if not event_title_lower or not event_hints:
        return 0.0
    bonus = 0.0
    for hint in event_hints:
        if hint in event_title_lower:
            if hint == 'roundtable':
                bonus += 1.2
            elif hint == 'no tax on tips':
                bonus += 2.0
            else:
                bonus += 0.5
    return bonus


def _title_topic_matches(event_title_lower: str, topics: list[str]) -> list[str]:
    matches = []
    for topic in topics:
        candidates = TOPIC_QUERY_EXPANSIONS.get(topic, [topic])
        if any(candidate in event_title_lower for candidate in candidates):
            matches.append(topic)
    return matches


def _build_effective_query(query: str, entities: dict) -> str:
    speakers = entities.get('speakers', []) or []
    topics = entities.get('topics', []) or []
    event_types = entities.get('event_types', []) or []
    parts = []
    if speakers:
        parts.append(speakers[0])
    parts.extend(event_types[:2])
    parts.extend(topics[:4])
    effective = ' '.join(part for part in parts if part).strip()
    if effective and len(effective.split()) >= 3:
        return effective
    return query


def _candidate_view(chunk: dict, speaker: str, format_hints: list[str], topics: list[str]) -> dict:
    event_title = chunk.get('event') or chunk.get('event_title') or ''
    text = chunk.get('text') or chunk.get('content') or ''
    text_blob = f'{event_title} {text}'.lower()
    speaker_value = (chunk.get('speaker') or '').strip()
    topic_matches = chunk.get('tag_topic_matches') or _topic_matches_precise(text_blob, topics)
    format_matches = chunk.get('tag_format_matches') or _format_matches(event_title.lower(), format_hints) or _format_matches(text_blob, format_hints)
    speaker_match = bool(speaker and speaker_value and speaker.lower() in speaker_value.lower())
    format_match = bool(format_hints and any(fmt in format_matches for fmt in format_hints))
    topic_match = bool(topic_matches)
    match_reasons = []
    if speaker_match:
        match_reasons.append('same-speaker')
    if format_match:
        match_reasons.append('same-format')
    if topic_match:
        match_reasons.append('same-topic')
    stitched_text = _stitched_candidate_text(chunk)
    quote = _build_candidate_quote(stitched_text or text, event_title, topic_matches, format_matches)
    return {
        'transcript_id': chunk.get('id'),
        'event_title': event_title,
        'speaker': speaker_value,
        'speaker_match': speaker_match,
        'format_match': format_match,
        'topic_match': topic_match,
        'topic_matches': topic_matches,
        'format_matches': format_matches,
        'relevance_score': chunk.get('retrieval_score', 0),
        'match_reasons': match_reasons,
        'quote': quote,
        'source': chunk.get('retrieval_source', ''),
        'chunk_kind': ((chunk.get('metadata') or {}).get('chunk_kind') if isinstance(chunk.get('metadata'), dict) else '') or chunk.get('chunk_kind', ''),
    }


def _segment_content_score(text: str, topic_matches: list[str], format_matches: list[str]) -> float:
    text = (text or '').lower()
    score = 0.0
    if not text:
        return score
    fluff = ['thank you', 'please', 'everybody', 'good afternoon', 'great to be here']
    if any(term in text for term in fluff):
        score -= 0.8

    event_family_terms = ['tax', 'tips', 'worker', 'workers', 'wages', 'service', 'restaurant', 'delivery', 'hospitality', 'ratepayer']
    broad_terms = ['inflation', 'economy', 'prices', 'consumer']
    offpath_terms = ['basketball', 'drug', 'military', 'war', 'nato', 'iran']

    topic_hit = False
    for topic in topic_matches or []:
        if str(topic).lower() in text:
            score += 2.2
            topic_hit = True
    for fmt in format_matches or []:
        normalized = str(fmt).replace('-', ' ').lower()
        if normalized in text:
            score += 0.4

    event_hits = sum(1 for term in event_family_terms if term in text)
    broad_hits = sum(1 for term in broad_terms if term in text)
    offpath_hits = sum(1 for term in offpath_terms if term in text)

    score += event_hits * 0.9
    score += broad_hits * 0.25
    score -= offpath_hits * 0.7

    if event_hits == 0 and not topic_hit:
        score -= 1.4
    return score


def _stitched_candidate_text(chunk: dict, radius: int = 1) -> str:
    transcript_id = chunk.get('transcript_id') or chunk.get('id')
    segment_index = chunk.get('segment_index')
    if transcript_id is None:
        return chunk.get('text') or chunk.get('content') or ''

    topic_matches = chunk.get('tag_topic_matches') or []
    format_matches = chunk.get('tag_format_matches') or []
    try:
        all_rows = get_transcript_segments(int(transcript_id))
    except Exception as exc:
        log.debug('get_transcript_segments failed for %r: %s', transcript_id, exc)
        all_rows = []
    if not all_rows:
        return chunk.get('text') or chunk.get('content') or ''

    scored = []
    for row in all_rows:
        text = ' '.join((row.get('text') or '').split())
        score = _segment_content_score(text, topic_matches, format_matches)
        if segment_index is not None and int(row.get('segment_index', -1)) == int(segment_index):
            score += 0.4
        scored.append((row, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    pivot_row = scored[0][0] if scored else None
    if not pivot_row:
        return chunk.get('text') or chunk.get('content') or ''
    pivot_index = int(pivot_row.get('segment_index') or segment_index or 0)
    try:
        rows = get_transcript_segment_window(int(transcript_id), pivot_index, radius=radius)
    except Exception as exc:
        log.debug('get_transcript_segment_window failed for %r/%r: %s', transcript_id, pivot_index, exc)
        rows = []
    if not rows:
        rows = [pivot_row]
    parts = []
    for row in rows:
        text = ' '.join((row.get('text') or '').split())
        if text:
            parts.append(text)
    return ' '.join(parts).strip()


def _build_candidate_quote(text: str, event_title: str, topic_matches: list[str], format_matches: list[str], max_chars: int = 420) -> str:
    text = ' '.join((text or '').split())
    if not text:
        return ''
    sentences = [s.strip() for s in text.replace('?', '.').replace('!', '.').split('.') if s.strip()]
    if not sentences:
        return text[:max_chars]

    needles = [str(x).lower() for x in (topic_matches or []) + (format_matches or []) if str(x).strip()]
    pivot = None
    for i, sentence in enumerate(sentences):
        blob = f"{event_title} {sentence}".lower()
        if any(needle in blob for needle in needles):
            pivot = i
            break
    if pivot is None:
        pivot = 0

    start = max(0, pivot - 1)
    end = min(len(sentences), pivot + 2)
    window = '. '.join(sentences[start:end]).strip()
    if window and not window.endswith('.'):
        window += '.'
    if len(window) <= max_chars:
        return window
    return window[:max_chars].rsplit(' ', 1)[0] + '…'


def _format_matches(text_blob: str, format_hints: list[str]) -> list[str]:
    if not format_hints:
        return []
    aliases = {
        'press-conference': ['press conference', 'briefing', 'presser'],
        'q-and-a': ['q&a', 'question', 'questions', 'asked'],
        'prepared-remarks': ['prepared remarks', 'remarks', 'speech'],
        'speech': ['speech', 'address', 'remarks'],
        'interview': ['interview'],
        'rally': ['rally'],
        'roundtable': ['roundtable'],
        'meeting': ['meeting'],
        'announcement': ['announcement'],
    }
    matches = []
    for fmt in format_hints:
        needles = aliases.get(fmt, [fmt.replace('-', ' ')])
        if any(needle in text_blob for needle in needles):
            matches.append(fmt)
    return matches


def _support_strength(same_speaker_hits: int, same_format_hits: int, same_topic_hits: int) -> str:
    score = same_speaker_hits + same_format_hits + same_topic_hits
    if score >= 6:
        return 'high'
    if score >= 3:
        return 'medium'
    return 'weak'


def _tendency_summary(candidates: list[dict], speaker: str) -> str:
    if not candidates:
        return 'No transcript-backed historical context found.'
    same_format = sum(1 for item in candidates if item.get('format_match'))
    same_topic = sum(1 for item in candidates if item.get('topic_match'))
    if same_format and same_topic:
        return f'Found same-speaker analogs with meaningful format and topic overlap for {speaker or "this speaker"}.'
    if same_format:
        return f'Found same-speaker format analogs for {speaker or "this speaker"}, but topic overlap is still thin.'
    if same_topic:
        return f'Found same-speaker topic analogs for {speaker or "this speaker"}, but format overlap is still thin.'
    return f'Found same-speaker historical transcripts for {speaker or "this speaker"}, but analog quality is weak.'


def _retrieval_summary(candidates: list[dict], speaker: str) -> str:
    if not candidates:
        return 'No transcript-backed analogs found.'
    same_format = sum(1 for item in candidates if item.get('format_match'))
    same_topic = sum(1 for item in candidates if item.get('topic_match'))
    if same_format and same_topic:
        return 'Found same-speaker analogs with both format and topic overlap.'
    if same_format:
        return 'Found same-speaker format analogs, but direct topic overlap is limited.'
    if same_topic:
        return 'Found same-speaker topic analogs, but format overlap is limited.'
    return 'Found same-speaker transcripts, but they are only weak analogs for this event.'


def _empty_bundle(query: str, speaker: str = '', reason: str = '') -> dict:
    risks = ['no-transcript-hits']
    if reason:
        risks.append(reason)
    return {
        'query': query,
        'speaker': speaker,
        'status': 'empty',
        'chunks': [],
        'summary': '',
        'top_speakers': [],
        'top_events': [],
        'context_risks': risks,
        'query_target': {'speaker': speaker, 'event_format': [], 'topic_candidates': []},
        'speaker_context': {'speaker': speaker, 'same_speaker_hits': 0, 'support_strength': 'weak', 'tendency_summary': 'No transcript-backed historical context found.'},
        'format_analogs': [],
        'topic_analogs': [],
        'counterevidence': [],
        'top_candidates': [],
        'retrieval_summary': 'No transcript-backed analogs found.',
    }
