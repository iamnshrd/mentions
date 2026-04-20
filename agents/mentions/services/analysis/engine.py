from __future__ import annotations

import logging

from mentions_domain.normalize import ensure_dict, ensure_list, normalize_confidence

log = logging.getLogger('mentions')


def analyze_evidence_bundle(query: str, frame: dict, bundle: dict) -> dict:
    from agents.mentions.services.analysis.market import analyze_market
    from agents.mentions.services.analysis.reasoning import build_reasoning_chain
    from agents.mentions.services.analysis.signal import assess_signal
    from agents.mentions.services.analysis.speaker import extract_speaker_context

    frame = ensure_dict(frame)
    bundle = ensure_dict(bundle)

    market = ensure_dict(bundle.get('market', {}))
    transcripts = ensure_list(bundle.get('transcripts', []))
    news = ensure_list(bundle.get('news', []))
    workflow_policy = ensure_dict(bundle.get('workflow_policy', {}))
    pmt_knowledge = ensure_dict(bundle.get('pmt_knowledge', {}))
    fused_evidence = ensure_dict(bundle.get('fused_evidence', {}))
    transcript_intelligence = ensure_dict(bundle.get('transcript_intelligence', {}))
    news_context_bundle = ensure_dict(bundle.get('news_context', {}))

    market_summary = analyze_market(market, frame)
    signal = assess_signal(market, frame)
    transcript_context = extract_speaker_context(transcripts, query)
    reasoning = build_reasoning_chain(
        query=query,
        frame=frame,
        market_summary=market_summary,
        signal=signal,
        transcript_context=transcript_context,
        news=news,
    )

    confidence = _compute_confidence(bundle, signal, workflow_policy)
    conclusion = _build_conclusion(signal, reasoning, confidence, workflow_policy)

    market_payload = ensure_dict(bundle.get('market', {}))
    market_data = ensure_dict(market_payload.get('market_data', {}))
    resolved_market = ensure_dict(market_data.get('resolved_market', {}))

    analysis = {
        'market_summary': market_summary,
        'signal_assessment': signal,
        'reasoning_chain': reasoning + _pmt_reasoning_tail(pmt_knowledge),
        'transcript_context': transcript_context,
        'news_context': _summarize_news(news),
        'conclusion': conclusion,
        'confidence': confidence,
        'recommended_action': _recommend_action(signal, confidence, workflow_policy),
        'policy_context': workflow_policy,
        'resolved_market': resolved_market,
        'pmt_knowledge': pmt_knowledge,
        'fused_evidence': fused_evidence,
        'evidence_debug': _build_evidence_debug(
            bundle=bundle,
            transcripts=transcripts,
            transcript_intelligence=transcript_intelligence,
            news=news,
            news_context=news_context_bundle,
        ),
    }

    try:
        from agents.mentions.services.analysis.engine_v2 import build_analysis_profiles
        analysis['analysis_profiles'] = build_analysis_profiles(query, frame, bundle, analysis)
    except Exception as exc:
        log.debug('build_analysis_profiles failed: %s', exc)
        analysis['analysis_profiles'] = {}

    return analysis


def _build_evidence_debug(*, bundle: dict, transcripts: list, transcript_intelligence: dict,
                          news: list, news_context: dict) -> dict:
    market = ensure_dict(bundle.get('market', {}))
    market_data = ensure_dict(market.get('market_data', {}))
    runtime_health = ensure_dict(bundle.get('runtime_health', {}))
    return {
        'source_summary': {
            'has_market_data': bool(market_data),
            'has_history': bool(market.get('history')),
            'news_count': len(news),
            'transcript_count': len(transcripts),
            'sources_used': ensure_list(bundle.get('sources_used', [])),
        },
        'runtime_health': runtime_health,
        'context_risks': {
            'news': ensure_list(news_context.get('context_risks', [])),
            'transcripts': ensure_list(transcript_intelligence.get('context_risks', [])),
        },
        'transcript_trace': _build_transcript_debug(transcripts, transcript_intelligence),
        'news_trace': _build_news_debug(news, news_context),
    }


def _build_transcript_debug(transcripts: list, transcript_intelligence: dict) -> dict:
    transcript_intelligence = ensure_dict(transcript_intelligence)
    lead_candidate = ensure_dict(transcript_intelligence.get('lead_candidate', {}))
    top_candidates = ensure_list(transcript_intelligence.get('top_candidates', []))
    top_candidate_traces = []
    for row in top_candidates[:3]:
        trace = _trace_from_candidate(row)
        if trace:
            top_candidate_traces.append(trace)
    retrieval_hit_traces = []
    for row in transcripts[:3]:
        trace = _trace_from_row(row)
        if trace:
            retrieval_hit_traces.append(trace)
    return {
        'lead_candidate': _trace_from_candidate(lead_candidate),
        'top_candidates': top_candidate_traces,
        'retrieval_hits': retrieval_hit_traces,
    }


