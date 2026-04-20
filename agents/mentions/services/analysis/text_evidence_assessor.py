from __future__ import annotations

from mentions_domain.normalize import ensure_dict, ensure_list, normalize_confidence


def assess_text_evidence(query: str, frame: dict, market_prior: dict, news_context: dict, transcript_intelligence: dict, selected_pmt_evidence: dict) -> dict:
    frame = ensure_dict(frame)
    market_prior = ensure_dict(market_prior)
    news_context = ensure_dict(news_context)
    transcript_intelligence = ensure_dict(transcript_intelligence)
    selected_pmt_evidence = ensure_dict(selected_pmt_evidence)

    news_items = ensure_list(news_context.get('news', []))
    transcript_chunks = ensure_list(transcript_intelligence.get('chunks', []))
    context_risks = ensure_list(news_context.get('context_risks', [])) + ensure_list(transcript_intelligence.get('context_risks', []))

    source_reliability = _source_reliability(news_context, transcript_intelligence, market_prior)
    contradiction_penalty = _contradiction_penalty(context_risks, market_prior)
    recency_score = _recency_score(news_context)
    transcript_score = min(len(transcript_chunks), 3)
    pmt_support_score = _pmt_support_score(selected_pmt_evidence, transcript_score, len(news_items))

    fresh_support_score = len(news_items) + transcript_score
    raw_strength = fresh_support_score + pmt_support_score - contradiction_penalty
    text_signal_strength = _strength_label(raw_strength, fresh_support_score)
    direction = _infer_direction(query, news_context, transcript_intelligence)

    return {
        'text_signal_strength': text_signal_strength,
        'direction': direction,
        'source_reliability': source_reliability,
        'contradiction_penalty': contradiction_penalty,
        'recency_score': recency_score,
        'fresh_support_score': fresh_support_score,
        'transcript_support_score': transcript_score,
        'pmt_support_score': pmt_support_score,
        'supporting_counts': {
            'news_items': len(news_items),
            'transcript_chunks': len(transcript_chunks),
        },
        'assessment_rationale': _build_rationale(frame, market_prior, news_context, transcript_intelligence, selected_pmt_evidence),
    }


def _source_reliability(news_context: dict, transcript_intelligence: dict, market_prior: dict) -> str:
    freshness = news_context.get('freshness', '')
    transcript_status = transcript_intelligence.get('status', '')
    prior_quality = market_prior.get('prior_quality', '')
    score = 0
    if freshness in ('high', 'fresh', 'stored'):
        score += 1
    if transcript_status in ('ok', 'partial'):
        score += 1
    if prior_quality == 'credible':
        score += 1
    if prior_quality in ('fragile', 'quoted_only'):
        score -= 1
    if score >= 2:
        return normalize_confidence('high')
    if score == 1:
        return normalize_confidence('medium')
    return normalize_confidence('low')


def _contradiction_penalty(context_risks: list, market_prior: dict) -> int:
    penalty = 0
    for risk in context_risks:
        if any(token in str(risk) for token in ['failed', 'missing', 'weak', 'late', 'fallback']):
            penalty += 1
    if market_prior.get('prior_quality') in ('fragile', 'quoted_only'):
        penalty += 1
    return penalty


def _recency_score(news_context: dict) -> int:
    freshness = news_context.get('freshness', '')
    if freshness == 'high':
        return 3
    if freshness in ('fresh', 'stored'):
        return 2
    if freshness in ('partial', 'stale', 'missing'):
        return 1
    return 0


def _pmt_support_score(selected_pmt_evidence: dict, transcript_score: int, news_count: int) -> int:
    score = 0
    for key in ['selected_pricing_signal', 'selected_execution_pattern', 'selected_phase_logic', 'selected_analog']:
        if ensure_dict(selected_pmt_evidence.get(key, {})):
            score += 1
    if transcript_score == 0 and news_count == 0:
        return min(score, 1)
    return min(score, 2)


def _strength_label(raw_strength: int, fresh_support_score: int) -> str:
    if fresh_support_score == 0 and raw_strength <= 1:
        return 'none'
    if raw_strength >= 5:
        return 'strong'
    if raw_strength >= 3:
        return 'moderate'
    if raw_strength >= 1:
        return 'weak'
    return 'none'


def _infer_direction(query: str, news_context: dict, transcript_intelligence: dict) -> str:
    text = ' '.join([
        query or '',
        news_context.get('summary', '') or '',
        transcript_intelligence.get('summary', '') or '',
    ]).lower()
    if any(token in text for token in ['mention', 'say', 'bring up', 'discuss']):
        return 'supports_yes'
    return 'unclear'


def _build_rationale(frame: dict, market_prior: dict, news_context: dict, transcript_intelligence: dict, selected_pmt_evidence: dict) -> list[str]:
    rationale = []
    if market_prior.get('market_regime'):
        rationale.append(f"market_regime={market_prior.get('market_regime')}")
    if frame.get('route'):
        rationale.append(f"route={frame.get('route')}")
    if news_context.get('freshness'):
        rationale.append(f"news_freshness={news_context.get('freshness')}")
    if transcript_intelligence.get('status'):
        rationale.append(f"transcript_status={transcript_intelligence.get('status')}")
    if ensure_dict(selected_pmt_evidence.get('selected_pricing_signal', {})):
        rationale.append('pmt_pricing_signal_present')
    if market_prior.get('prior_quality'):
        rationale.append(f"prior_quality={market_prior.get('prior_quality')}")
    return rationale[:10]
