"""Tests for agents.mentions.eval.harness.

Covers:
  * load_gold_queries validates required fields
  * _prf math (TP/FP/FN)
  * recall@k, MRR@k
  * run_eval with inline gold + FakeClient — intent/route accuracy,
    ticker/speaker PRF, per-query detail shape
  * run_eval with limit
  * Retrieval metrics only computed when retrieve=True and gold has
    expected_doc_ids
  * load_gold_queries against the real eval_queries.json (smoke)
"""
from __future__ import annotations

import json

import pytest

from agents.mentions.eval.harness import (
    _prf,
    _recall_at_k,
    _mrr_at_k,
    load_gold_queries,
    run_eval,
)
from mentions_domain.llm import NullClient, LLMResponse


# ── FakeClient (mirrors test_intent_classifier) ────────────────────────────

class FakeClient:
    def __init__(self, responder):
        """responder: callable taking user-query → dict | None."""
        self.responder = responder
        self.calls: list[dict] = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responder(kwargs.get('user', ''))
        return LLMResponse(text=json.dumps(r) if r else '')

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responder(kwargs.get('user', ''))


# ── Small metric helpers ───────────────────────────────────────────────────

class TestPrf:
    def test_all_tp(self):
        r = _prf(5, 0, 0)
        assert r['precision'] == 1.0
        assert r['recall'] == 1.0
        assert r['f1'] == 1.0

    def test_zero_denominators(self):
        r = _prf(0, 0, 0)
        assert r == {'precision': 0.0, 'recall': 0.0, 'f1': 0.0,
                     'tp': 0, 'fp': 0, 'fn': 0}

    def test_mixed(self):
        # 3 TP, 1 FP, 1 FN → P=0.75, R=0.75, F1=0.75
        r = _prf(3, 1, 1)
        assert r['precision'] == 0.75
        assert r['recall'] == 0.75
        assert r['f1'] == 0.75


class TestRetrievalMetrics:
    def test_recall_at_k(self):
        ranked = [10, 20, 30, 40, 50]
        gold = {20, 50}
        assert _recall_at_k(ranked, gold, 1) == 0.0
        assert _recall_at_k(ranked, gold, 2) == 0.5
        assert _recall_at_k(ranked, gold, 5) == 1.0

    def test_recall_empty_gold(self):
        assert _recall_at_k([1, 2, 3], set(), 3) == 0.0

    def test_mrr_at_k(self):
        ranked = [10, 20, 30, 40]
        assert _mrr_at_k(ranked, {20}, 5) == pytest.approx(0.5)
        assert _mrr_at_k(ranked, {10}, 5) == pytest.approx(1.0)
        assert _mrr_at_k(ranked, {99}, 5) == 0.0


# ── load_gold_queries ──────────────────────────────────────────────────────

class TestLoadGold:
    def test_missing_query_raises(self, tmp_path):
        p = tmp_path / 'bad.json'
        p.write_text(json.dumps([{'id': 'x'}]), encoding='utf-8')
        with pytest.raises(ValueError):
            load_gold_queries(p)

    def test_not_a_list_raises(self, tmp_path):
        p = tmp_path / 'bad.json'
        p.write_text(json.dumps({'a': 1}), encoding='utf-8')
        with pytest.raises(ValueError):
            load_gold_queries(p)

    def test_real_eval_queries_json_loads(self):
        """Smoke: the shipped eval_queries.json is valid."""
        qs = load_gold_queries()
        assert len(qs) >= 10
        assert all('query' in q for q in qs)
        assert all('id' in q for q in qs)


# ── run_eval (no retrieval) ────────────────────────────────────────────────

_INLINE_GOLD = [
    {
        'id': 'a1', 'query': 'why is BTC moving today?',
        'expected_intent': 'market_analysis',
        'expected_route': 'price-movement',
        'expected_entities': {},
    },
    {
        'id': 'a2', 'query': 'what did Powell say',
        'expected_intent': 'speaker_lookup',
        'expected_route': 'speaker-history',
        'expected_entities': {'speaker': 'Powell'},
    },
    {
        'id': 'a3', 'query': 'KXBTCD-25DEC today',
        'expected_intent': 'market_analysis',
        'expected_route': 'price-movement',
        'expected_entities': {'ticker': 'KXBTCD-25DEC'},
    },
]


