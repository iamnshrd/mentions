"""Probability primitives for the analytical pipeline."""
from __future__ import annotations

import math

__all__ = [
    'clamp01',
    'label_from_p',
    'p_from_label',
    'combine_independent',
    'logit',
    'sigmoid',
    'kelly_fraction',
]

_LOW_HI = 0.35
_MEDIUM_HI = 0.65

_LABEL_TO_P = {
    'low': 0.25,
    'medium': 0.50,
    'high': 0.75,
    'unknown': 0.50,
    '': 0.50,
}


def clamp01(x: float, *, default: float = 0.5) -> float:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def label_from_p(p: float) -> str:
    p = clamp01(p)
    if p < _LOW_HI:
        return 'low'
    if p < _MEDIUM_HI:
        return 'medium'
    return 'high'


def p_from_label(label: str) -> float:
    return _LABEL_TO_P.get((label or '').strip().lower(), 0.5)


def logit(p: float) -> float:
    p = clamp01(p)
    eps = 1e-9
    p = min(1 - eps, max(eps, p))
    return math.log(p / (1 - p))


def sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def combine_independent(prior: float, factors: list[float]) -> float:
    z = logit(prior)
    for f in factors:
        z += logit(f) - logit(0.5)
    return sigmoid(z)


def kelly_fraction(*, p: float, q: float, fractional: float = 0.25, cap: float = 1.0) -> float:
    p = clamp01(p)
    q = clamp01(q)
    if p <= q:
        return 0.0
    if q <= 1e-4 or q >= 1 - 1e-4:
        return 0.0
    raw = (p - q) / (q * (1.0 - q))
    sized = raw * max(0.0, float(fractional))
    return max(0.0, min(float(cap), sized))
