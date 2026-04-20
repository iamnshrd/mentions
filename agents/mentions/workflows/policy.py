from __future__ import annotations

from mentions_domain.normalize import ensure_dict, normalize_confidence


def evaluate_workflow_policy(query: str,
                             market_data: dict | None = None,
                             news_context: dict | None = None,
                             transcript_intelligence: dict | None = None) -> dict:
    market_data = ensure_dict(market_data or {})
    news_context = ensure_dict(news_context or {})
    transcript_intelligence = ensure_dict(transcript_intelligence or {})

    resolved = ensure_dict(market_data.get('resolved_market', {}))
    sourcing = ensure_dict(market_data.get('sourcing', {}))
    provider_status = ensure_dict(market_data.get('provider_status', {}))

    reasons: list[str] = []
    allow_full_analysis = True
    allow_trade_recommendation = True
    decision = 'full'
    output_mode = 'brief'

    resolution_confidence = normalize_confidence(resolved.get('confidence', 'low'))
    score_margin = float(resolved.get('score_margin', 0) or 0)
    filtered_market_count = int(sourcing.get('filtered_market_count', 0) or 0)

    if resolution_confidence == 'low' or not resolved.get('ticker'):
        reasons.append('resolution-weak')
        allow_full_analysis = False
        allow_trade_recommendation = False
        decision = 'clarify'
        output_mode = 'clarify'
    elif resolution_confidence == 'medium' or score_margin < 2:
        reasons.append('resolution-not-clean')
        allow_full_analysis = False
        allow_trade_recommendation = False
        decision = 'partial_only'
        output_mode = 'brief'

    if filtered_market_count > 1:
        reasons.append('resolution-ambiguous-family')
        allow_full_analysis = False
        allow_trade_recommendation = False
        if decision == 'full':
            decision = 'partial_only'

    news_status = (news_context.get('status') or '').lower()
    news_sufficiency = (news_context.get('sufficiency') or '').lower()
    if news_status in {'unavailable', 'error'}:
        reasons.append('fresh-context-missing')
        allow_full_analysis = False
        allow_trade_recommendation = False
        if decision == 'full':
            decision = 'partial_only'
    elif news_sufficiency == 'weak':
        reasons.append('news-context-weak')
        allow_full_analysis = False
        if decision == 'full':
            decision = 'partial_only'

    transcript_status = (transcript_intelligence.get('status') or '').lower()
    if transcript_status in {'empty', 'error'}:
        reasons.append('transcript-support-missing')
        if decision == 'full':
            decision = 'partial_only'

    if provider_status.get('market') != 'ok':
        reasons.append('market-provider-not-ok')
        allow_trade_recommendation = False
        if decision == 'full':
            decision = 'partial_only'

    if decision == 'full' and allow_trade_recommendation:
        output_mode = 'full_memo'
    elif decision == 'partial_only':
        output_mode = 'brief'
    elif decision == 'clarify':
        output_mode = 'clarify'
    elif decision == 'skip':
        output_mode = 'skip'

    overall_confidence = 'high' if decision == 'full' else 'medium' if decision == 'partial_only' else 'low'

    return {
        'query': query,
        'decision': decision,
        'output_mode': output_mode,
        'confidence': overall_confidence,
        'reasons': reasons,
        'allow_full_analysis': allow_full_analysis,
        'allow_trade_recommendation': allow_trade_recommendation,
    }
