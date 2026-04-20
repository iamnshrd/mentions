from __future__ import annotations

from agents.mentions.module_contracts import ensure_dict, ensure_list


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
    }
