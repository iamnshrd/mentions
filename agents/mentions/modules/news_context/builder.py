from __future__ import annotations

import logging
import re

from agents.mentions.analysis.event_context import analyze_event_context
from agents.mentions.fetch.news import fetch_news_with_status
from agents.mentions.module_contracts import ensure_dict, ensure_list, normalize_status
from agents.mentions.modules.market_resolution.extraction import extract_market_entities
from agents.mentions.providers.rss_provider import fetch_rss_news_bundle
from agents.mentions.fetch.google_news_rss import fetch_google_news_rss, GoogleNewsRssUnavailable
from agents.mentions.runtime.trace import new_run_id, trace_log

log = logging.getLogger('mentions')


def _merge_live_news_sources(*, news: list[dict], status: str, google_news_items: list[dict], rss_items: list[dict]) -> tuple[list[dict], str]:
    news = ensure_list(news)
    status = status or 'unavailable'
    google_news_items = ensure_list(google_news_items)
    rss_items = ensure_list(rss_items)
    if google_news_items:
        news = _merge_news_items(news, google_news_items)
        if status == 'unavailable':
            status = 'live'
    elif rss_items:
        news = _merge_news_items(news, rss_items)
        if status == 'unavailable':
            status = 'partial'
    return news, normalize_status(status)


def build_news_context_bundle(query: str, category: str = 'general',
                              market_data: dict | None = None,
                              speaker_info: dict | None = None,
                              limit: int = 5,
                              require_live: bool = False) -> dict:
    run_id = new_run_id()
    market_data = ensure_dict(market_data or {})
    speaker_info = ensure_dict(speaker_info or {})
    trace_log('news.builder.start', run_id=run_id, query=query, category=category, limit=limit, require_live=require_live)

    entities = extract_market_entities(query)
    topic_hints = _topic_hints(query, market_data=market_data, entities=entities)
    speaker_hint = speaker_info.get('speaker') or ((entities.get('speakers', []) or [''])[0])
    effective_query = _build_effective_query(query, market_data=market_data, speaker_info=speaker_info)
    event_hints = _event_hints(query, market_data=market_data, entities=entities)
    event_anchors = _event_anchors(query, market_data=market_data, entities=entities)
    event_phrases = _event_phrases(query, market_data=market_data, entities=entities)
    news, status = fetch_news_with_status(
        effective_query,
        category=category,
        limit=limit,
        require_live=require_live,
        topic_hints=topic_hints,
        speaker_hint=speaker_hint,
    )
    rss_bundle = fetch_rss_news_bundle(category=category, limit_per_feed=max(2, limit), max_feeds=6)
    rss_items = ensure_list(rss_bundle.get('raw_items', []))
    google_news_bundle = _fetch_google_news_bundle(query, market_data=market_data, speaker_hint=speaker_hint, event_phrases=event_phrases, limit=limit)
    google_news_items = ensure_list(google_news_bundle.get('raw_items', []))
    news, status = _merge_live_news_sources(
        news=news,
        status=status,
        google_news_items=google_news_items,
        rss_items=rss_items,
    )
    trace_log('news.builder.sources', run_id=run_id, google_news_count=len(google_news_items), rss_count=len(rss_items), merged_count=len(news), status=status)

    event_context = ensure_dict(analyze_event_context(market_data, news, speaker_info))
    relevance = {}
    try:
        from agents.mentions.modules.news_relevance import score_news_relevance
        relevance = score_news_relevance(news, speaker_hint=speaker_hint, topic_hints=topic_hints, event_context=event_context, event_hints=event_hints, event_anchors=event_anchors, event_phrases=event_phrases, limit=limit)
        kept_items = ensure_list(relevance.get('kept_items', []))
        if kept_items:
            news = kept_items
            if status == 'unavailable':
                status = 'live'
        else:
            news = []
            if rss_items:
                status = 'partial'
            else:
                status = 'unavailable'
    except Exception as exc:
        log.debug('score_news_relevance failed: %s', exc)
        relevance = {}
    typed_news = _build_typed_news(query=query, event_title=market_data.get('event_title') or market_data.get('title') or query, news=news, run_id=run_id)
    direct_paths, weak_paths, late_paths = _build_path_map(query, event_context, news)
    headlines = [item.get('headline', '') for item in news[:3] if isinstance(item, dict) and item.get('headline')]
    freshness = 'fresh' if status in {'live', 'partial'} else 'stale' if status == 'cache' else 'missing'
    sufficiency = _compute_sufficiency(status=status, news=news, event_context=event_context)

    trace_log('news.builder.finish', run_id=run_id, status=status, core_news=len(typed_news.get('core_news', [])), expansion_news=len(typed_news.get('expansion_news', [])), ambient_news=len(typed_news.get('ambient_news', [])))
    return {
        'query': query,
        'effective_query': effective_query,
        'category': category,
        'topic_hints': topic_hints,
        'speaker_hint': speaker_hint,
        'event_hints': event_hints,
        'event_anchors': event_anchors,
        'event_phrases': event_phrases,
        'status': status,
        'freshness': freshness,
        'sufficiency': sufficiency,
        'news': news,
        'rss_provider': rss_bundle,
        'google_news_provider': google_news_bundle,
        'summary': '; '.join(headlines),
        'event_context': event_context,
        'news_relevance': relevance,
        'typed_news': typed_news,
        'core_news': typed_news.get('core_news', []),
        'expansion_news': typed_news.get('expansion_news', []),
        'ambient_news': typed_news.get('ambient_news', []),
        'paths': {
            'direct': direct_paths,
            'weak': weak_paths,
            'late': late_paths,
        },
        'run_id': run_id,
    }


