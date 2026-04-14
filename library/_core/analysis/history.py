"""Historical pattern matching — compare current market state to past patterns."""
from __future__ import annotations

import logging

log = logging.getLogger('mentions')


def find_historical_patterns(ticker: str, current_price: float,
                              history: list) -> list[dict]:
    """Find historical patterns similar to the current market state.

    Returns a list of pattern dicts::

        {
            'pattern': str,
            'description': str,
            'frequency': int,
            'outcome': str,
        }
    """
    if not history or len(history) < 5:
        return []

    prices = _extract_prices(history)
    if len(prices) < 5:
        return []

    patterns = []

    # Pattern 1: price near all-time high
    high = max(prices)
    if current_price >= high * 0.95:
        patterns.append({
            'pattern': 'near-high',
            'description': f'Price near historical high ({high:.0f}¢)',
            'frequency': 1,
            'outcome': 'uncertain — could consolidate or break higher',
        })

    # Pattern 2: price near all-time low
    low = min(prices)
    if current_price <= low * 1.05:
        patterns.append({
            'pattern': 'near-low',
            'description': f'Price near historical low ({low:.0f}¢)',
            'frequency': 1,
            'outcome': 'uncertain — could be value or continued decline',
        })

    # Pattern 3: rapid reversal (last 3 data points)
    if len(prices) >= 3:
        recent = prices[-3:]
        if recent[0] > recent[1] and recent[1] < recent[2]:
            patterns.append({
                'pattern': 'v-reversal',
                'description': 'V-shaped reversal in recent data',
                'frequency': 1,
                'outcome': 'possible bounce continuation',
            })
        elif recent[0] < recent[1] and recent[1] > recent[2]:
            patterns.append({
                'pattern': 'inverted-v',
                'description': 'Inverted V (peak then decline) in recent data',
                'frequency': 1,
                'outcome': 'possible continued decline',
            })

    return patterns


def compute_base_rate(ticker: str, category: str) -> dict:
    """Compute base rate resolution probability from DB history.

    Returns::

        {
            'yes_rate': float | None,
            'sample_size': int,
            'category': str,
        }
    """
    try:
        from library.db import connect
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT COUNT(*) as total,
                          SUM(CASE WHEN status = 'resolved_yes' THEN 1 ELSE 0 END) as yes_count
                   FROM markets WHERE category = ?''',
                (category,),
            )
            row = cur.fetchone()
            if row and row[0] > 0:
                total, yes = row[0], row[1] or 0
                return {
                    'yes_rate': round(yes / total, 3),
                    'sample_size': total,
                    'category': category,
                }
    except Exception as exc:
        log.debug('Base rate query failed: %s', exc)

    return {'yes_rate': None, 'sample_size': 0, 'category': category}


def _extract_prices(history: list) -> list[float]:
    prices = []
    for entry in history:
        if isinstance(entry, dict):
            p = entry.get('yes_price', entry.get('price', None))
            if p is not None:
                try:
                    prices.append(float(p))
                except (ValueError, TypeError):
                    pass
    return prices
