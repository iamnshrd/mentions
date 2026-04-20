"""Signal vs noise detection for prediction market moves.

v0.13 rewrite: the old "additive score + threshold" classifier is
replaced with log-odds combination from
:mod:`mentions_domain.posteriors.probability`. Every factor contributes a
probability (not a magic weight), the combinator is symmetric around
0.5, and the final result carries an explicit ``p_signal`` so the
eval harness can calibrate it.

The legacy ``verdict`` / ``signal_strength`` / ``score`` fields are
still present for back-compat with ``synthesize.py``; they are
derived from ``p_signal`` so the two views are guaranteed consistent.
"""
from __future__ import annotations

import logging

from agents.mentions.utils import get_threshold

from mentions_domain.posteriors.probability import (
    clamp01, combine_independent, label_from_p,
)

log = logging.getLogger('mentions')


# ── Factor definitions ─────────────────────────────────────────────────────
#
# Each factor maps an observable to a probability "this looks like
# genuine signal". 0.5 = this observation carries no information.
# Values are rough priors meant to be refined empirically (#3 on the
# improvement backlog — correlate each factor with realised outcomes).

_PRIOR = 0.45  # Bias against "everything is signal"; calibrated later.


def _p_price_move(pct: float | None) -> float | None:
    if pct is None:
        return None
    sig_threshold = get_threshold('price_move_significant_pct', 5.0)
    a = abs(pct)
    if a >= sig_threshold * 2:
        return 0.80          # ≥10pp move — strong prior for signal
    if a >= sig_threshold:
        return 0.65          # ≥5pp move — moderate prior
    return 0.40              # <5pp — weak evidence of signal


def _p_volume_ratio(ratio: float | None) -> float | None:
    if ratio is None:
        return None
    vol_mult = get_threshold('volume_spike_multiplier', 2.0)
    if ratio > vol_mult:
        return 0.75          # spike
    if ratio > 0.5:
        return 0.55          # normal-ish
    return 0.45              # quiet


def _p_route(route: str) -> float | None:
    # Routes that usually front-run a market mover get a mild boost.
    if route in ('breaking-news', 'macro', 'context-research'):
        return 0.60
    return None


# ── Public entry point ────────────────────────────────────────────────────

def assess_signal(market_retrieval: dict, frame: dict) -> dict:
    """Assess whether a market move is signal or noise.

    Returns a dict with both the new probability-first shape and
    the legacy labels so callers mid-migration keep working::

        {
            # new
            'p_signal':   0.0..1.0,
            'factor_ps':  {factor_name: p, ...},

            # legacy (derived)
            'verdict':         'signal' | 'noise' | 'unclear',
            'signal_strength': 'strong' | 'moderate' | 'weak' | 'unknown',
            'score':           float,    # kept for grep compatibility

            'note':    str,
            'factors': list[str],        # human-readable bullets
        }
    """
    market_data = market_retrieval.get('market_data', {})
    history = market_retrieval.get('history', [])

    if not market_data and not history:
        return {
            'p_signal':        None,
            'factor_ps':       {},
            'verdict':         'unclear',
            'signal_strength': 'unknown',
            'score':           0.0,
            'note':            'Insufficient data to assess signal.',
            'factors':         [],
        }

    factor_ps: dict[str, float] = {}
    factors: list[str] = []

    # Price movement magnitude
    price_move = _compute_price_move(history)
    if price_move is not None:
        p = _p_price_move(price_move)
        if p is not None:
            factor_ps['price_move'] = p
            tag = 'Large' if abs(price_move) >= \
                get_threshold('price_move_significant_pct', 5.0) * 2 else (
                'Moderate' if abs(price_move) >=
                get_threshold('price_move_significant_pct', 5.0) else 'Small'
            )
            factors.append(f'{tag} price move: {price_move:+.1f}%')

    # Volume / open interest ratio
    if isinstance(market_data, dict):
        volume = market_data.get('volume', 0)
        open_interest = market_data.get('open_interest', 0)
        if volume and open_interest:
            try:
                ratio = float(volume) / float(open_interest)
                p = _p_volume_ratio(ratio)
                if p is not None:
                    factor_ps['volume_ratio'] = p
                    tag = (
                        'Volume spike' if ratio >
                        get_threshold('volume_spike_multiplier', 2.0)
                        else 'Normal volume'
                    )
                    factors.append(f'{tag}: {ratio:.1f}x open interest')
            except (ValueError, ZeroDivisionError):
                pass

    # Route context
    route = frame.get('route', '')
    p_r = _p_route(route)
    if p_r is not None:
        factor_ps['route'] = p_r
        factors.append(f'High-signal route: {route}')

    # ── Combine ────────────────────────────────────────────────────────────
    p_signal = combine_independent(_PRIOR, list(factor_ps.values()))
    p_signal = clamp01(p_signal)

    # ── Derive legacy labels from p_signal ────────────────────────────────
    verdict, strength = _derive_verdict(p_signal)
    note = _build_note(verdict, strength, factors)

    return {
        'p_signal':        round(p_signal, 4),
        'factor_ps':       {k: round(v, 4) for k, v in factor_ps.items()},
        'verdict':         verdict,
        'signal_strength': strength,
        # Kept for back-compat with consumers that did arithmetic on
        # "score"; it's now the probability on the 0–4-ish legacy scale.
        'score':           round(p_signal * 4.0, 2),
        'note':            note,
        'factors':         factors,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _derive_verdict(p: float) -> tuple[str, str]:
    """Map p_signal → (verdict, signal_strength) for legacy callers."""
    noise_threshold = get_threshold('signal_noise_threshold', 0.40)
    if p >= 0.75:
        return 'signal', 'strong'
    if p >= 0.60:
        return 'signal', 'moderate'
    if p >= 0.50:
        return 'signal', 'weak'
    if p >= noise_threshold:
        return 'noise', 'weak'
    return 'unclear', 'unknown'


def _compute_price_move(history: list) -> float | None:
    """Return percentage change from first to last price in history."""
    prices = []
    for entry in history:
        if isinstance(entry, dict):
            p = entry.get('yes_price', entry.get('price', None))
            if p is not None:
                try:
                    prices.append(float(p))
                except (ValueError, TypeError):
                    pass
    if len(prices) < 2:
        return None
    first, last = prices[0], prices[-1]
    if first == 0:
        return None
    return (last - first) / first * 100


def _build_note(verdict: str, strength: str, factors: list) -> str:
    if verdict == 'signal' and strength == 'strong':
        return 'Multiple factors confirm a genuine move. Worth close attention.'
    if verdict == 'signal' and strength == 'moderate':
        return 'Evidence leans toward signal. Monitor for confirmation.'
    if verdict == 'signal' and strength == 'weak':
        return 'Weak signal — possible early-stage move or thin market noise.'
    if verdict == 'noise':
        return 'Move appears to be noise. Insufficient factors to confirm signal.'
    return 'Insufficient data for clear verdict.'
