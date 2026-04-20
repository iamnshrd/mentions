"""Speaker event market synthesis, V1 event-level market view.

Triggered when the user provides a Kalshi URL or a known speaker-event ticker.
For V1, output centers on the event/market as a whole, not on a single strike.
Strikes remain supporting context only.
"""
from __future__ import annotations

import logging

from agents.mentions.presentation.speaker_report import render_analysis_report, sharpen_market_flattens, summarize_news
from agents.mentions.services.speakers.paths import (
    build_interpretation_block,
    build_strike_baskets,
    build_topic_path_map,
)
from agents.mentions.trace import new_run_id, trace_log
from agents.mentions.utils import timed

log = logging.getLogger('mentions')


@timed('synthesize_speaker')
def synthesize_speaker_market(ticker: str,
                               market_data: dict,
                               transcripts: list[dict],
                               news: list[dict],
                               url_info: dict | None = None,
                               transcript_bundle: dict | None = None) -> dict:
    from agents.mentions.services.analysis.speaker_extract import (
        extract_speaker, analyse_speaker_tendency,
    )
    from agents.mentions.services.analysis.event_context import analyze_event_context
    from agents.mentions.services.analysis.signal import assess_signal
    from agents.mentions.services.markets.trade_params import compute_trade_params

    url_info = url_info or {}
    transcript_bundle = transcript_bundle or {}
    run_id = transcript_bundle.get('run_id') or new_run_id()
    trace_log('synthesis.start', run_id=run_id, ticker=ticker, title=market_data.get('event_title') or market_data.get('title') or '', news_count=len(news), transcript_candidates=len(transcript_bundle.get('top_candidates', [])))

    speaker_info = extract_speaker(market_data, url_info=url_info)
    speaker_name = speaker_info.get('speaker_name', 'Unknown Speaker')
    speaker_slug = speaker_info.get('speaker_slug', '')

    if not transcripts and speaker_name and speaker_name != 'Unknown Speaker':
        transcripts = _fetch_speaker_transcripts(speaker_name, speaker_slug)

    tendency = analyse_speaker_tendency(speaker_name, speaker_slug, transcripts)
    transcript_evidence = _best_transcript_excerpt(transcripts, speaker_name)

    event_ctx = analyze_event_context(market_data, news, {
        'speaker_name': speaker_name,
        'speaker_org': speaker_info.get('speaker_org', ''),
    })

    frame = {
        'route': 'speaker-event',
        'category': speaker_info.get('domain', 'general'),
        'mode': 'deep',
    }
    signal = assess_signal({
        'market_data': market_data,
        'history': [],
        'ticker': ticker,
    }, frame)

    confidence = _compute_confidence(
        has_market=bool(market_data),
        has_transcripts=bool(transcripts),
        has_news=bool(news),
        tendency=tendency.get('tendency', 'unknown'),
        transcript_bundle=transcript_bundle,
        event_ctx=event_ctx,
    )

    trade = compute_trade_params(
        market_data=market_data,
        speaker_tendency={**tendency, 'speaker_name': speaker_name},
        confidence=confidence,
        event_context=event_ctx,
    )

    event_title = market_data.get('title', ticker)
    family_title = market_data.get('event_title') or event_title
    strike_title = market_data.get('yes_sub_title') or market_data.get('strike_title') or ''
    strike_list = market_data.get('strike_list') or ([strike_title] if strike_title else [])

    evidence_view = _build_evidence_view(news, transcript_bundle, event_ctx)
    topic_paths = build_topic_path_map(transcript_bundle, event_ctx)
    transcript_bundle = {**transcript_bundle, 'topic_paths': topic_paths}
    interpretation_block = build_interpretation_block(event_ctx, transcript_bundle, evidence_view)
    transcript_bundle = {**transcript_bundle, 'media_context': interpretation_block.get('media_context') or {}}
    strike_baskets = build_strike_baskets(strike_list, event_ctx, transcript_bundle, topic_paths)

    reasoning = _build_market_reasoning(
        ticker=ticker,
        event_title=event_title,
        family_title=family_title,
        strike_title=strike_title,
        market_data=market_data,
        speaker_info=speaker_info,
        tendency=tendency,
        event_ctx=event_ctx,
        trade=trade,
        signal=signal,
        has_news=bool(news),
        has_transcripts=bool(transcripts),
        transcript_bundle=transcript_bundle,
        evidence_view=evidence_view,
        interpretation_block=interpretation_block,
    )

    conclusion = _build_market_conclusion(
        event_title=event_title,
        strike_title=strike_title,
        tendency=tendency,
        trade=trade,
        confidence=confidence,
        has_news=bool(news),
        has_transcripts=bool(transcripts),
        transcript_bundle=transcript_bundle,
        evidence_view=evidence_view,
        interpretation_block=interpretation_block,
    )

    synthesis = {
        'ticker': ticker,
        'analysis_confidence': confidence,
        'market': {
            'title': event_title,
            'event_title': family_title,
            'strike_title': strike_title,
            'strike_list': strike_list,
            'ticker': ticker,
            'volume': market_data.get('volume'),
            'close_time': market_data.get('close_time', market_data.get('expiration_time', '')),
            'rules': market_data.get('rules_primary', market_data.get('rules', '')),
            'status': market_data.get('status', ''),
        },
        'speaker': {
            'name': speaker_name,
            'slug': speaker_slug,
            'org': speaker_info.get('speaker_org', ''),
            'domain': speaker_info.get('domain', ''),
            'event_type': speaker_info.get('event_type', ''),
            'tendency': tendency.get('tendency', 'unknown'),
            'tendency_reasoning': tendency.get('reasoning', ''),
            'evidence_count': tendency.get('evidence_count', 0),
        },
        'event_context': event_ctx,
        'transcript_evidence': transcript_evidence,
        'news_context': summarize_news(news),
        'transcript_context': _summarize_transcript_bundle(transcript_bundle),
        'transcript_trace': _build_transcript_trace(transcript_bundle),
        'evidence_view': evidence_view,
        'interpretation_block': interpretation_block,
        'media_context': interpretation_block.get('media_context') or {},
        'topic_paths': topic_paths,
        'strike_baskets': strike_baskets,
        'analysis_params': {
            'difficulty': trade.get('difficulty', 'medium'),
            'difficulty_factors': trade.get('difficulty_factors', []),
            'win_condition': trade.get('win_condition', ''),
        },
        'trade_params': trade,
        'signal_assessment': signal,
        'reasoning_chain': reasoning,
        'analysis_report': render_analysis_report(
            event_title=event_title,
            event_ctx=event_ctx,
            interpretation_block=interpretation_block,
            evidence_view=evidence_view,
            news=news,
            transcript_bundle=transcript_bundle,
            confidence=confidence,
            strike_list=strike_list,
            strike_baskets=strike_baskets,
            topic_paths=topic_paths,
            market_meta={
                'entity_kind': market_data.get('entity_kind', 'event' if (market_data.get('event_markets') or []) else 'market'),
                'resolution_source': market_data.get('resolution_source', ''),
            },
        ),
        'conclusion': conclusion,
        'confidence': confidence,
        'confidence_label': 'analysis confidence',
        'confidence_scope': 'context-grounding',
        'supporting_strikes': strike_list,
    }
    trace_log('synthesis.finish', run_id=run_id, ticker=ticker, analysis_confidence=confidence, direct_core=len((transcript_bundle.get('core_hits') or [])), spillover=len((transcript_bundle.get('spillover_hits') or [])), generic_regime=len((transcript_bundle.get('generic_regime_hits') or [])))
    return synthesis