def _fetch_google_news_bundle(query: str,
                              market_data: dict | None = None,
                              speaker_hint: str = '',
                              event_phrases: list[str] | None = None,
                              limit: int = 5) -> dict:
    queries = _build_google_news_queries(query, market_data=market_data, speaker_hint=speaker_hint, event_phrases=event_phrases)
    raw_items = []
    errors = []
    for item_query in queries:
        try:
            bundle = fetch_google_news_rss(item_query, limit=limit)
            raw_items.extend(ensure_list(bundle.get('raw_items', [])))
        except GoogleNewsRssUnavailable as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(str(exc))
    return {
        'status': 'ok' if raw_items else 'unavailable',
        'queries': queries,
        'raw_items': _merge_news_items([], raw_items),
        'errors': errors,
    }


def _clean_event_title_for_news_search(text: str) -> str:
    cleaned = (text or '').strip()
    cleaned = re.sub(r'^(what will|what would|will|would)\s+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\?+$', '', cleaned).strip()
    cleaned = cleaned.replace('Donald Trump say during', 'Donald Trump during')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _build_google_news_queries(query: str,
                               market_data: dict | None = None,
                               speaker_hint: str = '',
                               event_phrases: list[str] | None = None) -> list[str]:
    queries = []
    market_data = ensure_dict(market_data or {})
    event_title = _clean_event_title_for_news_search(market_data.get('event_title') or market_data.get('title') or '')
    event_phrases = [str(item).strip() for item in ensure_list(event_phrases or []) if str(item).strip()]

    if speaker_hint and event_phrases:
        for phrase in event_phrases[:3]:
            queries.append(f'{speaker_hint} "{phrase}"')
    if speaker_hint and event_title:
        queries.append(f'{speaker_hint} "{event_title}"')
    if event_title:
        queries.append(f'"{event_title}"')
    if query:
        queries.append(query)

    seen = set()
    deduped = []
    for item in queries:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item.strip())
    return deduped[:5]


