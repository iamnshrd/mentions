from __future__ import annotations

from mentions_domain.normalize import ensure_dict, ensure_list


def _runtime_health_summary(*, transcript_intelligence: dict, news_context: dict) -> dict:
    summary = {}
    transcript_health = ensure_dict(transcript_intelligence).get('runtime_health')
    news_health = ensure_dict(news_context).get('runtime_health')
    if transcript_health:
        summary['transcripts'] = ensure_dict(transcript_health)
    if news_health:
        summary['news'] = ensure_dict(news_health)
    return summary


def build_retrieval_result(*,
    market: dict,
    market_prior: dict,
    transcripts: list,
    transcript_intelligence: dict,
    news: list,
    news_status: str,
    news_context: dict,
    workflow_policy: dict,
    pmt_knowledge: dict,
    selected_pmt_evidence: dict,
    text_evidence_assessment: dict,
    posterior_update: dict,
    challenge_block: dict,
    fused_evidence: dict,
    has_data: bool,
    sources_used: list,
) -> dict:
    runtime_health = _runtime_health_summary(
        transcript_intelligence=transcript_intelligence,
        news_context=news_context,
    )
    return {
        'market': ensure_dict(market),
        'market_prior': ensure_dict(market_prior),
        'transcripts': ensure_list(transcripts),
        'transcript_intelligence': ensure_dict(transcript_intelligence),
        'news': ensure_list(news),
        'news_status': news_status or 'unavailable',
        'news_context': ensure_dict(news_context),
        'workflow_policy': ensure_dict(workflow_policy),
        'pmt_knowledge': ensure_dict(pmt_knowledge),
        'selected_pmt_evidence': ensure_dict(selected_pmt_evidence),
        'text_evidence_assessment': ensure_dict(text_evidence_assessment),
        'posterior_update': ensure_dict(posterior_update),
        'challenge_block': ensure_dict(challenge_block),
        'fused_evidence': ensure_dict(fused_evidence),
        'has_data': bool(has_data),
        'sources_used': ensure_list(sources_used),
        'runtime_health': runtime_health,
    }
