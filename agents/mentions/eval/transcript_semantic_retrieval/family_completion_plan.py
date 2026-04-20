"""Experimental planning notes for transcript-family completion work.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations


FAMILY_COMPLETION_PLAN_V0 = {
    'war_geopolitics': {
        'status': 'working',
        'expression': 'direct_core',
        'problem': 'Already the strongest ML family, but still needs broader validation on more cases.',
        'next_action': 'Keep as benchmark family and use it to calibrate what true direct-core quality should look like.',
    },
    'tariff_policy_legal': {
        'status': 'partial',
        'expression': 'regime_embedded',
        'problem': 'Still retrieves too much brag/political noise and lacks enough clean legal-tariff core windows.',
        'next_action': 'Build better positive anchors for tariff authority / court / import-duty language and validate on tariff-heavy transcripts.',
    },
    'trade_industry_manufacturing': {
        'status': 'partial',
        'expression': 'regime_embedded',
        'problem': 'Still drifts into broad economy or industrial-adjacent rhetoric instead of clean factory/manufacturing core.',
        'next_action': 'Tighten manufacturing core anchors and test against true factory/plant/manufacturing transcripts.',
    },
    'labor_service_workers': {
        'status': 'weak',
        'expression': 'regime_embedded',
        'problem': 'Does not yet emerge strongly as a stable family and still needs prompt-guided handling.',
        'next_action': 'Treat as hybrid/prompt-guided family and build better service-worker/tips-specific anchors.',
    },
    'broad_economy_prices': {
        'status': 'weak',
        'expression': 'regime_embedded',
        'problem': 'Too broad, too easy to overgeneralize, and likely better used as regime context than direct family evidence.',
        'next_action': 'Define it explicitly as regime-layer support instead of trying to force it into direct-core retrieval.',
    },
    'energy_industry_manufacturing': {
        'status': 'weak',
        'expression': 'regime_embedded',
        'problem': 'Still entangled with trade/manufacturing and not cleanly separated as an independent family.',
        'next_action': 'Separate energy-production anchors from general industrial and tariff rhetoric.',
    },
    'border_immigration': {
        'status': 'taxonomy_only',
        'expression': 'direct_core',
        'problem': 'Looks plausible in taxonomy but has not yet been properly scored and validated on the ML path.',
        'next_action': 'Run dedicated ML passes and define clean border/enforcement anchor terms.',
    },
    'healthcare_drug_pricing': {
        'status': 'taxonomy_only',
        'expression': 'direct_core',
        'problem': 'Seems like a potentially strong direct-core family, but has not yet been tested deeply in the current worker path.',
        'next_action': 'Run dedicated scoring on healthcare/drug transcripts and validate precision.',
    },
    'sports_education_institutions': {
        'status': 'taxonomy_only',
        'expression': 'direct_core',
        'problem': 'Conceptually clear family, but not yet operationalized in the new worker-backed scoring path.',
        'next_action': 'Run focused tests on college sports / NIL / university-governance transcripts.',
    },
    'gop_coalition_internal': {
        'status': 'taxonomy_only',
        'expression': 'regime_embedded',
        'problem': 'Likely real as a rhetorical regime, but not yet expressed cleanly in family scoring.',
        'next_action': 'Define internal-party / conference / member-retreat anchors and test as regime family.',
    },
    'agriculture_farmers': {
        'status': 'taxonomy_only',
        'expression': 'regime_embedded',
        'problem': 'Still mixed with trade/economy language and not yet validated as its own family.',
        'next_action': 'Collect farmer/agriculture-specific transcripts and tighten rural-production anchors.',
    },
    'opponents_media_attacks': {
        'status': 'taxonomy_only',
        'expression': 'regime_embedded',
        'problem': 'Likely real but too mixed with generic grievance and election-brag rhetoric.',
        'next_action': 'Decide whether to keep standalone or fold into broader regime logic; then calibrate anchors.',
    },
}
