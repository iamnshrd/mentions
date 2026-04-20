"""Tests for the probability-first signal assessor (v0.13)."""
from __future__ import annotations

from agents.mentions.services.analysis.signal import assess_signal


def _retrieval(*, history=None, market=None):
    return {
        'market_data': market or {},
        'history':     history or [],
    }


class TestEmptyInputs:
    def test_no_data_returns_unclear(self):
        r = assess_signal(_retrieval(), frame={})
        assert r['p_signal'] is None
        assert r['verdict'] == 'unclear'
        assert r['signal_strength'] == 'unknown'


class TestProbabilityComputation:
    def test_price_move_pushes_p_up(self):
        hist = [{'yes_price': 0.50}, {'yes_price': 0.65}]  # +30% move
        r = assess_signal(_retrieval(history=hist, market={'ignore': 1}),
                          frame={})
        assert r['p_signal'] is not None
        assert r['p_signal'] > 0.5
        assert 'price_move' in r['factor_ps']

    def test_small_move_pushes_p_down(self):
        hist = [{'yes_price': 0.50}, {'yes_price': 0.505}]  # +1%
        r = assess_signal(_retrieval(history=hist, market={'ignore': 1}),
                          frame={})
        # Prior is 0.45 and a small move contributes p=0.40 — p_signal
        # should stay below the "signal" threshold.
        assert r['p_signal'] < 0.5

    def test_p_in_unit_interval(self):
        hist = [{'yes_price': 0.1}, {'yes_price': 0.95}]
        mkt  = {'volume': 10_000, 'open_interest': 1_000}
        r = assess_signal(_retrieval(history=hist, market=mkt),
                          frame={'route': 'breaking-news'})
        assert 0.0 <= r['p_signal'] <= 1.0

    def test_factor_ps_recorded_for_each_observed_signal(self):
        hist = [{'yes_price': 0.50}, {'yes_price': 0.70}]
        mkt  = {'volume': 50_000, 'open_interest': 10_000}
        r = assess_signal(_retrieval(history=hist, market=mkt),
                          frame={'route': 'macro'})
        assert set(r['factor_ps'].keys()) == {
            'price_move', 'volume_ratio', 'route',
        }


class TestVerdictDerivation:
    def test_verdict_consistent_with_p_signal(self):
        # High p_signal → verdict == 'signal'.
        hist = [{'yes_price': 0.30}, {'yes_price': 0.80}]
        mkt  = {'volume': 100_000, 'open_interest': 10_000}
        r = assess_signal(_retrieval(history=hist, market=mkt),
                          frame={'route': 'breaking-news'})
        assert r['verdict'] == 'signal'
        assert r['signal_strength'] in ('moderate', 'strong')
        # Back-compat field (score) stays present.
        assert 'score' in r


class TestLegacyBackCompat:
    def test_legacy_fields_present(self):
        hist = [{'yes_price': 0.50}, {'yes_price': 0.60}]
        r = assess_signal(_retrieval(history=hist, market={'x': 1}), frame={})
        for k in ('p_signal', 'verdict', 'signal_strength', 'score',
                  'note', 'factors', 'factor_ps'):
            assert k in r
