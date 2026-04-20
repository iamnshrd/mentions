"""Speaker-reliability weighting primitives for retrieval."""
from __future__ import annotations

_MIN_APPLICATIONS = 3
_WEIGHT_BASE = 0.5
_WEIGHT_NEUTRAL = 1.0


def speaker_weight(alpha: float | None, beta: float | None, n_apps: int, *, min_apps: int = _MIN_APPLICATIONS) -> float:
    if alpha is None or beta is None or n_apps < min_apps:
        return _WEIGHT_NEUTRAL
    total = float(alpha) + float(beta)
    if total <= 0:
        return _WEIGHT_NEUTRAL
    p = float(alpha) / total
    return _WEIGHT_BASE + p


def apply_weights(hits, weights: dict[str, float]) -> None:
    for h in hits:
        key = (getattr(h, 'speaker_canonical', '') or h.speaker or '')
        w = weights.get(key.strip().lower(), _WEIGHT_NEUTRAL)
        setattr(h, 'score_reliability', w)
        h.score_final *= w
