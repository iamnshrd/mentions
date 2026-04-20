"""Tests for the in-process metrics collector + JSONL event log."""
from __future__ import annotations

import json
import time

import pytest

from mentions_core.base.obs import (
    MetricsCollector,
    get_collector,
    reset_collector,
    persist_event,
    load_events,
    summarize_events,
)
from mentions_core.base.obs.metrics import _percentile, _tag_key


# ── Unit: helpers ──────────────────────────────────────────────────────────

class TestHelpers:
    def test_tag_key_sorted(self):
        assert _tag_key({'b': 2, 'a': 1}) == 'a=1|b=2'

    def test_tag_key_empty(self):
        assert _tag_key(None) == ''
        assert _tag_key({}) == ''

    def test_percentile_empty(self):
        assert _percentile([], 50) == 0.0

    def test_percentile_basic(self):
        values = sorted([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        assert _percentile(values, 50) == 50
        assert _percentile(values, 95) == 100
        assert _percentile(values, 0) == 10


# ── Unit: collector ────────────────────────────────────────────────────────

class TestCollector:
    def test_counter_accumulates(self):
        c = MetricsCollector()
        c.incr('x')
        c.incr('x', n=3)
        snap = c.snapshot()
        assert snap['counters'] == [{'name': 'x', 'tags': '', 'value': 4}]

    def test_counter_tags_separate(self):
        c = MetricsCollector()
        c.incr('x', tags={'k': 'a'})
        c.incr('x', tags={'k': 'b'})
        c.incr('x', tags={'k': 'a'})
        snap = c.snapshot()
        by_tag = {row['tags']: row['value'] for row in snap['counters']}
        assert by_tag == {'k=a': 2, 'k=b': 1}

    def test_observe_histogram(self):
        c = MetricsCollector()
        for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            c.observe('lat', v)
        snap = c.snapshot()
        h = snap['histograms'][0]
        assert h['name'] == 'lat'
        assert h['count'] == 10
        assert h['min'] == 10.0
        assert h['max'] == 100.0
        assert h['p50'] == 50.0

    def test_timed_records_ms(self):
        c = MetricsCollector()
        with c.timed('block'):
            pass
        snap = c.snapshot()
        h = snap['histograms'][0]
        assert h['name'] == 'block'
        assert h['count'] == 1
        # Timing is in ms; whatever the exact value, it must be non-negative.
        assert h['min'] >= 0

    def test_reset_clears(self):
        c = MetricsCollector()
        c.incr('x')
        c.observe('y', 1.0)
        c.reset()
        snap = c.snapshot()
        assert snap == {'counters': [], 'histograms': []}


# ── Singleton ──────────────────────────────────────────────────────────────

class TestSingleton:
    def test_singleton_identity(self):
        a = get_collector()
        b = get_collector()
        assert a is b

    def test_reset_swaps(self):
        a = get_collector()
        a.incr('keep')
        b = reset_collector()
        assert a is not b
        assert b.snapshot() == {'counters': [], 'histograms': []}


# ── Event log ──────────────────────────────────────────────────────────────

class TestEventLog:
    def test_persist_and_load(self, tmp_path):
        path = tmp_path / 'metrics.jsonl'
        persist_event({'counters': [{'name': 'x', 'tags': '', 'value': 1}],
                       'histograms': [], 'timestamp': 1.0}, path=path)
        persist_event({'counters': [{'name': 'x', 'tags': '', 'value': 2}],
                       'histograms': [], 'timestamp': 2.0}, path=path)
        events = load_events(path=path)
        # newest first
        assert len(events) == 2
        assert events[0]['timestamp'] == 2.0
        assert events[1]['timestamp'] == 1.0

    def test_load_missing_returns_empty(self, tmp_path):
        assert load_events(path=tmp_path / 'nope.jsonl') == []

    def test_load_skips_junk_lines(self, tmp_path):
        path = tmp_path / 'metrics.jsonl'
        with open(path, 'w', encoding='utf-8') as f:
            f.write('{"counters": [], "histograms": []}\n')
            f.write('not json\n')
            f.write('\n')
            f.write('{"counters": [{"name":"x","tags":"","value":3}], "histograms": []}\n')
        events = load_events(path=path)
        assert len(events) == 2

    def test_load_limit(self, tmp_path):
        path = tmp_path / 'metrics.jsonl'
        for i in range(5):
            persist_event({'counters': [], 'histograms': [], 'i': i}, path=path)
        events = load_events(path=path, limit=2)
        assert len(events) == 2

    def test_summarize_events(self):
        evs = [
            {'counters': [{'name': 'x', 'tags': '', 'value': 1}],
             'histograms': [{'name': 'lat', 'tags': '', 'count': 2,
                             'min': 10, 'max': 20, 'mean': 15,
                             'p50': 15, 'p95': 20, 'p99': 20}]},
            {'counters': [{'name': 'x', 'tags': '', 'value': 4}],
             'histograms': [{'name': 'lat', 'tags': '', 'count': 1,
                             'min': 30, 'max': 30, 'mean': 30,
                             'p50': 30, 'p95': 30, 'p99': 30}]},
        ]
        agg = summarize_events(evs)
        assert agg['n_events'] == 2
        counters = {row['name']: row['value'] for row in agg['counters']}
        assert counters['x'] == 5
        hist = agg['histograms'][0]
        assert hist['count'] == 3  # 2 + 1


# ── Hook integration ───────────────────────────────────────────────────────

class TestIntentHooks:
    def test_nullclient_records_rules_fallback(self):
        from mentions_domain.llm import NullClient
        from mentions_domain.intent.classifier import classify_intent

        reset_collector()
        classify_intent('what is btc doing', client=NullClient())
        snap = get_collector().snapshot()
        names = {row['name'] for row in snap['counters']}
        assert 'intent.rules_fallback' in names
        assert 'intent.result' in names

    def test_empty_query_does_not_invoke_llm(self):
        from mentions_domain.intent.classifier import classify_intent

        reset_collector()
        classify_intent('')
        snap = get_collector().snapshot()
        names = {row['name'] for row in snap['counters']}
        # Empty query short-circuits before touching the collector.
        assert 'intent.llm_attempt' not in names


class TestExtractHook:
    def test_nullclient_records_skip(self):
        from mentions_domain.llm import NullClient
        from agents.mentions.services.extraction.pipeline import extract_from_chunk

        reset_collector()
        chunk = {'id': 1, 'document_id': 1, 'text': 'some body text'}
        result = extract_from_chunk(chunk, client=NullClient())
        assert result == {'heuristics': [], 'decision_cases': [],
                          'pricing_signals': []}
        snap = get_collector().snapshot()
        names = {row['name'] for row in snap['counters']}
        assert 'extract.skipped_no_llm' in names


class TestRetrieveHook:
    def test_empty_query_records_nothing(self):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve

        reset_collector()
        result = hybrid_retrieve('')
        assert result == []
        snap = get_collector().snapshot()
        names = {row['name'] for row in snap['counters']}
        assert 'retrieve.calls' not in names

    def test_no_candidates_records_empty(self, tmp_db):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve

        reset_collector()
        # tmp_db is empty of transcript chunks → 0 candidates.
        result = hybrid_retrieve('no such query here xyzzy')
        assert result == []
        snap = get_collector().snapshot()
        names = {row['name'] for row in snap['counters']}
        assert 'retrieve.calls' in names
        assert 'retrieve.empty' in names
