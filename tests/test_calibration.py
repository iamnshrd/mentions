"""Tests for calibration metrics added to the eval harness."""
from __future__ import annotations

import math

import pytest

from library._core.eval.harness import (
    _brier_score, _log_loss, _reliability_bins, _ece, run_eval,
)


# ── Unit math ──────────────────────────────────────────────────────────────

class TestBrier:
    def test_empty_zero(self):
        assert _brier_score([]) == 0.0

    def test_perfect(self):
        # Confidence matches outcome exactly.
        preds = [(1.0, 1), (0.0, 0), (1.0, 1)]
        assert _brier_score(preds) == 0.0

    def test_worst(self):
        # Fully confident and fully wrong every time.
        preds = [(1.0, 0), (0.0, 1)]
        assert _brier_score(preds) == 1.0

    def test_uninformative(self):
        # Always 0.5; outcomes 50/50. Brier = 0.25.
        preds = [(0.5, 1), (0.5, 0)]
        assert _brier_score(preds) == 0.25


class TestLogLoss:
    def test_empty_zero(self):
        assert _log_loss([]) == 0.0

    def test_perfect_near_zero(self):
        # Close to perfect — log loss approaches 0.
        preds = [(1 - 1e-12, 1), (1e-12, 0)]
        assert _log_loss(preds) < 1e-6

    def test_uninformative_ln2(self):
        preds = [(0.5, 1), (0.5, 0)]
        assert abs(_log_loss(preds) - math.log(2)) < 1e-9

    def test_clamp_handles_extremes(self):
        # Confident & wrong: loss stays finite thanks to eps clamp.
        preds = [(1.0, 0)]
        assert math.isfinite(_log_loss(preds))


class TestReliabilityBins:
    def test_empty(self):
        assert _reliability_bins([], n_bins=10) == []

    def test_bin_shape(self):
        bins = _reliability_bins([(0.05, 1), (0.15, 0)], n_bins=10)
        assert len(bins) == 10
        first = bins[0]
        assert first['lo'] == 0.0 and first['hi'] == 0.1
        assert first['count'] == 1
        assert first['mean_confidence'] == 0.05
        assert first['accuracy'] == 1.0

    def test_top_bin_catches_one(self):
        bins = _reliability_bins([(1.0, 1)], n_bins=10)
        last = bins[-1]
        assert last['count'] == 1
        assert last['accuracy'] == 1.0

    def test_empty_bins_carry_nulls(self):
        bins = _reliability_bins([(0.05, 1)], n_bins=10)
        assert bins[5]['count'] == 0
        assert bins[5]['accuracy'] is None
        assert bins[5]['mean_confidence'] is None


class TestECE:
    def test_perfectly_calibrated_zero(self):
        # One bin, accuracy == confidence.
        bins = [{'lo': 0.0, 'hi': 1.0, 'count': 10,
                 'mean_confidence': 0.7, 'accuracy': 0.7}]
        assert _ece(bins) == 0.0

    def test_max_gap(self):
        bins = [{'lo': 0.0, 'hi': 1.0, 'count': 10,
                 'mean_confidence': 1.0, 'accuracy': 0.0}]
        assert _ece(bins) == 1.0

    def test_weighted_by_count(self):
        bins = [
            {'lo': 0, 'hi': .5, 'count': 9,  'mean_confidence': 0.5, 'accuracy': 0.5},
            {'lo': .5, 'hi': 1, 'count': 1,  'mean_confidence': 1.0, 'accuracy': 0.0},
        ]
        # Only 1/10 contribute a gap of 1.0 → ECE = 0.1.
        assert abs(_ece(bins) - 0.1) < 1e-9

    def test_empty_zero(self):
        assert _ece([]) == 0.0


# ── Integration with run_eval ──────────────────────────────────────────────

class TestRunEvalCalibration:
    def test_report_contains_calibration(self):
        queries = [{
            'id': 'q1', 'query': 'powell speech',
            'expected_intent': 'speaker_lookup',
            'expected_route':  'speaker-history',
        }]
        report = run_eval(queries=queries)
        cal = report['calibration']
        assert cal['n'] == 1
        assert 'brier' in cal and 'log_loss' in cal and 'ece' in cal
        assert len(cal['bins']) == 10

    def test_calibration_skips_queries_without_gold(self):
        queries = [
            {'id': 'q1', 'query': 'powell speech',
             'expected_intent': 'speaker_lookup'},
            # No expected_intent — skipped from calibration tally.
            {'id': 'q2', 'query': 'random'},
        ]
        report = run_eval(queries=queries)
        assert report['calibration']['n'] == 1
