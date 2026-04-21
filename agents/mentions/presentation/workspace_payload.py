from __future__ import annotations

from agents.mentions.interfaces.capabilities.analysis.api import run_query, run_url
from agents.mentions.interfaces.capabilities.news_context.api import build_context
from agents.mentions.interfaces.capabilities.transcripts.api import search_transcripts
from agents.mentions.presentation.debug_view import build_debug_view
from mentions_domain.normalize import ensure_dict, ensure_list


def build_workspace_payload(query: str, *, user_id: str = 'default',
                            mode: str = 'query',
                            news_limit: int = 5,
                            transcript_limit: int = 5) -> dict:
    if mode == 'url':
        analysis_result = ensure_dict(run_url(query, user_id=user_id))
    else:
        analysis_result = ensure_dict(run_query(query, user_id=user_id))
    news_context = ensure_dict(build_context(query, limit=news_limit))
    transcript_hits = ensure_list(
        search_transcripts(query, limit=transcript_limit)
    )
    return compose_workspace_payload(
        query=query,
        analysis_result=analysis_result,
        news_context=news_context,
        transcript_hits=transcript_hits,
    )


def compose_workspace_payload(*, query: str, analysis_result: dict,
                              news_context: dict, transcript_hits: list[dict]) -> dict:
    analysis_result = ensure_dict(analysis_result)
    news_context = ensure_dict(news_context)
    transcript_hits = ensure_list(transcript_hits)

    synthesis = ensure_dict(analysis_result.get('synthesis', {}))
    analysis_profiles = ensure_dict(synthesis.get('analysis_profiles', {}))
    analysis_card = (
        ensure_dict(analysis_profiles.get('analysis_card', {}))
        or _fallback_analysis_card(
            query=query,
            analysis_result=analysis_result,
            news_context=news_context,
            transcript_hits=transcript_hits,
        )
    )

    direct_event_news = [
        _normalize_news_item(item, 'direct')
        for item in ensure_list(news_context.get('direct_event_news', []))[:3]
    ]
    background_news = [
        _normalize_news_item(item, 'background')
        for item in ensure_list(news_context.get('background_news', []))[:3]
    ]
    transcript_trace = _extract_transcript_trace(synthesis, transcript_hits, query=query)
    ranking_debug = _extract_ranking_debug(news_context)
    context_risks = _dedupe_strings(
        ensure_list(news_context.get('context_risks', []))
        + ensure_list(
            ensure_dict(ensure_dict(synthesis.get('evidence_debug', {})).get('context_risks', {})).get('transcripts', [])
        )
    )
    debug_view = _extract_debug_view(
        synthesis=synthesis,
        news_context=news_context,
        transcript_trace=transcript_trace,
    )

    payload = {
        'query': query,
        'analysis_card': analysis_card,
        'direct_event_news': direct_event_news,
        'background_news': background_news,
        'transcript_trace': transcript_trace,
        'ranking_debug': ranking_debug,
        'context_risks': context_risks,
        'debug_view': debug_view,
    }
    payload['evidence_sources'] = _build_evidence_sources(payload)
    return payload


def _fallback_analysis_card(*, query: str, analysis_result: dict,
                            news_context: dict, transcript_hits: list[dict]) -> dict:
    direct_event_news = ensure_list(news_context.get('direct_event_news', []))
    background_news = ensure_list(news_context.get('background_news', []))
    news_summary = (news_context.get('news_summary') or '').strip()
    reason = (analysis_result.get('reason') or '').strip()
    response = (
        analysis_result.get('response')
        or analysis_result.get('response_raw')
        or ''
    ).strip()

    evidence = []
    if direct_event_news:
        lead = ensure_dict(direct_event_news[0])
        evidence.append(
            f"Есть прямой event source: {lead.get('headline', '')} ({lead.get('source', '')})."
        )
    if background_news:
        lead = ensure_dict(background_news[0])
        evidence.append(
            f"Есть фоновый контекст: {lead.get('headline', '')} ({lead.get('source', '')})."
        )
    if transcript_hits:
        lead = ensure_dict(transcript_hits[0])
        speaker = lead.get('speaker', '') or 'unknown speaker'
        event = lead.get('event', '') or query
        evidence.append(
            f"Есть transcript hit по событию {event} с участием {speaker}."
        )
    if news_summary:
        evidence.append(news_summary)
    if response:
        evidence.append(response)
    evidence = [item for item in evidence if item][:3]

    if response:
        thesis = response.split('\n', 1)[0].strip()
    elif direct_event_news or background_news or transcript_hits:
        thesis = 'Структурный market-linked analysis для этого запроса ещё не собран, но source context уже доступен.'
    else:
        thesis = 'Для этого запроса пока нет достаточного source context, чтобы собрать структурный analysis card.'

    uncertainty = reason or _render_context_risks(ensure_list(news_context.get('context_risks', [])))
    if not uncertainty:
        uncertainty = 'Текущий запрос пока не привязан к стабильному market-analysis маршруту.'

    if transcript_hits:
        next_check = 'Проверить transcript evidence и сопоставить его с direct event coverage.'
    elif direct_event_news:
        next_check = 'Добрать transcript-backed подтверждение по событию, чтобы усилить analysis card.'
    else:
        next_check = 'Сначала собрать direct event coverage или transcript evidence по событию.'

    return {
        'thesis': thesis,
        'evidence': evidence,
        'uncertainty': uncertainty,
        'risk': 'Без transcript-backed и event-specific подтверждения вывод может остаться слишком общим.',
        'next_check': next_check,
        'action': 'Использовать source inspection и context review до появления более сильного structured analysis.',
        'fair_value_view': 'Fair value view недоступен, пока запрос не привязан к market-analysis маршруту.',
    }


