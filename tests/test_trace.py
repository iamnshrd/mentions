"""Tests for obs/trace — ContextVar propagation + JSONL event log."""
from __future__ import annotations

import json
import threading

import pytest

from mentions_core.base.obs import trace as trace_mod
from mentions_core.base.obs.trace import (
    new_trace, current_trace, with_trace,
    trace_event, iter_events, events_for_trace, list_traces,
)


@pytest.fixture
def trace_path(monkeypatch, tmp_path):
    path = tmp_path / 'traces.jsonl'
    monkeypatch.setattr(trace_mod, '_default_trace_path', lambda: path)
    # Reset ContextVar so tests don't leak ids into each other.
    token = trace_mod._current_trace.set('')
    try:
        yield path
    finally:
        trace_mod._current_trace.reset(token)


# ── Basics ─────────────────────────────────────────────────────────────────

class TestContextVar:
    def test_new_trace_sets_current(self, trace_path):
        assert current_trace() == ''
        tid = new_trace()
        assert current_trace() == tid
        assert len(tid) == 32  # uuid4 hex

    def test_with_trace_scoped(self, trace_path):
        with with_trace() as tid:
            assert current_trace() == tid
        assert current_trace() == ''

    def test_with_trace_explicit_id(self, trace_path):
        with with_trace('abc123') as tid:
            assert tid == 'abc123'
            assert current_trace() == 'abc123'

    def test_with_trace_nested_restores(self, trace_path):
        with with_trace('outer'):
            with with_trace('inner'):
                assert current_trace() == 'inner'
            assert current_trace() == 'outer'
        assert current_trace() == ''


# ── Event log ──────────────────────────────────────────────────────────────

class TestEventLog:
    def test_event_attaches_trace_id(self, trace_path):
        with with_trace('t1'):
            trace_event('foo', x=1)
        rows = iter_events(path=trace_path)
        assert len(rows) == 1
        assert rows[0]['trace_id'] == 't1'
        assert rows[0]['name'] == 'foo'
        assert rows[0]['x'] == 1
        assert 'ts' in rows[0]

    def test_event_without_trace_writes_empty_id(self, trace_path):
        trace_event('orphan')
        rows = iter_events(path=trace_path)
        assert rows and rows[0]['trace_id'] == ''

    def test_events_for_trace_ordering(self, trace_path):
        with with_trace('alpha'):
            trace_event('a', i=1)
            trace_event('b', i=2)
        with with_trace('beta'):
            trace_event('x', i=1)
        rows = events_for_trace('alpha', path=trace_path)
        assert [r['name'] for r in rows] == ['a', 'b']
        assert all(r['trace_id'] == 'alpha' for r in rows)

    def test_events_for_empty_trace_id(self, trace_path):
        trace_event('anon')
        assert events_for_trace('', path=trace_path) == []

    def test_list_traces_summarizes(self, trace_path):
        with with_trace('one'):
            trace_event('start')
            trace_event('end')
        with with_trace('two'):
            trace_event('start')
        summaries = list_traces(path=trace_path)
        assert len(summaries) == 2
        # Each summary has required shape.
        for s in summaries:
            assert 'trace_id' in s
            assert 'duration_ms' in s
            assert 'n_events' in s

    def test_iter_events_handles_missing_file(self, tmp_path):
        assert iter_events(path=tmp_path / 'nope.jsonl') == []

    def test_iter_events_skips_junk(self, trace_path):
        with open(trace_path, 'w', encoding='utf-8') as f:
            f.write('{"trace_id":"t","name":"ok","ts":1.0}\n')
            f.write('not-json\n\n')
            f.write('{"trace_id":"t","name":"ok2","ts":2.0}\n')
        rows = iter_events(path=trace_path)
        assert len(rows) == 2


class TestThreading:
    def test_trace_is_per_thread(self, trace_path):
        # ContextVar isolates trace ids per-thread.
        seen: list[str] = []

        def worker(label):
            with with_trace(label):
                seen.append(current_trace())

        threads = [threading.Thread(target=worker, args=(f't{i}',))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(seen) == [f't{i}' for i in range(5)]


# ── Hook integration ───────────────────────────────────────────────────────

class TestHookIntegration:
    def test_intent_classifier_emits_event(self, trace_path):
        from mentions_domain.llm import NullClient
        from mentions_domain.intent.classifier import classify_intent

        with with_trace('integr'):
            classify_intent('what is btc doing', client=NullClient())
        rows = events_for_trace('integr', path=trace_path)
        assert any(r['name'] == 'intent.classify' for r in rows)
        e = next(r for r in rows if r['name'] == 'intent.classify')
        assert e['source'] == 'rules'
        assert 'intent' in e
        assert 'confidence' in e
