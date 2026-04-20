"""Experimental planning notes for transcript candidate-sourcing work.

Research/perimeter tooling only, not part of the current main runtime path.
"""
from __future__ import annotations


CANDIDATE_SOURCING_PLAN_V0 = {
    'goal': 'Improve weak families by fixing transcript candidate pool quality before scoring.',
    'why_now': [
        'Several weak families are not failing only at scoring, but earlier at candidate sourcing.',
        'Current ML family path is now strong enough that candidate-pool quality is the main bottleneck for the weakest families.',
    ],
    'families_needing_sourcing_work': {
        'healthcare_drug_pricing': {
            'problem': 'Current speaker-wide candidate pool rarely surfaces drug-pricing or healthcare-cost windows.',
            'needed': ['title-first healthcare terms', 'drug-company title priors', 'healthcare-specific transcript pools'],
        },
        'sports_education_institutions': {
            'problem': 'Current pool does not reliably surface college sports / NIL / university-governance transcripts.',
            'needed': ['sports/NIL title priors', 'event-title filtering', 'education/sports-specific transcript pools'],
        },
        'agriculture_farmers': {
            'problem': 'Current pool is dominated by generic economy/political rhetoric and not farmer-specific material.',
            'needed': ['farmer/agriculture title priors', 'rural-production transcript pools', 'negative filtering vs broad economy'],
        },
    },
    'next_layer_design': {
        'title_first_pool': 'Search transcript/event titles with family-specific anchor terms before semantic scoring.',
        'family_pool_builder': 'Build a per-family candidate transcript shortlist, not one generic speaker-wide pool for all families.',
        'negative_pool_filters': 'Apply family-specific rejection guards before semantic ranking, not only after scoring.',
        'tier_aware_usage': 'Use weak-family sourcing only for families still marked not-ready, without disturbing the already working families.',
    },
    'priority_order': [
        'healthcare_drug_pricing',
        'sports_education_institutions',
        'agriculture_farmers',
    ],
}