def _extract_transcript_trace(synthesis: dict, transcript_hits: list[dict], *, query: str) -> dict:
    evidence_debug = ensure_dict(synthesis.get('evidence_debug', {}))
    transcript_debug = ensure_dict(evidence_debug.get('transcript_trace', {}))
    lead_candidate = ensure_dict(transcript_debug.get('lead_candidate', {}))
    retrieval_hits = ensure_list(transcript_debug.get('retrieval_hits', []))
    top_candidates = ensure_list(transcript_debug.get('top_candidates', []))

    if not lead_candidate and transcript_hits:
        hit = ensure_dict(transcript_hits[0])
        lead_candidate = {
            'transcript_id': hit.get('document_id') or hit.get('transcript_id') or '',
            'segment_index': hit.get('chunk_index') or hit.get('segment_index') or 0,
            'source_ref': hit.get('source_ref') or hit.get('source_url') or hit.get('source_file') or '',
            'event_title': hit.get('event') or query,
            'event_date': hit.get('event_date') or '',
            'start_ts': hit.get('start_ts') or '',
            'end_ts': hit.get('end_ts') or '',
            'speaker': hit.get('speaker') or '',
        }

    normalized_hits = []
    if retrieval_hits:
        normalized_hits = [_normalize_transcript_hit(hit) for hit in retrieval_hits[:3]]
    else:
        normalized_hits = [_normalize_transcript_hit(hit) for hit in transcript_hits[:3]]

    excerpt = (
        transcript_debug.get('excerpt')
        or lead_candidate.get('excerpt')
        or ''
    )
    excerpt_speaker = lead_candidate.get('speaker') or ''
    if not excerpt and transcript_hits:
        hit = ensure_dict(transcript_hits[0])
        excerpt = (hit.get('text') or '').strip()
        excerpt_speaker = hit.get('speaker', '') or excerpt_speaker

    return {
        'lead_candidate': {
            'transcript_id': lead_candidate.get('transcript_id', ''),
            'segment_index': lead_candidate.get('segment_index', ''),
            'source_ref': lead_candidate.get('source_ref', ''),
            'event_title': lead_candidate.get('event_title') or lead_candidate.get('event') or query,
            'event_date': lead_candidate.get('event_date', ''),
            'start_ts': lead_candidate.get('start_ts', ''),
            'end_ts': lead_candidate.get('end_ts', ''),
            'speaker': excerpt_speaker or lead_candidate.get('speaker', ''),
        },
        'top_candidates': top_candidates[:3],
        'retrieval_hits': normalized_hits,
        'excerpt': excerpt,
        'excerpt_speaker': excerpt_speaker,
    }


def _normalize_transcript_hit(hit: dict) -> dict:
    hit = ensure_dict(hit)
    return {
        'chunk_id': hit.get('chunk_id') or hit.get('id') or '',
        'document_id': hit.get('document_id') or hit.get('transcript_id') or '',
        'chunk_index': hit.get('chunk_index') or hit.get('segment_index') or '',
        'source_file': hit.get('source_file') or hit.get('source_ref') or '',
        'speaker': hit.get('speaker') or '',
        'event': hit.get('event') or hit.get('event_title') or '',
        'text': hit.get('text') or '',
        'start_ts': hit.get('start_ts') or '',
        'end_ts': hit.get('end_ts') or '',
    }


