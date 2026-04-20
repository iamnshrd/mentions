"""Experimental evaluation notes for transcript-family retrieval quality.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations

from agents.mentions.services.transcripts.semantic_retrieval.family_taxonomy import TRANSCRIPT_FAMILY_TAXONOMY_V0


FAMILY_EVALUATION_V0 = {
    'war_geopolitics': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['war_geopolitics']['mode'],
        'quality': 'strong',
        'confidence': 'high',
        'status': 'usable',
        'notes': 'Semantic retrieval already finds coherent Iran/war/national-security windows.',
        'next_action': 'Integrate into experimental transcript family path with minimal extra filtering.',
    },
    'tariff_policy_legal': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['tariff_policy_legal']['mode'],
        'quality': 'medium',
        'confidence': 'medium',
        'status': 'promising',
        'notes': 'Semantic retrieval finds tariff/legal-policy windows, but still leaks into broader rhetorical regime language.',
        'next_action': 'Tighten with title priors and light lexical filtering around tariffs, legal process, and formal policy framing.',
    },
    'trade_industry_manufacturing': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['trade_industry_manufacturing']['mode'],
        'quality': 'medium',
        'confidence': 'medium',
        'status': 'promising',
        'notes': 'Semantic retrieval finds trade/manufacturing windows, but still overlaps with broad economy and boast language.',
        'next_action': 'Separate industry/manufacturing prompts from generic economy bragging and keep as regime-embedded rather than pure direct-core.',
    },
    'healthcare_drug_pricing': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['healthcare_drug_pricing']['mode'],
        'quality': 'medium',
        'confidence': 'medium',
        'status': 'promising',
        'notes': 'Cluster discovery suggests a strong family, but direct family-level inspection still needs more passes.',
        'next_action': 'Run targeted inspection and calibrate prompts against healthcare/drug transcripts.',
    },
    'border_immigration': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['border_immigration']['mode'],
        'quality': 'medium',
        'confidence': 'medium',
        'status': 'promising',
        'notes': 'Corpus clustering suggests a real border/security family, but retrieval quality still needs validation.',
        'next_action': 'Run targeted family inspection and add border/immigration lexical gates if needed.',
    },
    'energy_industry_manufacturing': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['energy_industry_manufacturing']['mode'],
        'quality': 'medium',
        'confidence': 'low',
        'status': 'mixed',
        'notes': 'Family appears in clustering, but overlaps strongly with tariffs/economy and is not yet cleanly separated.',
        'next_action': 'Separate energy/industry prompts from general tariff/economy rhetoric.',
    },
    'broad_economy_prices': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['broad_economy_prices']['mode'],
        'quality': 'medium',
        'confidence': 'low',
        'status': 'mixed',
        'notes': 'Very broad family, useful as spillover context but easy to overgeneralize.',
        'next_action': 'Keep as secondary family rather than primary retrieval family for now.',
    },
    'gop_coalition_internal': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['gop_coalition_internal']['mode'],
        'quality': 'medium',
        'confidence': 'low',
        'status': 'mixed',
        'notes': 'Real rhetorical regime, but often overlaps with election boasting and internal politics chatter.',
        'next_action': 'Use mostly for event-regime labeling, not direct strike-family mapping.',
    },
    'agriculture_farmers': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['agriculture_farmers']['mode'],
        'quality': 'medium',
        'confidence': 'low',
        'status': 'mixed',
        'notes': 'Shows up in cluster discovery, but still entangled with tariff/economy themes.',
        'next_action': 'Inspect farmer-specific transcripts and tighten agricultural prompts.',
    },
    'opponents_media_attacks': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['opponents_media_attacks']['mode'],
        'quality': 'medium',
        'confidence': 'low',
        'status': 'mixed',
        'notes': 'Likely real family, but currently too entangled with election/boasting rhetoric.',
        'next_action': 'Decide whether to keep as standalone family or fold into political spillover logic.',
    },
    'sports_education_institutions': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['sports_education_institutions']['mode'],
        'quality': 'medium',
        'confidence': 'medium',
        'status': 'usable',
        'notes': 'Clustered cleanly enough as a distinct event family around college sports and institutional survival.',
        'next_action': 'Keep as semantic-native and validate on non-Trump event cases later.',
    },
    'labor_service_workers': {
        'mode': TRANSCRIPT_FAMILY_TAXONOMY_V0['labor_service_workers']['mode'],
        'quality': 'weak',
        'confidence': 'high',
        'status': 'not_ready',
        'notes': 'Does not emerge well from unsupervised clustering and still retrieves broad tax/economy chatter unless heavily guided.',
        'next_action': 'Keep prompt-guided; use targeted event/title priors and phrase anchoring rather than broad semantic retrieval.',
    },
}