def _perfect_responder(query: str) -> dict:
    q = query.lower()
    if 'powell' in q:
        return {
            'intent': 'speaker_lookup', 'route': 'speaker-history',
            'confidence': 0.95,
            'entities': {'speaker': 'Powell'},
        }
    if 'kxbtcd' in q:
        return {
            'intent': 'market_analysis', 'route': 'price-movement',
            'confidence': 0.9,
            'entities': {'ticker': 'KXBTCD-25DEC'},
        }
    return {
        'intent': 'market_analysis', 'route': 'price-movement',
        'confidence': 0.9, 'entities': {},
    }


class TestRunEval:
    def test_perfect_run(self):
        r = run_eval(queries=_INLINE_GOLD, client=FakeClient(_perfect_responder))
        assert r['n_queries'] == 3
        assert r['intent_accuracy'] == 1.0
        assert r['route_accuracy'] == 1.0
        assert r['ticker_prf']['f1'] == 1.0
        assert r['speaker_prf']['f1'] == 1.0
        # Per-query shape
        assert len(r['queries']) == 3
        assert r['queries'][0]['actual']['source'] == 'llm'

    def test_wrong_intent_recorded(self):
        def bad(q):
            return {'intent': 'general_chat', 'route': 'general-market',
                    'confidence': 0.6, 'entities': {}}
        r = run_eval(queries=_INLINE_GOLD, client=FakeClient(bad))
        assert r['intent_accuracy'] == 0.0
        # Speaker FN (expected Powell, got nothing) → 1 fn
        assert r['speaker_prf']['fn'] == 1
        assert r['ticker_prf']['fn'] == 1

    def test_spurious_entity_counts_fp(self):
        def extra(q):
            return {'intent': 'market_analysis', 'route': 'price-movement',
                    'confidence': 0.8,
                    'entities': {'ticker': 'FAKE-99'}}
        # Query a1 has no expected ticker; returning one should be FP.
        r = run_eval(queries=_INLINE_GOLD[:1],
                     client=FakeClient(extra))
        assert r['ticker_prf']['fp'] == 1
        assert r['ticker_prf']['tp'] == 0

    def test_null_client_uses_rules(self):
        r = run_eval(queries=_INLINE_GOLD, client=NullClient())
        # All actual sources should be 'rules'.
        sources = {q['actual']['source'] for q in r['queries']}
        assert sources == {'rules'}

    def test_limit_respected(self):
        r = run_eval(queries=_INLINE_GOLD,
                     client=FakeClient(_perfect_responder), limit=2)
        assert r['n_queries'] == 2

    def test_retrieval_disabled_by_default(self):
        r = run_eval(queries=_INLINE_GOLD,
                     client=FakeClient(_perfect_responder))
        assert r['retrieval'] is None

    def test_retrieval_runs_only_with_gold_ids(self, tmp_db):
        """When retrieve=True but no expected_doc_ids, retrieval stays empty."""
        r = run_eval(
            queries=_INLINE_GOLD,
            client=FakeClient(_perfect_responder),
            retrieve=True,
            k_values=(1, 3),
        )
        assert r['retrieval'] is not None
        assert r['retrieval']['n_queries_with_gold'] == 0
        # None of the per-query entries should have retrieval detail
        assert all('retrieval' not in q for q in r['queries'])

    def test_case_insensitive_entity_substring_match(self):
        def lower_case(q):
            # Returns ticker in different case — should still count as TP.
            if 'kxbtcd' in q.lower():
                return {'intent': 'market_analysis',
                        'route': 'price-movement',
                        'confidence': 0.9,
                        'entities': {'ticker': 'kxbtcd-25dec'}}
            return _perfect_responder(q)
        r = run_eval(queries=_INLINE_GOLD,
                     client=FakeClient(lower_case))
        assert r['ticker_prf']['f1'] == 1.0


class TestReportShape:
    def test_stable_keys(self):
        r = run_eval(queries=_INLINE_GOLD[:1],
                     client=FakeClient(_perfect_responder))
        for key in ('timestamp', 'n_queries', 'intent_accuracy',
                    'route_accuracy', 'ticker_prf', 'speaker_prf',
                    'retrieval', 'queries'):
            assert key in r
