"""Experimental rollout notes for transcript-family retrieval.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations

from agents.mentions.eval.transcript_semantic_retrieval.family_evaluation import FAMILY_EVALUATION_V0


FAMILY_ROLLOUT_SHORTLIST_V0 = {
    'enable_in_experimental_path': {
        'families': ['war_geopolitics', 'tariff_policy_legal', 'trade_industry_manufacturing'],
        'reason': 'These families already show useful ML retrieval behavior and outperform the current baseline localizer on representative comparisons.',
    },
    'keep_in_lab': {
        'families': [
            'healthcare_drug_pricing',
            'border_immigration',
            'sports_education_institutions',
            'energy_industry_manufacturing',
            'broad_economy_prices',
            'gop_coalition_internal',
            'agriculture_farmers',
            'opponents_media_attacks',
        ],
        'reason': 'These families look real and in some cases promising, but they still need targeted inspection or cleaner separation before rollout.',
    },
    'needs_calibration': {
        'families': ['labor_service_workers'],
        'reason': 'This family remains weak under broad semantic retrieval and should stay prompt-guided with stronger event/title priors for now.',
    },
}


def build_rollout_view() -> dict:
    return {
        'status': 'ok',
        'shortlist': FAMILY_ROLLOUT_SHORTLIST_V0,
        'evaluation': FAMILY_EVALUATION_V0,
    }
