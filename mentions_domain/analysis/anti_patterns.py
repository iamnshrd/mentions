"""Pure anti-pattern warning projection and scoring helpers."""
from __future__ import annotations

_P_ANTI_PATTERN = 0.42
_P_CROWD_MISTAKE = 0.44
_P_DISPUTE_PATTERN = 0.40


def build_anti_pattern_warnings(
    anti_patterns: list[dict],
    crowd_mistakes: list[dict],
    dispute_patterns: list[dict],
) -> dict:
    """Project structured warning rows into flags and factor weights."""
    flags: list[str] = []
    factor_ps: dict[str, float] = {}

    for row in anti_patterns:
        flags.append(f'Anti-pattern: {row.get("pattern_text", "")[:120]}')
    if anti_patterns:
        factor_ps['anti_pattern'] = _P_ANTI_PATTERN

    for row in crowd_mistakes:
        flags.append(
            f'Crowd mistake: {row.get("mistake_name", "")} — '
            f'{row.get("mistake_type", "")}'
        )
    if crowd_mistakes:
        factor_ps['crowd_mistake'] = _P_CROWD_MISTAKE

    for row in dispute_patterns:
        flags.append(
            f'Dispute risk: {row.get("pattern_name", "")} '
            f'({row.get("dispute_type", "")})'
        )
    if dispute_patterns:
        factor_ps['dispute_pattern'] = _P_DISPUTE_PATTERN

    return {
        'anti_patterns': anti_patterns,
        'crowd_mistakes': crowd_mistakes,
        'dispute_patterns': dispute_patterns,
        'flags': flags,
        'factor_ps': factor_ps,
        'any_triggered': bool(flags),
    }


def apply_anti_patterns_to_p_signal(
    p_signal: float | None,
    warnings: dict,
) -> float | None:
    """Fold anti-pattern factors into an existing p_signal."""
    from mentions_domain.posteriors.probability import clamp01, combine_independent

    if p_signal is None or not warnings.get('factor_ps'):
        return p_signal
    probability = combine_independent(p_signal, list(warnings['factor_ps'].values()))
    return clamp01(probability)