def _fetch_speaker_transcripts(speaker_name: str, speaker_slug: str, limit: int = 10) -> list[dict]:
    try:
        from agents.mentions.services.knowledge import query_transcripts
        from agents.mentions.utils import fts_query
        search = fts_query(speaker_name or speaker_slug)
        if not search:
            return []
        return query_transcripts(search, limit=limit, speaker=speaker_name)
    except Exception as exc:
        log.debug('Transcript fetch failed: %s', exc)
        return []


def _best_transcript_excerpt(chunks: list[dict], speaker_name: str, max_excerpts: int = 3) -> str:
    if not chunks:
        return ''
    relevant = [c for c in chunks if speaker_name.lower() in (c.get('speaker') or '').lower() or not c.get('speaker')]
    if not relevant:
        relevant = chunks
    parts: list[str] = []
    seen: set[str] = set()
    for chunk in relevant[:max_excerpts]:
        text = (chunk.get('text') or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        if len(text) > 180:
            cut = text[:180].rfind('. ')
            text = text[:cut + 1] if cut > 80 else text[:180] + '…'
        label = chunk.get('speaker') or speaker_name
        parts.append(f'"{text}" — {label}')
    return '\n\n'.join(parts)


def _compute_confidence(has_market: bool, has_transcripts: bool, has_news: bool, tendency: str,
                        transcript_bundle: dict | None = None,
                        event_ctx: dict | None = None) -> str:
    transcript_bundle = transcript_bundle or {}
    event_ctx = event_ctx or {}
    score = sum([has_market, has_transcripts, has_news])
    if tendency in ('hit_all', 'evasive'):
        score += 1
    support_strength = ((transcript_bundle.get('speaker_context') or {}).get('support_strength') or '').lower()
    format_analogs = len(transcript_bundle.get('format_analogs') or [])
    topic_analogs = len(transcript_bundle.get('topic_analogs') or [])
    support_shape = (transcript_bundle.get('support_shape') or '').lower()
    news_contract = (event_ctx.get('news_context') or {}).get('typed_news') or {}
    coverage_state = (news_contract.get('coverage_state') or '').lower()
    if support_strength == 'high':
        score += 1
    if format_analogs and topic_analogs:
        score += 1
    if coverage_state == 'event-led':
        score += 1
    elif coverage_state == 'ambient-only':
        score -= 1
    if support_shape == 'core-led':
        score += 1
    elif support_shape == 'generic-only':
        score -= 1
    elif support_shape == 'spillover-led':
        score -= 0.5
    if coverage_state in {'ambient-only', 'empty'} and support_shape in {'generic-only', 'empty'}:
        score -= 1
    if score >= 5:
        return 'high'
    if score >= 2:
        return 'medium'
    return 'low'


def _interpretation_reasoning(interpretation_block: dict | None, signal: dict | None) -> list[str]:
    steps: list[str] = []
    interpretive_line = _render_interpretive_state(interpretation_block, signal)
    if interpretive_line:
        steps.append(f"Интерпретационный вывод: {interpretive_line}")
    signal_line = _signal_line(signal)
    if signal_line:
        steps.append(signal_line)
    return steps


def _event_context_reasoning(event_ctx: dict, evidence_view: dict | None, has_news: bool) -> list[str]:
    steps: list[str] = []
    fmt = event_ctx.get('format', 'event')
    venue = event_ctx.get('venue', 'unknown venue')
    qa = event_ctx.get('qa_likelihood', 'medium')
    steps.append(f'Формат события: {_humanize_event_format(fmt)}, площадка {_humanize_venue(venue)}, вероятность Q&A: {_humanize_level(qa)}.')
    topics = event_ctx.get('likely_topics', [])
    if topics:
        steps.append(f'Наиболее естественные темы в текущем контексте: {", ".join(topics[:5])}.')
    else:
        steps.append('Тематический контекст пока тонкий, поэтому текущая интерпретация ещё слабо заземлена свежими подтверждениями.')
    news_contract = (evidence_view or {}).get('news_contract') or {}
    coverage_state = news_contract.get('coverage_state') or ''
    if evidence_view and evidence_view.get('news_line'):
        steps.append(evidence_view['news_line'])
    elif coverage_state == 'ambient-only':
        steps.append('Свежий новостной контекст есть, но это скорее общий режимный фон, а не прямое покрытие самого события.')
    elif coverage_state == 'topic-led':
        steps.append('Свежий новостной контекст есть, но он больше расширяет соседние темы, чем напрямую заземляет само событие.')
    else:
        steps.append('Свежий новостной контекст доступен.' if has_news else 'Свежий новостной контекст пока тонкий.')
    return steps


def _build_market_reasoning(ticker: str, event_title: str, family_title: str, strike_title: str,
                            market_data: dict, speaker_info: dict, tendency: dict,
                            event_ctx: dict, trade: dict, signal: dict,
                            has_news: bool, has_transcripts: bool,
                            transcript_bundle: dict | None = None,
                            evidence_view: dict | None = None,
                            interpretation_block: dict | None = None) -> list[str]:
    steps: list[str] = []
    steps.append(f'Событие рынка: {event_title}.')
    if family_title and family_title != event_title:
        steps.append(f'Контекст семейства рынка: {family_title}.')
    strike_list = market_data.get('strike_list') or ([strike_title] if strike_title else [])
    if strike_list:
        steps.append(f'Список страйков Kalshi: {", ".join(strike_list[:8])}.')
    steps.append(f'Сложность рынка сейчас оценивается как {_humanize_difficulty(trade.get("difficulty", "medium"))}.')
    speaker = speaker_info.get('speaker_name', 'Speaker')
    speaker_line = _speaker_context_line(speaker, tendency)
    if speaker_line:
        steps.append(speaker_line)
    steps.extend(_event_context_reasoning(event_ctx, evidence_view, has_news))
    if has_transcripts:
        steps.append(_transcript_reasoning_line(transcript_bundle))
    else:
        steps.append('Транскриптная опора по спикеру пока отсутствует.')
    if evidence_view and evidence_view.get('synthesis_line'):
        steps.append(evidence_view['synthesis_line'])
    steps.extend(_interpretation_reasoning(interpretation_block, signal))
    return steps


def _conclusion_support_state(has_news: bool, has_transcripts: bool) -> str:
    evidence_state = []
    evidence_state.append('свежий новостной контекст есть' if has_news else 'свежий новостной контекст пока тонкий')
    evidence_state.append('транскриптная опора есть' if has_transcripts else 'транскриптная опора пока пустая')
    return ', '.join(evidence_state)


def _build_market_conclusion(event_title: str, strike_title: str, tendency: dict,
                             trade: dict, confidence: str,
                             has_news: bool, has_transcripts: bool,
                             transcript_bundle: dict | None = None,
                             evidence_view: dict | None = None,
                             interpretation_block: dict | None = None) -> str:
    difficulty = trade.get('difficulty', 'medium')
    tend = tendency.get('tendency', 'unknown')
    support = _conclusion_support_state(has_news, has_transcripts)
    strike_note = ' Список страйков Kalshi доступен.' if strike_title else ''
    transcript_note = _transcript_conclusion_note(transcript_bundle)
    evidence_note = (evidence_view or {}).get('conclusion_note', '')
    interpretation_note = _render_interpretive_state(interpretation_block, None)
    tendency_note = '' if tend in {'mixed', 'unknown'} else f'Речевой профиль спикера: {tend}. '
    support_sentence = support[:1].upper() + support[1:] + '.' if support else ''
    parts = [
        f'Итоговая интерпретация по событию: {event_title}.',
        f'Сложность: {_humanize_difficulty(difficulty)}.',
        f'Уровень уверенности анализа: {_humanize_confidence(confidence)}.',
        support_sentence,
    ]
    if tendency_note:
        parts.insert(2, tendency_note.strip())
    if strike_note:
        parts.append(strike_note.strip())
    if interpretation_note:
        parts.append(interpretation_note.strip())
    if evidence_note:
        parts.append(evidence_note.strip())
    if transcript_note:
        parts.append(transcript_note.strip())
    return ' '.join(part for part in parts if part).strip()


def _evidence_conclusion_state(top_news: list[dict], top_transcript: list[dict],
                               news_contract: dict | None = None,
                               transcript_contract: dict | None = None) -> str:
    news_contract = news_contract or {}
    transcript_contract = transcript_contract or {}
    coverage_state = news_contract.get('coverage_state') or ''
    support_shape = transcript_contract.get('support_shape') or ''
    if top_news and top_transcript:
        if coverage_state == 'event-led' and support_shape == 'core-led':
            return 'event-and-core-aligned'
        return 'news-and-transcript-aligned'
    if top_news:
        if coverage_state == 'ambient-only':
            return 'ambient-news-only'
        if coverage_state == 'topic-led':
            return 'topic-led-news-only'
        return 'event-news-with-limited-transcripts'
    if top_transcript:
        if support_shape == 'generic-only':
            return 'generic-transcript-only'
        if support_shape == 'spillover-led':
            return 'spillover-transcript-only'
        return 'transcript-stronger-than-news'
    return 'empty'


def _build_evidence_view(news: list[dict], transcript_bundle: dict | None, event_ctx: dict | None) -> dict:
    transcript_bundle = transcript_bundle or {}
    event_ctx = event_ctx or {}
    ranked_news = _rank_news_for_reasoning(news)
    top_news = ranked_news[:3]
    top_topics = event_ctx.get('likely_topics', [])[:3]
    top_transcript = (transcript_bundle.get('top_candidates') or [])[:1]
    news_line = ''
    synthesis_line = ''
    news_contract = (event_ctx.get('news_context') or {}).get('typed_news') or {}
    transcript_contract = transcript_bundle

    if top_news:
        lead = top_news[0]
        headline = lead.get('headline') or lead.get('title') or ''
        source = lead.get('source') or 'news source'
        coverage_state = news_contract.get('coverage_state') or ''
        if headline:
            if coverage_state == 'topic-led':
                news_line = f'Fresh news context is present, but it looks more topic-adjacent than event-direct. Lead item: {headline} ({source}).'
            elif coverage_state == 'ambient-only':
                news_line = f'Fresh news context exists, but it is mostly ambient regime coverage. Lead item: {headline} ({source}).'
            else:
                news_line = f'Fresh news context is available. Lead event coverage: {headline} ({source}).'
    if top_topics and top_transcript:
        topic_text = ', '.join(top_topics)
        lead_transcript = top_transcript[0].get('event_title') or 'historical analog'
        support_shape = transcript_contract.get('support_shape') or ''
        if support_shape == 'spillover-led':
            synthesis_line = f'Current event picture is anchored by topics like {topic_text}, but the best transcript analog still looks more spillover than direct event support ({lead_transcript}).'
        elif support_shape == 'generic-only':
            synthesis_line = f'Current event picture is anchored by topics like {topic_text}, but transcript support is still mostly generic regime context ({lead_transcript}).'
        else:
            synthesis_line = f'Current event picture is anchored by topics like {topic_text}, and the best historical analog is {lead_transcript}.'
    elif top_topics:
        topic_text = ', '.join(top_topics)
        synthesis_line = f'Current event picture is anchored by topics like {topic_text}.'

    return {
        'news_line': news_line,
        'synthesis_line': synthesis_line,
        'conclusion_state': _evidence_conclusion_state(top_news, top_transcript, news_contract=news_contract, transcript_contract=transcript_contract),
        'lead_news': top_news[0] if top_news else {},
        'lead_transcript': top_transcript[0] if top_transcript else {},
        'lead_transcript_trace': (top_transcript[0] or {}).get('trace', {}) if top_transcript else {},
        'news_contract': news_contract,
        'transcript_contract': transcript_contract,
    }


def _speaker_context_line(speaker: str, tendency: dict | None) -> str:
    tendency = tendency or {}
    tend = (tendency.get('tendency') or 'unknown').lower()
    reasoning = (tendency.get('reasoning') or '').strip()
    if tend in {'unknown', 'mixed'}:
        return ''
    if reasoning:
        return f'Профиль речи спикера: {speaker}, типичный паттерн {tend}. {reasoning}'
    return f'Профиль речи спикера: {speaker}, типичный паттерн {tend}.'


def _render_interpretive_state(interpretation_block: dict | None, signal: dict | None) -> str:
    interpretation_block = interpretation_block or {}
    state = (interpretation_block.get('interpretive_state') or '').lower()
    if state == 'weak-grounding':
        return 'Опора пока слишком тонкая, чтобы уверенно говорить о сильной заземлённости события.'
    if state == 'structured-not-grounded':
        return 'Контекст пока больше говорит о структуре события, чем о сильной заземлённой интерпретации.'
    if state == 'evidence-note':
        return ''
    return ''


def _signal_line(signal: dict | None) -> str:
    signal = signal or {}
    verdict = (signal.get('verdict') or '').lower()
    strength = (signal.get('signal_strength') or '').lower()
    note = (signal.get('note') or '').strip()
    if verdict in {'', 'unclear'}:
        return ''
    rendered_verdict = _humanize_signal_verdict(verdict)
    rendered_strength = _humanize_level(strength)
    if note and strength and strength != 'unknown':
        return f'Оценка рыночного сигнала: {rendered_verdict} ({rendered_strength}). {note}'
    if note:
        return f'Оценка рыночного сигнала: {rendered_verdict}. {note}'
    return f'Оценка рыночного сигнала: {rendered_verdict}.'


from agents.mentions.presentation.normalizer import (
    normalize_confidence as _normalize_confidence,
    normalize_difficulty as _normalize_difficulty,
    normalize_format as _normalize_event_format,
    normalize_level as _normalize_level,
    normalize_signal_verdict as _normalize_signal_verdict,
    normalize_venue as _normalize_venue,
)


def _humanize_difficulty(value: str) -> str:
    return _normalize_difficulty(value)


def _humanize_confidence(value: str) -> str:
    mapping = {
        'high': 'высокий',
        'medium': 'умеренный',
        'low': 'низкий',
    }
    return mapping.get((value or '').lower(), value)


def _humanize_level(value: str) -> str:
    return _normalize_level(value)


def _humanize_event_format(value: str) -> str:
    return _normalize_event_format(value)


def _humanize_venue(value: str) -> str:
    return _normalize_venue(value)


def _humanize_signal_verdict(value: str) -> str:
    return _normalize_signal_verdict(value)


def _rank_news_for_reasoning(news: list[dict]) -> list[dict]:
    if not isinstance(news, list):
        return []
    preferred = ['pbs', 'associated press', 'ap', 'reuters', 'politico', 'the hill', 'guardian', 'bbc', 'npr', 'c-span', 'washington post', 'the nevada independent']
    def score(item: dict) -> tuple[float, float]:
        source = (item.get('source') or '').lower()
        source_boost = 0.0
        for idx, name in enumerate(preferred):
            if name in source:
                source_boost = 100 - idx
                break
        rel = float(item.get('final_relevance_score') or 0)
        return (source_boost, rel)
    return sorted(news, key=score, reverse=True)


def _transcript_reasoning_line(transcript_bundle: dict | None) -> str:
    transcript_bundle = transcript_bundle or {}
    summary = transcript_bundle.get('retrieval_summary') or ''
    top = transcript_bundle.get('top_candidates') or []
    if not top:
        return 'Транскриптная опора по спикеру есть, но качество аналогов пока слабое.'
    lead = top[0]
    lead_title = lead.get('event_title') or 'исторический аналог'
    reasons = ', '.join(lead.get('match_reasons') or [])
    if summary and reasons:
        return f'Транскриптная опора по спикеру: {summary} Лучший аналог: {lead_title} ({reasons}).'
    if summary:
        return f'Транскриптная опора по спикеру: {summary}'
    return f'Транскриптная опора по спикеру: лучший аналог {lead_title}.'


def _transcript_conclusion_note(transcript_bundle: dict | None) -> str:
    transcript_bundle = transcript_bundle or {}
    speaker_context = transcript_bundle.get('speaker_context') or {}
    strength = speaker_context.get('support_strength') or ''
    top = transcript_bundle.get('top_candidates') or []
    if strength == 'high' and top:
        return 'Транскриптная аналогия выглядит сильной.'
    if strength == 'medium':
        return 'Транскриптная аналогия полезна, но не является решающей.'
    if top:
        return 'Транскриптная аналогия есть, но пока остаётся слабой.'
    return ''


def _summarize_transcript_bundle(transcript_bundle: dict | None) -> str:
    transcript_bundle = transcript_bundle or {}
    summary = transcript_bundle.get('retrieval_summary') or ''
    core_hits = transcript_bundle.get('core_hits') or []
    generic_regime_hits = transcript_bundle.get('generic_regime_hits') or []
    media_analogs = transcript_bundle.get('media_analogs') or []
    parts = [summary] if summary else []
    if core_hits:
        families = list({row.get('family') for row in core_hits[:3] if row.get('family')})
        if families:
            parts.append(f"Direct core: {', '.join(families)}.")
    if generic_regime_hits:
        families = list({row.get('family') for row in generic_regime_hits[:4] if row.get('family')})
        if families:
            parts.append(f"Regime-embedded context: {', '.join(families)}.")
    if media_analogs:
        titles = [row.get('event_title') for row in media_analogs[:2] if row.get('event_title')]
        if titles:
            parts.append(f"Media-format analogs: {', '.join(titles)}.")
    return ' '.join(part for part in parts if part).strip()


def _trace_rows(rows: list[dict], limit: int = 3) -> list[dict]:
    out: list[dict] = []
    for row in rows[:limit]:
        trace = row.get('trace') or {}
        out.append({
            'transcript_id': row.get('transcript_id'),
            'event_title': row.get('event_title') or trace.get('event_title', ''),
            'family': row.get('family', ''),
            'evidence_type': row.get('evidence_type', ''),
            'quote': row.get('quote', ''),
            'relevance_score': row.get('relevance_score', 0),
            'trace': trace,
        })
    return out


def _build_transcript_trace(transcript_bundle: dict | None) -> dict:
    transcript_bundle = transcript_bundle or {}
    top_candidates = transcript_bundle.get('top_candidates') or []
    core_hits = transcript_bundle.get('core_hits') or []
    spillover_hits = transcript_bundle.get('spillover_hits') or []
    generic_regime_hits = transcript_bundle.get('generic_regime_hits') or []
    media_analogs = transcript_bundle.get('media_analogs') or []
    return {
        'lead_candidate': _trace_rows(top_candidates, limit=1)[0] if top_candidates else {},
        'top_candidates': _trace_rows(top_candidates, limit=3),
        'core_hits': _trace_rows(core_hits, limit=3),
        'spillover_hits': _trace_rows(spillover_hits, limit=3),
        'generic_regime_hits': _trace_rows(generic_regime_hits, limit=3),
        'media_analogs': _trace_rows(media_analogs, limit=3),
        'support_shape': transcript_bundle.get('support_shape', ''),
    }
