"""Canonical posterior and probability domain logic."""

from .probability import (
    clamp01,
    combine_independent,
    kelly_fraction,
    label_from_p,
    logit,
    p_from_label,
    sigmoid,
)
from .time_decay import (
    DEFAULT_HALF_LIFE_DAYS,
    decayed_counts,
    decayed_counts_from_rows,
)
from .heuristic_learn import (
    decayed_counts as decayed_heuristic_counts,
    get_counts as get_heuristic_counts,
    posterior_by_regime,
    posterior_ci,
    posterior_p,
    record_application,
    record_case_outcomes,
    reset_posterior,
    top_confident,
    top_confident_for_regime,
)
from .speaker_learn import (
    decayed_counts as decayed_speaker_counts,
    get_counts as get_speaker_counts,
    posterior_by_stance,
    record_speaker_application,
    reset_posterior as reset_speaker_posterior,
    top_confident_speakers,
)

__all__ = [
    'DEFAULT_HALF_LIFE_DAYS',
    'clamp01',
    'combine_independent',
    'decayed_counts',
    'decayed_counts_from_rows',
    'decayed_heuristic_counts',
    'decayed_speaker_counts',
    'get_heuristic_counts',
    'get_speaker_counts',
    'kelly_fraction',
    'label_from_p',
    'logit',
    'p_from_label',
    'posterior_by_regime',
    'posterior_by_stance',
    'posterior_ci',
    'posterior_p',
    'record_application',
    'record_case_outcomes',
    'record_speaker_application',
    'reset_posterior',
    'reset_speaker_posterior',
    'sigmoid',
    'top_confident',
    'top_confident_for_regime',
    'top_confident_speakers',
]
