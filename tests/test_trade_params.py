"""Tests for Kelly-based trade parameter computation (v0.13)."""
from __future__ import annotations

from agents.mentions.services.markets.trade_params import compute_trade_params


def _market(yes_price_cents: float, **extra) -> dict:
    m = {'yes_price': yes_price_cents, 'title': 'Test market', 'rules': ''}
    m.update(extra)
    return m


class TestKellyPath:
    def test_no_edge_returns_zero_size(self):
        """p == q → edge zero → no size."""
        tp = compute_trade_params(
            market_data=_market(50), speaker_tendency={},
            p_yes=0.50,
        )
        assert tp['sizing_multiplier'] == 0.0
        assert tp['sizing_method'] == 'kelly'
        assert 'Skip' in tp['sizing_note']

    def test_positive_edge_returns_positive_size(self):
        tp = compute_trade_params(
            market_data=_market(40),  # market says 40%, we think 60%
            speaker_tendency={},
            p_yes=0.60,
        )
        assert tp['sizing_multiplier'] > 0
        assert tp['p_edge'] > 0
        assert tp['sizing_method'] == 'kelly'

    def test_edge_direction_encoded(self):
        tp = compute_trade_params(
            market_data=_market(70), speaker_tendency={},
            p_yes=0.40,
        )
        # Subjective 0.40 vs market 0.70 → p < q → no YES bet.
        assert tp['sizing_multiplier'] == 0.0
        assert tp['p_edge'] < 0

    def test_sizing_capped(self):
        # Huge implied edge — cap should kick in.
        tp = compute_trade_params(
            market_data=_market(20), speaker_tendency={},
            p_yes=0.95,
        )
        # Default cap = 0.25.
        assert tp['sizing_multiplier'] <= 0.25


class TestLabelFallback:
    def test_label_fallback_uses_midpoint(self):
        # No p_yes → falls back to p_from_label('medium') = 0.5.
        tp = compute_trade_params(
            market_data=_market(30), speaker_tendency={},
            confidence='medium',
        )
        assert tp['sizing_method'] == 'kelly_from_label'
        assert tp['p_yes'] == 0.5
        assert tp['sizing_multiplier'] > 0  # edge 0.5 - 0.3 = 0.2

    def test_low_label_at_expensive_market_skips(self):
        # label=low → p=0.25, market at 70¢ → q=0.70 → no edge.
        tp = compute_trade_params(
            market_data=_market(70), speaker_tendency={},
            confidence='low',
        )
        assert tp['sizing_multiplier'] == 0.0


class TestShapeStable:
    def test_always_returns_expected_keys(self):
        tp = compute_trade_params(
            market_data=_market(50), speaker_tendency={},
            p_yes=0.55,
        )
        for k in ('win_condition', 'difficulty', 'difficulty_factors',
                  'invalidation', 'scaling_out', 'p_yes', 'q_market',
                  'p_edge', 'sizing_multiplier', 'sizing_method',
                  'sizing_note'):
            assert k in tp
