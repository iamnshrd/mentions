from __future__ import annotations

from mentions_domain.normalize import ensure_dict, ensure_list


DEFAULT_ALTERNATIVES = [
    'market move is mostly noise / liquidity artifact',
    'topic relevance is being over-inferred from generic speaker context',
    'historical analog is mismatched to current format or phase',
]


def build_challenge_block(market_prior: dict, text_evidence_assessment: dict, posterior_update: dict, workflow_policy: dict, news_context: dict, transcript_intelligence: dict) -> dict:
    market_prior = ensure_dict(market_prior)
    text_evidence_assessment = ensure_dict(text_evidence_assessment)
    posterior_update = ensure_dict(posterior_update)
    workflow_policy = ensure_dict(workflow_policy)
    news_context = ensure_dict(news_context)
    transcript_intelligence = ensure_dict(transcript_intelligence)

    return {
        'alternative_hypotheses': _alternatives(market_prior, text_evidence_assessment, workflow_policy),
        'key_assumption': _key_assumption(text_evidence_assessment, workflow_policy),
        'disconfirming_indicator': _disconfirming_indicator(news_context, transcript_intelligence, posterior_update),
        'missing_evidence': _missing_evidence(news_context, transcript_intelligence),
        'what_changes_view': _what_changes_view(workflow_policy, text_evidence_assessment),
    }


def _alternatives(market_prior: dict, text_evidence_assessment: dict, workflow_policy: dict) -> list[str]:
    alternatives = list(DEFAULT_ALTERNATIVES)
    regime = market_prior.get('market_regime', '')
    if regime == 'thin_noisy_market':
        alternatives.insert(0, 'thin market microstructure is distorting the apparent signal')
    if workflow_policy.get('decision') == 'partial_only':
        alternatives.append('fresh context gap means the current read may be structurally incomplete')
    if text_evidence_assessment.get('source_reliability') == 'low':
        alternatives.append('weak sourcing means the posterior update may be overstating conviction')
    return alternatives[:5]


def _key_assumption(text_evidence_assessment: dict, workflow_policy: dict) -> str:
    if workflow_policy.get('decision') == 'partial_only':
        return 'missing fresh context would not materially reverse the current directional read'
    if text_evidence_assessment.get('source_reliability') == 'low':
        return 'historical analogs are still informative despite weak live confirmation'
    return 'retrieved text evidence is aligned with the actual settlement-triggering context'


def _disconfirming_indicator(news_context: dict, transcript_intelligence: dict, posterior_update: dict) -> str:
    if posterior_update.get('suggested_posterior') is None:
        return 'a live priced market with contradicting fresh reporting would invalidate the current update path'
    if not ensure_list(news_context.get('news', [])):
        return 'credible fresh reporting that the speaker focus shifted away from the topic would weaken the thesis'
    if not ensure_list(transcript_intelligence.get('chunks', [])):
        return 'verbatim transcript evidence omitting the topic in the relevant format would disconfirm the setup'
    return 'new primary-source text contradicting the current topical expectation would reduce confidence'


def _missing_evidence(news_context: dict, transcript_intelligence: dict) -> list[str]:
    missing = []
    if not ensure_list(news_context.get('news', [])):
        missing.append('fresh event-specific news evidence')
    if not ensure_list(transcript_intelligence.get('chunks', [])):
        missing.append('speaker- or format-matched transcript evidence')
    return missing[:4]


def _what_changes_view(workflow_policy: dict, text_evidence_assessment: dict) -> str:
    if workflow_policy.get('decision') == 'clarify':
        return 'cleaner contract linkage or a confirmed exact market/event mapping'
    if text_evidence_assessment.get('text_signal_strength') in ('none', 'weak'):
        return 'fresh high-quality text evidence in the relevant event window'
    return 'credible disconfirming text or a strong market repricing against the current read'
