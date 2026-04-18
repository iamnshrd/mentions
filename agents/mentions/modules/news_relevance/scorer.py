from __future__ import annotations

import re

from agents.mentions.module_contracts import ensure_dict, ensure_list


HARD_REJECT_TERMS = {
    'anthropic', 'gen z', 'religious resurgence', 'subscription', 'ai model', 'startup'
}

SOFT_CONTEXT_TERMS = {
    'trump administration', 'white house', 'press briefing', 'brief on', 'reporters', 'remarks'
}

EVENT_NEGATIVE_TERMS = {
    'impeachment', 'misdemeanors', 'efficiency gains', 'haitians', 'pope', 'anthropic'
}

GENERIC_NEWS_TERMS = {
    'campaign', 'election', 'poll', 'approval', 'administration', 'white house officials'
}

LOW_QUALITY_SOURCE_TERMS = {
    'coinbase', 'polymarket', 'kalshi', 'odds', 'betting', 'prediction'
}


def score_news_relevance(news: list[dict], speaker_hint: str = '', topic_hints: list[str] | None = None,
                         event_context: dict | None = None, event_hints: list[str] | None = None,
                         event_anchors: list[str] | None = None,
                         event_phrases: list[str] | None = None,
                         limit: int = 5) -> dict:
    topic_hints = [hint.lower() for hint in (topic_hints or []) if hint]
    event_hints = [hint.lower() for hint in (event_hints or []) if hint]
    event_anchors = [anchor.lower() for anchor in (event_anchors or []) if anchor]
    event_phrases = [phrase.lower() for phrase in (event_phrases or []) if phrase]
    event_context = ensure_dict(event_context)
    scored = []
    for item in ensure_list(news):
        if not isinstance(item, dict):
            continue
        headline = (item.get('headline') or '').strip()
        summary = (item.get('summary') or '').strip()
        text_blob = f'{headline} {summary}'.lower()
        speaker_score = _speaker_score(text_blob, speaker_hint)
        topic_matches = [topic for topic in topic_hints if _contains_term(text_blob, topic)]
        topic_score = min(1.0, 0.35 * len(topic_matches))
        event_hint_matches = [hint for hint in event_hints if _contains_event_hint(text_blob, hint)]
        event_anchor_matches = [anchor for anchor in event_anchors if _contains_event_anchor(text_blob, anchor)]
        event_phrase_matches = [phrase for phrase in event_phrases if _contains_event_anchor(text_blob, phrase)]
        event_score = _event_score(text_blob, event_context, event_hint_matches, event_anchor_matches, event_phrase_matches)
        freshness_score = 0.5 if item.get('published_at') else 0.2
        source_quality = _source_quality(item)
        noise_flags = []
        if any(term in text_blob for term in HARD_REJECT_TERMS):
            noise_flags.append('hard-topic-mismatch')
        if _is_low_quality_source(item):
            noise_flags.append('low-quality-source')
        if any(term in text_blob for term in EVENT_NEGATIVE_TERMS):
            noise_flags.append('event-mismatch')
        if speaker_hint and speaker_score == 0:
            noise_flags.append('speaker-not-mentioned')
        if topic_hints and not topic_matches:
            noise_flags.append('topic-not-mentioned')
        if event_hints and not event_hint_matches and not event_phrase_matches:
            noise_flags.append('event-frame-not-mentioned')
        if event_anchors and not event_anchor_matches:
            noise_flags.append('strict-event-anchor-missing')
        if _is_generic_context_only(text_blob, topic_matches, event_hint_matches, event_anchor_matches, event_phrase_matches):
            noise_flags.append('generic-context-only')
        if any(term in text_blob for term in SOFT_CONTEXT_TERMS):
            event_score = min(1.0, event_score + 0.15)
        coupling_score = _speaker_event_coupling_score(text_blob, speaker_score, event_hint_matches, event_anchor_matches, event_phrase_matches)
        final_score = round(speaker_score + topic_score + event_score + freshness_score + source_quality + coupling_score, 3)
        if event_anchors and not event_anchor_matches and speaker_score < 1.0:
            noise_flags.append('generic-institutional-match')
        decision = 'keep' if final_score >= 2.45 and 'topic-not-mentioned' not in noise_flags and 'hard-topic-mismatch' not in noise_flags and 'event-mismatch' not in noise_flags and 'generic-institutional-match' not in noise_flags and 'generic-context-only' not in noise_flags and 'low-quality-source' not in noise_flags and ('speaker-not-mentioned' not in noise_flags or speaker_score >= 0.6) and ('event-frame-not-mentioned' not in noise_flags or coupling_score >= 0.2 or bool(event_phrase_matches)) and ('strict-event-anchor-missing' not in noise_flags or coupling_score >= 0.35 or bool(event_phrase_matches)) else 'reject'
        scored.append({
            **item,
            'speaker_relevance': speaker_score,
            'topic_relevance': topic_score,
            'event_relevance': event_score,
            'source_quality': source_quality,
            'freshness_score': freshness_score,
            'topic_matches': topic_matches,
            'noise_flags': noise_flags,
            'event_hint_matches': event_hint_matches,
            'event_anchor_matches': event_anchor_matches,
            'event_phrase_matches': event_phrase_matches,
            'coupling_score': coupling_score,
            'final_relevance_score': final_score,
            'decision': decision,
        })
    scored.sort(key=lambda item: item.get('final_relevance_score', 0), reverse=True)
    kept = [item for item in scored if item.get('decision') == 'keep'][:limit]
    rejected = [item for item in scored if item.get('decision') != 'keep'][:limit]
    return {
        'ranked_items': scored[:limit],
        'kept_items': kept,
        'rejected_items': rejected,
    }


