"""Pure hedge / contradiction detection helpers.

This module owns the reusable conflict-classification rules. It
deliberately excludes database reads so callers can apply the same
logic to historical rows, backtests, or in-memory prior decisions.
"""
from __future__ import annotations


def ticker_prefix(ticker: str) -> str:
    """Return the event stem of a Kalshi-style ticker."""
    value = (ticker or '').strip().upper()
    if not value:
        return ''
    if '-' not in value:
        return value
    return value.rsplit('-', 1)[0]


def ticker_outcome(ticker: str) -> str:
    """Return the outcome suffix of a Kalshi-style ticker."""
    value = (ticker or '').strip().upper()
    if not value or '-' not in value:
        return ''
    return value.rsplit('-', 1)[1]


def detect_hedge_conflicts(
    current_ticker: str,
    current_decision: str,
    priors: list[dict],
) -> list[dict]:
    """Classify prior decisions as contradictions or stacked outcomes."""
    current_ticker = (current_ticker or '').upper()
    current_decision = (current_decision or '').upper()
    current_outcome = ticker_outcome(current_ticker)
    conflicts: list[dict] = []
    for prior in priors:
        prior_ticker = (prior.get('market_ticker') or '').upper()
        prior_decision = (prior.get('decision') or '').upper()
        if not prior_ticker or not prior_decision:
            continue
        if prior_ticker == current_ticker:
            if prior_decision != current_decision and prior_decision in {'YES', 'NO'}:
                conflicts.append({
                    'type': 'contradiction',
                    'prior': prior,
                    'note': (
                        f'Prior decision {prior_decision} on {prior_ticker} '
                        f'conflicts with proposed {current_decision}.'
                    ),
                })
            continue
        if ticker_outcome(prior_ticker) == current_outcome:
            continue
        if prior_decision == current_decision == 'YES':
            conflicts.append({
                'type': 'stacked_yes',
                'prior': prior,
                'note': (
                    f'YES on {prior_ticker} and proposed YES on '
                    f'{current_ticker} are sibling outcomes — '
                    f'at most one can resolve YES.'
                ),
            })
        elif prior_decision == current_decision == 'NO':
            conflicts.append({
                'type': 'stacked_no',
                'prior': prior,
                'note': (
                    f'NO on {prior_ticker} and proposed NO on '
                    f'{current_ticker} are sibling outcomes — '
                    f'under an exhaustive outcome set this '
                    f'implies no resolution path.'
                ),
            })
    return conflicts
