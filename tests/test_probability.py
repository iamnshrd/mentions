"""Tests for the probability primitives."""
from __future__ import annotations

import math

import pytest

from library._core.analysis.probability import (
    clamp01, combine_independent, kelly_fraction, label_from_p,
    logit, p_from_label, sigmoid,
)


class TestClamp:
    def test_in_range_passthrough(self):
        assert clamp01(0.3) == 0.3

    def test_below_zero_clips(self):
        assert clamp01(-0.5) == 0.0

    def test_above_one_clips(self):
        assert clamp01(1.7) == 1.0

    def test_nan_returns_default(self):
        assert clamp01(float('nan')) == 0.5
        assert clamp01(float('nan'), default=0.3) == 0.3

    def test_non_numeric_returns_default(self):
        assert clamp01('foo') == 0.5
        assert clamp01(None) == 0.5


class TestLabelMapping:
    @pytest.mark.parametrize('p,expected', [
        (0.0, 'low'),
        (0.2, 'low'),
        (0.34, 'low'),
        (0.35, 'medium'),
        (0.5, 'medium'),
        (0.64, 'medium'),
        (0.65, 'high'),
        (0.9, 'high'),
    ])
    def test_label_from_p_buckets(self, p, expected):
        assert label_from_p(p) == expected

    def test_p_from_label_midpoints(self):
        assert p_from_label('low')    == 0.25
        assert p_from_label('medium') == 0.50
        assert p_from_label('high')   == 0.75
        assert p_from_label('')       == 0.50
        assert p_from_label('garbage') == 0.50


class TestLogitSigmoid:
    def test_round_trip(self):
        for p in (0.1, 0.3, 0.5, 0.7, 0.9):
            assert sigmoid(logit(p)) == pytest.approx(p, abs=1e-9)

    def test_logit_of_half_is_zero(self):
        assert logit(0.5) == pytest.approx(0.0, abs=1e-9)

    def test_extremes_clamped(self):
        # logit(0) and logit(1) should not blow up.
        assert math.isfinite(logit(0.0))
        assert math.isfinite(logit(1.0))


class TestCombineIndependent:
    def test_neutral_factor_no_change(self):
        assert combine_independent(0.3, [0.5]) == pytest.approx(0.3, abs=1e-9)

    def test_supporting_factor_raises(self):
        p = combine_independent(0.5, [0.7])
        assert 0.5 < p < 1.0

    def test_opposing_factor_lowers(self):
        p = combine_independent(0.5, [0.3])
        assert 0.0 < p < 0.5

    def test_two_supporting_compound(self):
        one = combine_independent(0.5, [0.7])
        two = combine_independent(0.5, [0.7, 0.7])
        assert two > one

    def test_symmetric_around_half(self):
        up   = combine_independent(0.5, [0.8])
        down = combine_independent(0.5, [0.2])
        assert up + down == pytest.approx(1.0, abs=1e-9)

    def test_always_in_unit_interval(self):
        for factors in ([0.9]*10, [0.1]*10, [0.5]*100):
            p = combine_independent(0.5, factors)
            assert 0.0 <= p <= 1.0


class TestKelly:
    def test_no_edge_returns_zero(self):
        assert kelly_fraction(p=0.5, q=0.5) == 0.0
        assert kelly_fraction(p=0.4, q=0.5) == 0.0

    def test_positive_edge_scaled_by_fractional(self):
        # full = (0.6 - 0.5) / (0.5 * 0.5) = 0.4
        full_bank = kelly_fraction(p=0.6, q=0.5, fractional=1.0, cap=1.0)
        assert full_bank == pytest.approx(0.4, abs=1e-9)
        quarter = kelly_fraction(p=0.6, q=0.5, fractional=0.25, cap=1.0)
        assert quarter == pytest.approx(0.1, abs=1e-9)

    def test_cap_applies(self):
        # Would be 0.4, capped at 0.25.
        out = kelly_fraction(p=0.6, q=0.5, fractional=1.0, cap=0.25)
        assert out == 0.25

    def test_extreme_q_returns_zero(self):
        # Market at 99.99¢ — no room for Kelly.
        assert kelly_fraction(p=0.999, q=0.9999) == 0.0
        assert kelly_fraction(p=0.001, q=0.0001) == 0.0

    def test_output_in_unit_interval(self):
        for p in (0.1, 0.5, 0.9):
            for q in (0.1, 0.5, 0.9):
                out = kelly_fraction(p=p, q=q)
                assert 0.0 <= out <= 1.0
