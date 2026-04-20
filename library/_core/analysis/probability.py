"""Probability primitives for the analytical pipeline.

Pre-v0.13 the analysis modules spoke in coarse labels:
``confidence ∈ {high, medium, low}`` and
``signal_strength ∈ {strong, moderate, weak, unknown}``. The labels
read well in UI text but they hide ~30pp of information and make
calibration impossible — the eval harness measures Brier / ECE on a
probability, so a "medium" answer collapses to a single mid-range
bin and is never calibrated sharply.

This module introduces:

* :func:`label_from_p` — project a probability to the old three-bucket
  ``{low, medium, high}`` label. Used only at the UI/back-compat edge.
* :func:`p_from_label` — the reverse, for legacy callers that still
  hand in a label. Uses the bucket midpoint (so ``medium → 0.5``).
* :func:`combine_independent` — multiply odds of independent factors
  in log-space so the accumulation is numerically stable and
  symmetric around 0.5.
* :func:`clamp01` — standard [0, 1] clip with sane default.
* :func:`kelly_fraction` — fractional-Kelly bet size given subjective
  ``p`` and market-implied price ``q``. Returns 0 when edge ≤ 0, the
  raw Kelly fraction when edge > 0, and caps at ``cap`` to guard
  against over-confidence.

Keep the module dependency-free (just ``math``) so it can be pulled
into any analysis path without import order concerns.
"""
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


# Label thresholds. Tuned to roughly match the v0.12 eval baseline
# where "medium" answers clustered around 0.45 and "high" around 0.7.
_LOW_HI     = 0.35
_MEDIUM_HI  = 0.65

# Midpoints used when a legacy caller hands us a label and asks for p.
_LABEL_TO_P = {
    'low':    0.25,
    'medium': 0.50,
    'high':   0.75,
    'unknown': 0.50,
    '':       0.50,
}


def clamp01(x: float, *, default: float = 0.5) -> float:
    """Clip *x* to [0, 1]; non-finite / non-numeric inputs → *default*."""
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
    """Project *p* to the legacy three-bucket label.

    Thresholds are fixed so the mapping is deterministic across
    callers; if you want a different split, change the bucket here
    rather than in individual consumers.
    """
    p = clamp01(p)
    if p < _LOW_HI:
        return 'low'
    if p < _MEDIUM_HI:
        return 'medium'
    return 'high'


def p_from_label(label: str) -> float:
    """Map a legacy label to its bucket midpoint probability."""
    return _LABEL_TO_P.get((label or '').strip().lower(), 0.5)


# ── Log-odds combinators ──────────────────────────────────────────────────

def logit(p: float) -> float:
    """Standard logit with clamp so p=0 / p=1 don't explode."""
    p = clamp01(p)
    eps = 1e-9
    p = min(1 - eps, max(eps, p))
    return math.log(p / (1 - p))


def sigmoid(z: float) -> float:
    """Inverse of :func:`logit`."""
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def combine_independent(prior: float, factors: list[float]) -> float:
    """Combine a prior with independent factor probabilities in log-odds.

    Each factor in *factors* is itself a probability in [0, 1]. We
    treat factors as Bayesian updates independent of the prior — the
    combined log-odds is the sum of the prior's log-odds plus each
    factor's log-odds offset from 0.5 (since a factor of 0.5 carries
    no information).

    This is symmetric around 0.5 and numerically stable even with
    dozens of weak factors, which is what a factor-sum approach
    ``score += 2.0 ; score += 1.5`` fails at (the absolute weights
    don't compose and the threshold is arbitrary).
    """
    z = logit(prior)
    for f in factors:
        z += logit(f) - logit(0.5)  # logit(0.5) = 0, kept for clarity
    return sigmoid(z)


# ── Sizing ─────────────────────────────────────────────────────────────────

def kelly_fraction(*, p: float, q: float,
                   fractional: float = 0.25,
                   cap: float = 1.0) -> float:
    """Fractional-Kelly bet size for a binary Kalshi-style market.

    Parameters
    ----------
    p:
        Subjective probability of YES resolution, in [0, 1].
    q:
        Market-implied probability (= YES price as a fraction). The
        implied cost of one YES share.
    fractional:
        Scalar applied to raw Kelly. 0.25 = quarter-Kelly, the
        standard defensive setting — full Kelly is provably optimal
        only for known *p*, and our *p* is estimated, so we haircut.
    cap:
        Maximum fraction of bankroll. 1.0 = no cap (use only if
        ``fractional`` is already conservative); typical is 0.25.

    Returns
    -------
    Fraction of bankroll to stake on YES. Zero when *p ≤ q* (no
    edge) or when inputs are degenerate.

    Formula
    -------
    For a bet that pays ``1-q`` on win and loses ``q`` on loss::

        f* = (p*(1-q) - (1-p)*q) / (1-q) / q  (full Kelly)

    which simplifies, after multiplying through, to
    ``(p - q) / (q * (1 - q))``. That's the form below.
    """
    p = clamp01(p)
    q = clamp01(q)
    if p <= q:
        return 0.0
    # Avoid q → 0 or q → 1 blowing up; at extremes the market prices
    # leave no Kelly edge anyway.
    if q <= 1e-4 or q >= 1 - 1e-4:
        return 0.0
    raw = (p - q) / (q * (1.0 - q))
    sized = raw * max(0.0, float(fractional))
    return max(0.0, min(float(cap), sized))
