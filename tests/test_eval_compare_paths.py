"""Tests for run_eval(compare_paths=True) — v0.13.

The comparison pass re-runs intent classification with a NullClient
(forcing the deterministic rules path) so the harness can report
whether the LLM-augmented classifier actually beats the rules
baseline on the same gold set, per metric.
"""
from __future__ import annotations

import json

from agents.mentions.eval.harness import (
    _calibration_summary, _path_comparison_delta,
    _shadow_rules_pass, run_eval,
)
from mentions_domain.llm import LLMResponse


# ── FakeClient (mirrors test_eval_harness) ────────────────────────────────

class FakeClient:
    def __init__(self, responder):
        self.responder = responder
        self.calls: list[dict] = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responder(kwargs.get('user', ''))
        return LLMResponse(text=json.dumps(r) if r else '')

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responder(kwargs.get('user', ''))


def _perfect(user: str) -> dict:
    u = user.lower()
    if 'powell' in u or 'speech' in u:
        return {'intent': 'speaker_lookup', 'route': 'speaker',
                'confidence': 0.95,
                'entities': {'speaker': 'Jerome Powell'}}
    return {'intent': 'market_analysis', 'route': 'general-market',
            'confidence': 0.9, 'entities': {}}


_GOLD = [
    {'id': 'a', 'query': 'What is BTC price doing?',
     'expected_intent': 'market_analysis'},
    {'id': 'b', 'query': 'Powell speech on rate cuts',
     'expected_intent': 'speaker_lookup'},
]


# ── Helpers ────────────────────────────────────────────────────────────────

class TestCalibrationSummary:
    def test_empty_preds(self):
        s = _calibration_summary([])
        assert s['n'] == 0
        assert s['base_rate'] == 0.0
        assert s['brier'] == 0.0
        assert s['auc_roc'] == 0.5

    def test_perfect_preds(self):
        preds = [(0.9, 1), (0.9, 1), (0.1, 0), (0.1, 0)]
        s = _calibration_summary(preds)
        assert s['n'] == 4
        assert s['auc_roc'] == 1.0
        assert s['brier'] < 0.05

    def test_has_all_expected_keys(self):
        s = _calibration_summary([(0.5, 1)])
        for k in ('n', 'base_rate', 'brier', 'log_loss', 'ece',
                  'resolution', 'sharpness', 'auc_roc', 'bins'):
            assert k in s


class TestDelta:
    def test_positive_delta_when_llm_better(self):
        llm   = {'intent_accuracy': 0.9, 'brier': 0.1, 'auc_roc': 0.85,
                 'log_loss': 0.3, 'ece': 0.05, 'resolution': 0.2,
                 'sharpness': 0.4}
        rules = {'intent_accuracy': 0.7, 'brier': 0.2, 'auc_roc': 0.65,
                 'log_loss': 0.5, 'ece': 0.1,  'resolution': 0.1,
                 'sharpness': 0.3}
        d = _path_comparison_delta(llm, rules)
        assert d['intent_accuracy'] > 0
        assert d['auc_roc'] > 0
        # For error metrics, llm − rules negative means llm improved.
        assert d['brier'] < 0
        assert d['log_loss'] < 0
        assert d['ece'] < 0

    def test_zero_delta_when_identical(self):
        m = {'intent_accuracy': 0.8, 'brier': 0.15, 'log_loss': 0.4,
             'ece': 0.05, 'resolution': 0.1, 'sharpness': 0.3,
             'auc_roc': 0.75}
        d = _path_comparison_delta(m, m)
        assert all(v == 0.0 for v in d.values())

    def test_missing_keys_default_to_zero(self):
        # Edge: one side lacks a metric — shouldn't crash.
        d = _path_comparison_delta({'intent_accuracy': 0.9}, {})
        assert d['intent_accuracy'] == 0.9
        assert d['brier'] == 0.0


# ── Shadow pass ───────────────────────────────────────────────────────────

class TestShadowRulesPass:
    def test_skips_queries_without_gold(self):
        s = _shadow_rules_pass([{'id': 'x', 'query': 'anything'}])
        # No gold intents → 0 preds counted.
        assert s['n'] == 0

    def test_counts_gold_queries(self):
        s = _shadow_rules_pass(_GOLD)
        # Both queries have a gold intent → n == 2.
        assert s['n'] == 2
        assert 'intent_accuracy' in s


# ── run_eval integration ──────────────────────────────────────────────────

class TestRunEvalCompare:
    def test_no_path_comparison_by_default(self):
        r = run_eval(queries=_GOLD, client=FakeClient(_perfect))
        assert 'path_comparison' not in r

    def test_path_comparison_block_present_when_enabled(self):
        r = run_eval(queries=_GOLD, client=FakeClient(_perfect),
                     compare_paths=True)
        pc = r['path_comparison']
        assert 'llm' in pc
        assert 'rules' in pc
        assert 'delta' in pc
        for block in (pc['llm'], pc['rules']):
            for k in ('intent_accuracy', 'brier', 'auc_roc', 'n'):
                assert k in block

    def test_perfect_llm_beats_or_matches_rules(self):
        # With a perfect responder, LLM accuracy must be ≥ rules baseline.
        r = run_eval(queries=_GOLD, client=FakeClient(_perfect),
                     compare_paths=True)
        pc = r['path_comparison']
        assert pc['llm']['intent_accuracy'] >= pc['rules']['intent_accuracy']
        assert pc['delta']['intent_accuracy'] >= 0.0

    def test_broken_llm_loses_to_rules(self):
        def liar(_):
            return {'intent': 'general_chat', 'route': 'general-market',
                    'confidence': 0.99, 'entities': {}}
        r = run_eval(queries=_GOLD, client=FakeClient(liar),
                     compare_paths=True)
        pc = r['path_comparison']
        # LLM is wrong everywhere but claims p=0.99 → worse Brier than rules.
        assert pc['llm']['intent_accuracy'] <= pc['rules']['intent_accuracy']
        assert pc['delta']['brier'] >= 0  # llm − rules error ≥ 0 means llm worse