def _merge_news_items(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for item in ensure_list(primary) + ensure_list(secondary):
        if not isinstance(item, dict):
            continue
        key = (item.get('headline') or item.get('title') or '', item.get('url') or '')
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _typed_news_rows(*, query: str, event_title: str, news: list[dict], run_id: str, families: list[str]) -> tuple[dict, list[dict]]:
    from agents.mentions.modules.transcript_semantic_retrieval.client import news_score

    family_results = {}
    typed_rows = []
    for family in families:
        result = news_score(query=query, family=family, event_title=event_title, articles=news, top_k=3, run_id=run_id)
        rows = ensure_list(result.get('results', [])) if isinstance(result, dict) else []
        family_results[family] = rows
        typed_rows.extend(rows)
    return family_results, typed_rows


def _typed_news_buckets(typed_rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    core_news = []
    expansion_news = []
    ambient_news = []
    seen = set()
    for row in typed_rows:
        key = (row.get('headline', ''), row.get('family', ''))
        if key in seen:
            continue
        seen.add(key)
        evidence_type = row.get('evidence_type') or ''
        if evidence_type == 'event_core':
            core_news.append(row)
        elif evidence_type == 'topic_expansion':
            expansion_news.append(row)
        elif evidence_type == 'ambient_regime':
            ambient_news.append(row)
    return core_news[:5], expansion_news[:5], ambient_news[:5]


def _typed_news_contract(*, family_results: dict, core_news: list[dict],
                         expansion_news: list[dict], ambient_news: list[dict]) -> dict:
    return {
        'core_news': core_news,
        'expansion_news': expansion_news,
        'ambient_news': ambient_news,
        'families': family_results,
        'has_event_core': bool(core_news),
        'has_topic_expansion': bool(expansion_news),
        'has_ambient_regime': bool(ambient_news),
        'coverage_state': 'event-led' if core_news else 'topic-led' if expansion_news else 'ambient-only' if ambient_news else 'empty',
    }


def _build_typed_news(query: str, event_title: str, news: list[dict], run_id: str = '') -> dict:
    try:
        from agents.mentions.modules.transcript_semantic_retrieval.client import news_score
    except Exception as exc:
        log.debug('news_score import failed: %s', exc)
        return {'core_news': [], 'expansion_news': [], 'ambient_news': [], 'families': {}}

    families = ['direct_event_coverage', 'local_event_logistics', 'broader_economy_regime', 'opposition_media_reaction']
    family_results, typed_rows = _typed_news_rows(
        query=query,
        event_title=event_title,
        news=news,
        run_id=run_id,
        families=families,
    )

    core_news, expansion_news, ambient_news = _typed_news_buckets(typed_rows)

    return _typed_news_contract(
        family_results=family_results,
        core_news=core_news,
        expansion_news=expansion_news,
        ambient_news=ambient_news,
    )


def _build_path_map(query: str, event_context: dict, news: list[dict]) -> tuple[list[str], list[str], list[str]]:
    direct = []
    weak = []
    late = []
    likely_topics = [str(item).lower() for item in ensure_list(event_context.get('likely_topics', []))]
    for item in news:
        headline = (item.get('headline') or item.get('title') or '').lower()
        if any(topic.lower() in headline for topic in likely_topics if topic):
            direct.append(item.get('headline') or item.get('title') or '')
        elif any(term in headline for term in ['tariff', 'inflation', 'social security', 'economy']):
            late.append(item.get('headline') or item.get('title') or '')
        else:
            weak.append(item.get('headline') or item.get('title') or '')
    return direct[:3], weak[:3], late[:3]


def _compute_sufficiency(status: str, news: list[dict], event_context: dict) -> str:
    if status in {'live', 'partial'} and news:
        if ensure_list(event_context.get('likely_topics', [])):
            return 'strong'
        return 'moderate'
    if news:
        return 'limited'
    return 'weak'


def _build_effective_query(query: str, market_data: dict | None = None, speaker_info: dict | None = None) -> str:
    speaker_info = ensure_dict(speaker_info or {})
    market_data = ensure_dict(market_data or {})
    speaker = speaker_info.get('speaker') or ''
    title = market_data.get('event_title') or market_data.get('title') or ''
    phrase = _clean_event_title_for_news_search(title)
    if speaker and phrase:
        return f'{speaker} {phrase}'.strip()
    if phrase:
        return phrase
    return query


def _topic_hints(query: str, market_data: dict | None = None, entities: dict | None = None) -> list[str]:
    market_data = ensure_dict(market_data or {})
    entities = ensure_dict(entities or {})
    hints = []
    event_title = market_data.get('event_title') or market_data.get('title') or ''
    if event_title:
        hints.append(event_title)
    for item in ensure_list(entities.get('topics', [])):
        if item and item not in hints:
            hints.append(item)
    return hints[:8]


def _event_hints(query: str, market_data: dict | None = None, entities: dict | None = None) -> list[str]:
    market_data = ensure_dict(market_data or {})
    entities = ensure_dict(entities or {})
    hints = []
    for key in ('event_title', 'title', 'subtitle'):
        value = market_data.get(key)
        if value:
            hints.append(str(value))
    for item in ensure_list(entities.get('topics', [])):
        if item and item not in hints:
            hints.append(item)
    return hints[:8]


def _event_anchors(query: str, market_data: dict | None = None, entities: dict | None = None) -> list[str]:
    anchors = []
    for item in _event_hints(query, market_data=market_data, entities=entities):
        parts = re.split(r'[^A-Za-z0-9]+', str(item))
        for part in parts:
            part = part.strip()
            if len(part) >= 4 and part.lower() not in {anchor.lower() for anchor in anchors}:
                anchors.append(part)
    return anchors[:10]


def _event_phrases(query: str, market_data: dict | None = None, entities: dict | None = None) -> list[str]:
    market_data = ensure_dict(market_data or {})
    phrases = []
    title = market_data.get('event_title') or market_data.get('title') or ''
    cleaned = _clean_event_title_for_news_search(title)
    if cleaned:
        phrases.append(cleaned)
    if 'no tax on tips' in cleaned.lower() or 'no tax on tips' in query.lower():
        phrases.extend(['no tax on tips', 'no tax on tip'])
    return phrases[:6]