def _build_news_debug(news: list, news_context: dict) -> dict:
    news_context = ensure_dict(news_context)
    items = []
    for row in news[:3]:
        if not isinstance(row, dict):
            continue
        items.append({
            'headline': row.get('headline', ''),
            'url': row.get('url', ''),
            'source': row.get('source', ''),
            'published_at': row.get('published_at', '') or row.get('published', ''),
        })
    return {
        'status': news_context.get('status', ''),
        'freshness': news_context.get('freshness', ''),
        'sufficiency': news_context.get('sufficiency', ''),
        'items': items,
    }


def _trace_from_candidate(row: dict) -> dict:
    row = ensure_dict(row)
    trace = ensure_dict(row.get('trace', {}))
    if trace:
        return trace
    return {}


def _trace_from_row(row: dict) -> dict:
    row = ensure_dict(row)
    trace = ensure_dict(row.get('trace', {}))
    if trace:
        return trace
    fields = {
        'chunk_id': row.get('chunk_id'),
        'document_id': row.get('document_id'),
        'chunk_index': row.get('chunk_index'),
        'source_file': row.get('source_file'),
        'source_url': row.get('source_url') or row.get('url'),
        'speaker': row.get('speaker'),
        'speaker_canonical': row.get('speaker_canonical'),
        'section': row.get('section'),
        'event': row.get('event'),
        'event_date': row.get('event_date'),
        'char_start': row.get('char_start'),
        'char_end': row.get('char_end'),
    }
    compact = {key: value for key, value in fields.items() if value not in (None, '', [])}
    return compact


def _compute_confidence(bundle: dict, signal: dict, workflow_policy: dict) -> str:
    has_live = bool(ensure_dict(bundle.get('market', {})).get('market_data'))
    has_history = bool(ensure_dict(bundle.get('market', {})).get('history'))
    has_transcripts = bool(bundle.get('transcripts'))
    has_news = bool(bundle.get('news'))

    score = sum([has_live, has_history, has_transcripts, has_news])
    signal_str = signal.get('signal_strength', 'unknown') if isinstance(signal, dict) else 'unknown'

    confidence = 'low'
    if score >= 3 and signal_str in ('strong', 'moderate'):
        confidence = 'high'
    elif score >= 2:
        confidence = 'medium'
    elif score >= 1:
        confidence = 'low'

    if workflow_policy.get('decision') == 'partial_only' and confidence == 'high':
        confidence = 'medium'
    if workflow_policy.get('decision') == 'clarify':
        confidence = 'low'

    return normalize_confidence(confidence)


def _build_conclusion(signal: dict, reasoning: list, confidence: str, workflow_policy: dict) -> str:
    if not isinstance(signal, dict):
        return 'Данных пока недостаточно для внятного вывода.'

    verdict = signal.get('verdict', 'unclear')
    strength = signal.get('signal_strength', 'unknown')

    parts = []
    if workflow_policy.get('decision') == 'clarify':
        parts.append('Связка рынка с событием пока слишком слабая для чистого вывода.')
    elif verdict == 'signal':
        parts.append(f'Это больше похоже на реальный сигнал (сила: {strength}).')
    elif verdict == 'noise':
        parts.append('Это больше похоже на рыночный шум, чем на осмысленное движение.')
    else:
        parts.append('Разделение между signal и noise пока остаётся неясным.')

    parts.append(f'Уверенность: {confidence}.')

    if workflow_policy.get('reasons'):
        parts.append('Ограничения policy: ' + ', '.join(workflow_policy['reasons']) + '.')
    elif reasoning:
        parts.append('Ключевой фактор: ' + reasoning[-1])

    return ' '.join(parts)


def _summarize_news(news: list) -> str:
    if not news:
        return ''
    headlines = [n.get('headline', '') for n in news[:3] if isinstance(n, dict) and n.get('headline')]
    return '; '.join(headlines) if headlines else ''


def _pmt_reasoning_tail(pmt_knowledge: dict) -> list[str]:
    tail = []
    for key in ['pricing_signals', 'execution_patterns', 'phase_logic', 'decision_cases', 'speaker_profiles']:
        rows = pmt_knowledge.get(key, []) if isinstance(pmt_knowledge, dict) else []
        if rows:
            first = rows[0]
            name = first.get('signal_name') or first.get('pattern_name') or first.get('phase_name') or first.get('market_context') or first.get('speaker_name') or key
            tail.append(f'PMT KB: {key} -> {name}')
    return tail[:5]


def _recommend_action(signal: dict, confidence: str, workflow_policy: dict) -> str:
    if workflow_policy.get('allow_trade_recommendation') is False:
        return 'Пока наблюдать, policy ещё не разрешает trade recommendation'

    if not isinstance(signal, dict):
        return 'Пока наблюдать, данных недостаточно'

    verdict = signal.get('verdict', 'unclear')

    if confidence == 'low':
        return 'Пока наблюдать, уверенность низкая и нужно больше данных'
    if verdict == 'signal' and confidence in ('medium', 'high'):
        return 'Можно рассматривать позицию, сигнал выглядит достаточно собранным'
    if verdict == 'noise':
        return 'Скорее игнорировать, это больше похоже на шум'
    return 'Пока наблюдать, сигнал неясен'
