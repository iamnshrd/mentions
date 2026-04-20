"""Shared analysis-domain helpers.

This package owns reusable, pure analysis logic that should be shared
across Mentions workflows without living in pack-specific adapters.
"""

from .regime import (
    detect_regime,
    detect_regime_tags,
)
from .hedge_check import (
    detect_hedge_conflicts,
    ticker_outcome,
    ticker_prefix,
)
from .evidence_conflict import (
    apply_to_p_signal,
    classify_stance,
    detect_conflict,
)
from .anti_patterns import (
    apply_anti_patterns_to_p_signal,
    build_anti_pattern_warnings,
)

__all__ = [
    'apply_anti_patterns_to_p_signal',
    'apply_to_p_signal',
    'build_anti_pattern_warnings',
    'classify_stance',
    'detect_conflict',
    'detect_hedge_conflicts',
    'detect_regime',
    'detect_regime_tags',
    'ticker_outcome',
    'ticker_prefix',
]