def _is_low_quality_source(item: dict) -> bool:
    source = (item.get('source') or '').lower()
    url = (item.get('url') or '').lower()
    blob = f'{source} {url}'
    return any(term in blob for term in LOW_QUALITY_SOURCE_TERMS)


def _source_quality(item: dict) -> float:
    source = (item.get('source') or '').strip()
    if not source:
        return 0.3
    if _is_low_quality_source(item):
        return 0.1
    high_signal = ['pbs', 'ap', 'associated press', 'reuters', 'politico', 'the hill', 'guardian', 'bbc', 'npr', 'c-span', 'washington post']
    if any(name in source.lower() for name in high_signal):
        return 0.9
    return 0.7


def _speaker_score(text_blob: str, speaker_hint: str) -> float:
    if not speaker_hint:
        return 0.0
    normalized = speaker_hint.lower().strip()
    if normalized in text_blob:
        return 1.0
    parts = [part for part in normalized.split() if part]
    if not parts:
        return 0.0
    last_name = parts[-1]
    if last_name and _contains_term(text_blob, last_name):
        return 0.6
    if len(parts) >= 2 and all(_contains_term(text_blob, part) for part in parts[-2:]):
        return 0.75
    return 0.0


def _event_score(text_blob: str, event_context: dict, event_hint_matches: list[str], event_anchor_matches: list[str], event_phrase_matches: list[str]) -> float:
    score = 0.0
    exact_topic_hits = 0
    for token in ensure_list(event_context.get('likely_topics', []))[:4]:
        token = (token or '').lower()
        if token and _contains_term(text_blob, token):
            score += 0.25
            exact_topic_hits += 1
    fmt = (event_context.get('format') or '').replace('_', '-')
    if fmt and fmt in text_blob:
        score += 0.2
    venue = (event_context.get('venue') or '').lower()
    if venue and any(part for part in venue.split(',')[:1] if part and part in text_blob):
        score += 0.2
    qa = (event_context.get('qa_likelihood') or '').lower()
    if qa in {'high', 'medium'} and any(term in text_blob for term in ['briefing', 'remarks', 'reporters', 'asked', 'questioned']):
        score += 0.15
    if exact_topic_hits == 0 and any(term in text_blob for term in ['iran', 'nuclear', 'tehran']):
        score += 0.05
    if event_hint_matches:
        score += min(0.2, 0.1 * len(event_hint_matches))
    if event_anchor_matches:
        score += min(0.35, 0.2 * len(event_anchor_matches))
    if event_phrase_matches:
        score += min(0.45, 0.25 * len(event_phrase_matches))
    return min(score, 1.0)


def _is_generic_context_only(text_blob: str, topic_matches: list[str], event_hint_matches: list[str], event_anchor_matches: list[str], event_phrase_matches: list[str]) -> bool:
    if topic_matches or event_hint_matches or event_anchor_matches or event_phrase_matches:
        return False
    return any(term in text_blob for term in GENERIC_NEWS_TERMS)


def _speaker_event_coupling_score(text_blob: str, speaker_score: float, event_hint_matches: list[str], event_anchor_matches: list[str], event_phrase_matches: list[str]) -> float:
    score = 0.0
    if speaker_score >= 0.6 and event_phrase_matches:
        score += 0.45
    elif speaker_score >= 0.6 and event_anchor_matches:
        score += 0.4
    elif speaker_score >= 0.6 and event_hint_matches:
        score += 0.2
    elif speaker_score >= 0.6:
        score += 0.05
    elif event_anchor_matches:
        score += 0.05
    if any(term in text_blob for term in ['speech', 'remarks', 'briefing', 'press conference', 'correspondents dinner']):
        score += 0.1
    return min(score, 0.5)


def _contains_term(text: str, term: str) -> bool:
    text = f' {text.lower()} '
    term = f' {(term or '').lower()} '
    return term in text


def _contains_event_hint(text: str, hint: str) -> bool:
    hint = (hint or '').strip().lower()
    if not hint:
        return False
    if ' ' in hint:
        pattern = r'\b' + r'\s+'.join(re.escape(part) for part in hint.split()) + r'\b'
        return re.search(pattern, text.lower()) is not None
    if hint in {'mention', 'remarks', 'speech', 'briefing'}:
        aliases = {
            'mention': ['mention', 'mentions', 'mentioned'],
            'remarks': ['remarks', 'remark'],
            'speech': ['speech', 'address'],
            'briefing': ['briefing', 'brief'],
        }
        pattern = r'\b(?:' + '|'.join(re.escape(value) for value in aliases.get(hint, [hint])) + r')\b'
        return re.search(pattern, text.lower()) is not None
    return re.search(r'\b' + re.escape(hint) + r'\b', text.lower()) is not None


def _contains_event_anchor(text: str, anchor: str) -> bool:
    anchor = (anchor or '').strip().lower()
    if not anchor:
        return False
    pattern = r'\b' + r'\s+'.join(re.escape(part) for part in anchor.split()) + r'\b'
    return re.search(pattern, text.lower()) is not None