def _extract_ranking_debug(news_context: dict) -> dict:
    ranking_debug = ensure_dict(news_context.get('ranking_debug', {}))
    return {
        'status': ranking_debug.get('status', ''),
        'freshness': ranking_debug.get('freshness', ''),
        'sufficiency': ranking_debug.get('sufficiency', ''),
        'provider_coverage': ensure_dict(ranking_debug.get('provider_coverage', {})),
        'ranking_summary': ensure_dict(ranking_debug.get('ranking_summary', {})),
        'typed_coverage': ensure_dict(ranking_debug.get('typed_coverage', {})),
        'context_risks': ensure_list(ranking_debug.get('context_risks', [])),
        'quality_signals': ensure_dict(ranking_debug.get('quality_signals', {})),
        'lead_news': ensure_dict(ranking_debug.get('lead_news', {})),
        'top_ranked': ensure_list(ranking_debug.get('top_ranked', []))[:3],
        'top_rejected': ensure_list(ranking_debug.get('top_rejected', []))[:3],
    }


def _extract_debug_view(*, synthesis: dict, news_context: dict,
                        transcript_trace: dict) -> dict:
    if synthesis:
        debug_view = ensure_dict(build_debug_view(synthesis))
    else:
        debug_view = {}
    if debug_view:
        return debug_view

    ranking_debug = _extract_ranking_debug(news_context)
    direct_news = ensure_list(news_context.get('direct_event_news', []))
    background_news = ensure_list(news_context.get('background_news', []))
    return {
        'summary': {
            'sources_used': ['news', 'transcripts'],
            'news_count': len(direct_news) + len(background_news),
            'transcript_count': len(ensure_list(transcript_trace.get('retrieval_hits', []))),
            'has_market_data': False,
            'has_history': False,
        },
        'runtime_health': {},
        'context_risks': {
            'news': ensure_list(news_context.get('context_risks', [])),
            'transcripts': [],
        },
        'top_evidence': {
            'lead_transcript': ensure_dict(transcript_trace.get('lead_candidate', {})),
            'transcript_candidates': ensure_list(transcript_trace.get('top_candidates', [])),
            'retrieval_hits': ensure_list(transcript_trace.get('retrieval_hits', []))[:3],
            'news_items': direct_news[:3] or background_news[:3],
        },
        'status': {
            'news': {
                'status': news_context.get('news_status', ''),
                'freshness': news_context.get('freshness', ''),
                'sufficiency': news_context.get('sufficiency', ''),
                'coverage_state': ensure_dict(ranking_debug.get('typed_coverage', {})).get('coverage_state', ''),
            },
        },
    }


def _normalize_news_item(item: dict, tag: str) -> dict:
    item = ensure_dict(item)
    return {
        'headline': item.get('headline', ''),
        'source': item.get('source', ''),
        'published_at': item.get('published_at') or item.get('published') or '',
        'url': item.get('url', ''),
        'tag': tag,
    }


def _build_evidence_sources(payload: dict) -> list[dict]:
    evidence = ensure_list(ensure_dict(payload.get('analysis_card', {})).get('evidence', []))
    direct = ensure_list(payload.get('direct_event_news', []))
    background = ensure_list(payload.get('background_news', []))
    transcript = ensure_dict(payload.get('transcript_trace', {}))
    lead_transcript = ensure_dict(transcript.get('lead_candidate', {}))

    source_queue = []
    for item in direct[:2]:
        source_queue.append({
            'sourceType': 'direct',
            'sourceLabel': item.get('source', ''),
            'tag': 'DIRECT',
            'headline': item.get('headline', ''),
        })
    if lead_transcript:
        source_queue.append({
            'sourceType': 'transcript',
            'sourceLabel': lead_transcript.get('source_ref') or lead_transcript.get('event_title', ''),
            'tag': 'TRANSCRIPT',
            'headline': lead_transcript.get('event_title', ''),
        })
    for item in background[:2]:
        source_queue.append({
            'sourceType': 'background',
            'sourceLabel': item.get('source', ''),
            'tag': 'BG',
            'headline': item.get('headline', ''),
        })
    if not source_queue:
        source_queue.append({
            'sourceType': 'background',
            'sourceLabel': 'No linked source yet',
            'tag': 'BG',
            'headline': '',
        })

    mapped = []
    for idx, _ in enumerate(evidence):
        source = source_queue[min(idx, len(source_queue) - 1)]
        mapped.append({'evidenceIdx': idx, **source})
    return mapped


def _render_context_risks(risks: list[str]) -> str:
    risks = _dedupe_strings(risks)
    if not risks:
        return ''
    return 'Context risks: ' + ', '.join(risks[:3])


def _dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out

