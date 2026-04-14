"""Signal vs noise detection for prediction market moves."""
from __future__ import annotations

import logging

from library.utils import get_threshold

log = logging.getLogger('mentions')


def assess_signal(market_retrieval: dict, frame: dict) -> dict:
    """Assess whether a market move is signal or noise.

    Returns::

        {
            'verdict': 'signal' | 'noise' | 'unclear',
            'signal_strength': 'strong' | 'moderate' | 'weak' | 'unknown',
            'note': str,
            'factors': list[str],
        }
    """
    market_data = market_retrieval.get('market_data', {})
    history = market_retrieval.get('history', [])

    if not market_data and not history:
        return {
            'verdict': 'unclear',
            'signal_strength': 'unknown',
            'note': 'Insufficient data to assess signal.',
            'factors': [],
        }

    factors = []
    signal_score = 0.0

    # Price movement magnitude
    price_move = _compute_price_move(history)
    if price_move is not None:
        sig_threshold = get_threshold('price_move_significant_pct', 5.0)
        if abs(price_move) >= sig_threshold * 2:
            signal_score += 2.0
            factors.append(f'Large price move: {price_move:+.1f}%')
        elif abs(price_move) >= sig_threshold:
            signal_score += 1.0
            factors.append(f'Moderate price move: {price_move:+.1f}%')
        else:
            factors.append(f'Small price move: {price_move:+.1f}%')

    # Volume relative to baseline
    if isinstance(market_data, dict):
        volume = market_data.get('volume', 0)
        open_interest = market_data.get('open_interest', 0)
        if volume and open_interest:
            try:
                ratio = float(volume) / float(open_interest)
                vol_mult = get_threshold('volume_spike_multiplier', 2.0)
                if ratio > vol_mult:
                    signal_score += 1.5
                    factors.append(f'Volume spike: {ratio:.1f}x open interest')
                elif ratio > 0.5:
                    signal_score += 0.5
                    factors.append(f'Normal volume: {ratio:.1f}x open interest')
            except (ValueError, ZeroDivisionError):
                pass

    # Route context — breaking-news and macro routes boost signal confidence
    route = frame.get('route', '')
    if route in ('breaking-news', 'macro', 'context-research'):
        signal_score += 0.5
        factors.append(f'High-signal route: {route}')

    # Classify
    noise_threshold = get_threshold('signal_noise_threshold', 0.4)
    if signal_score >= 3.0:
        verdict, strength = 'signal', 'strong'
    elif signal_score >= 1.5:
        verdict, strength = 'signal', 'moderate'
    elif signal_score >= noise_threshold:
        verdict, strength = 'signal', 'weak'
    elif signal_score > 0:
        verdict, strength = 'noise', 'weak'
    else:
        verdict, strength = 'unclear', 'unknown'

    note = _build_note(verdict, strength, factors)

    return {
        'verdict': verdict,
        'signal_strength': strength,
        'note': note,
        'factors': factors,
        'score': round(signal_score, 2),
    }


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
