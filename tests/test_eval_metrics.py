"""Tests for the extended calibration + profit-sim metrics (v0.13)."""
from __future__ import annotations

import math

import pytest

from agents.mentions.eval.harness import (
    _auc_roc, _profit_sim, _reliability_bins, _resolution, _sharpness,
)


# ── Resolution ─────────────────────────────────────────────────────────────

class TestResolution:
    def test_empty_bins(self):
        assert _resolution([], 0.5) == 0.0

    def test_perfectly_split_bins(self):
        # Two bins at 0/1 with base rate 0.5 → max resolution = 0.25.
        bins = [
            {'count': 10, 'accuracy': 0.0, 'mean_confidence': 0.1},
            {'count': 10, 'accuracy': 1.0, 'mean_confidence': 0.9},
        ]
        res = _resolution(bins, 0.5)
        assert res == pytest.approx(0.25, abs=1e-9)

    def test_all_at_base_rate_is_zero(self):
        bins = [
            {'count': 10, 'accuracy': 0.5, 'mean_confidence': 0.5},
            {'count': 10, 'accuracy': 0.5, 'mean_confidence': 0.5},
        ]
        assert _resolution(bins, 0.5) == 0.0


# ── Sharpness ──────────────────────────────────────────────────────────────

class TestSharpness:
    def test_hedging_is_zero(self):
        preds = [(0.5, 0), (0.5, 1), (0.5, 0)]
        assert _sharpness(preds) == 0.0

    def test_extreme_predictions_half(self):
        preds = [(0.0, 0), (1.0, 1)]
        assert _sharpness(preds) == pytest.approx(0.5, abs=1e-9)

    def test_empty_is_zero(self):
        assert _sharpness([]) == 0.0


# ── AUC-ROC ────────────────────────────────────────────────────────────────

class TestAUC:
    def test_perfect_separation(self):
        preds = [(0.1, 0), (0.2, 0), (0.8, 1), (0.9, 1)]
        assert _auc_roc(preds) == pytest.approx(1.0, abs=1e-9)

    def test_perfectly_wrong(self):
        preds = [(0.9, 0), (0.8, 0), (0.2, 1), (0.1, 1)]
        assert _auc_roc(preds) == pytest.approx(0.0, abs=1e-9)

    def test_all_tied_is_half(self):
        preds = [(0.5, 0), (0.5, 1), (0.5, 0), (0.5, 1)]
        assert _auc_roc(preds) == pytest.approx(0.5, abs=1e-9)

    def test_one_class_missing(self):
        preds = [(0.3, 1), (0.6, 1)]
        assert _auc_roc(preds) == 0.5

    def test_monotone_in_quality(self):
        easy  = [(0.1, 0), (0.9, 1)]
        mixed = [(0.4, 0), (0.6, 1)]
        assert _auc_roc(easy) >= _auc_roc(mixed)


# ── Profit simulation ─────────────────────────────────────────────────────

class TestProfitSim:
    def test_empty_rows(self):
        out = _profit_sim([])
        assert out['n'] == 0
        assert out['pnl'] == 0.0

    def test_no_edge_no_bets(self):
        rows = [{'p': 0.5, 'q': 0.5, 'y': 1}] * 5
        out = _profit_sim(rows)
        assert out['n_bet'] == 0
        assert out['pnl'] == 0.0

    def test_positive_edge_winning_bet_grows_bankroll(self):
        # p=0.7, q=0.5 → strong YES edge; y=1 → win.
        rows = [{'p': 0.7, 'q': 0.5, 'y': 1}]
        out = _profit_sim(rows, fractional=0.25, cap=0.25)
        assert out['n_bet'] == 1
        assert out['wins'] == 1
        assert out['pnl'] > 0

    def test_positive_edge_losing_bet_shrinks_bankroll(self):
        rows = [{'p': 0.7, 'q': 0.5, 'y': 0}]
        out = _profit_sim(rows, fractional=0.25, cap=0.25)
        assert out['wins'] == 0
        assert out['losses'] == 1
        assert out['pnl'] < 0

    def test_roi_is_pnl_over_bankroll(self):
        rows = [{'p': 0.7, 'q': 0.5, 'y': 1}]
        out = _profit_sim(rows, bankroll=100.0)
        assert out['roi'] == pytest.approx(out['pnl'] / 100.0, abs=1e-6)

    def test_edge_but_negative_direction_skips(self):
        # p < q → no YES bet → no trade.
        rows = [{'p': 0.3, 'q': 0.6, 'y': 0}]
        out = _profit_sim(rows)
        assert out['n_bet'] == 0


# ── Integration with report ───────────────────────────────────────────────

class TestRunEvalReport:
    def test_report_carries_new_fields(self, tmp_workspace, tmp_db):
        """Harness must include resolution/sharpness/auc_roc in calibration."""
        from agents.mentions.eval.harness import run_eval

        tiny_queries = [
            {'id': 'a', 'query': 'what is BTC doing?',
             'expected_intent': 'market_analysis'},
            {'id': 'b', 'query': 'Powell speech on rates',
             'expected_intent': 'speaker_lookup'},
        ]
        r = run_eval(queries=tiny_queries)
        cal = r['calibration']
        for k in ('resolution', 'sharpness', 'auc_roc', 'base_rate'):
            assert k in cal
        # profit_sim only present if any row had p/q/y in gold.
        assert 'profit_sim' in r

    def test_profit_sim_active_when_gold_has_prices(self, tmp_workspace, tmp_db):
        from agents.mentions.eval.harness import run_eval

        queries = [
            {'id': 'a', 'query': 'Powell speaks tomorrow',
             'expected_intent': 'speaker_lookup',
             'market_price': 0.4,
             'expected_outcome': 1},
        ]
        r = run_eval(queries=queries)
        # Whether or not the intent matched, profit_sim dict should exist.
        assert r['profit_sim'] is not None
        assert r['profit_sim']['n'] == 1
