"""Tests for the Kalshi client — cache, retry, metrics wiring.

We patch ``urllib.request.urlopen`` to avoid real network calls and
verify that the wrapper layer (cache + rate limit + retry + metrics)
behaves correctly.
"""
from __future__ import annotations

import io
import json
import sqlite3
import urllib.request
from unittest.mock import patch

import pytest

from agents.mentions.providers.kalshi import client as kclient
from mentions_core.base.net.rate_limit import TokenBucket
from mentions_core.base.obs import get_collector, reset_collector


# ── Fakes ──────────────────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self._raw


def _fake_urlopen(payload, counter):
    def _factory(req, timeout=10):
        counter.append(1)
        return _FakeResponse(payload)
    return _factory


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def fast_limiter(monkeypatch):
    """Replace the module-global rate limiter with a no-op bucket."""
    bucket = TokenBucket(capacity=1_000_000,
                         refill_per_sec=1_000_000,
                         sleep=lambda _d: None)
    monkeypatch.setattr(kclient, '_LIMITER', bucket)
    yield bucket


@pytest.fixture
def fresh_metrics():
    reset_collector()
    yield get_collector()
    reset_collector()


# ── Cache behaviour ────────────────────────────────────────────────────────

class TestCache:
    def test_second_call_hits_cache(self, tmp_db, fast_limiter,
                                    fresh_metrics):
        calls = []
        payload = {'market': {'ticker': 'X', 'yes_price': 42}}
        with patch('urllib.request.urlopen',
                   _fake_urlopen(payload, calls)):
            r1 = kclient.get_market('X')
            r2 = kclient.get_market('X')
        assert r1 == r2
        # HTTP called exactly once — second call served from cache.
        assert len(calls) == 1
        names = {row['name'] for row in fresh_metrics.snapshot()['counters']}
        assert 'kalshi.cache_miss' in names
        assert 'kalshi.cache_hit'  in names

    def test_cache_disabled_via_use_cache_false(self, tmp_db, fast_limiter):
        calls = []
        payload = {'market': {'ticker': 'Y'}}
        with patch('urllib.request.urlopen',
                   _fake_urlopen(payload, calls)):
            kclient._get('/markets/Y', use_cache=False)
            kclient._get('/markets/Y', use_cache=False)
        assert len(calls) == 2


# ── Retry behaviour ────────────────────────────────────────────────────────

class TestRetry:
    def test_retries_on_500(self, tmp_db, fast_limiter, monkeypatch,
                            fresh_metrics):
        # First two calls: 500. Third: 200.
        state = {'calls': 0}
        payload = {'market': {'ticker': 'Z'}}

        class FakeHTTPError(Exception):
            def __init__(self, code):
                self.code = code
                self.reason = 'boom'

            def read(self):
                return b'boom'

        def _urlopen(req, timeout=10):
            state['calls'] += 1
            if state['calls'] < 3:
                import urllib.error
                raise urllib.error.HTTPError(
                    req.full_url, 500, 'boom', {}, io.BytesIO(b'boom'))
            return _FakeResponse(payload)

        # Disable retry sleeps in the underlying with_retry.
        import mentions_domain.llm.retry as retry_mod
        monkeypatch.setattr(retry_mod, 'time',
                            type('T', (), {'sleep': lambda _d: None})())

        with patch('urllib.request.urlopen', _urlopen):
            result = kclient._get('/markets/Z', use_cache=False)
        assert result == payload
        assert state['calls'] == 3
        names = {row['name'] for row in fresh_metrics.snapshot()['counters']}
        assert 'kalshi.retry'   in names
        assert 'kalshi.call_ok' in names

    def test_4xx_not_retried(self, tmp_db, fast_limiter, fresh_metrics):
        state = {'calls': 0}

        def _urlopen(req, timeout=10):
            state['calls'] += 1
            import urllib.error
            raise urllib.error.HTTPError(
                req.full_url, 401, 'nope', {}, io.BytesIO(b'unauth'))

        with patch('urllib.request.urlopen', _urlopen):
            result = kclient._get('/markets/FORBIDDEN', use_cache=False)
        assert result is None
        assert state['calls'] == 1
        names = {row['name'] for row in fresh_metrics.snapshot()['counters']}
        assert 'kalshi.call_err' in names


# ── Metrics integration ────────────────────────────────────────────────────

class TestMetrics:
    def test_success_increments_ok_counter(self, tmp_db, fast_limiter,
                                           fresh_metrics):
        with patch('urllib.request.urlopen',
                   _fake_urlopen({'market': {}}, [])):
            kclient._get('/markets/A', use_cache=False)
        snap = fresh_metrics.snapshot()
        names = {row['name'] for row in snap['counters']}
        assert 'kalshi.call_attempt' in names
        assert 'kalshi.call_ok'      in names
        # Latency histogram recorded.
        hist_names = {row['name'] for row in snap['histograms']}
        assert 'kalshi.latency_ms' in hist_names


# ── Rate limit integration ─────────────────────────────────────────────────

class TestRateLimit:
    def test_acquire_called_per_request(self, tmp_db, monkeypatch):
        acquires = []

        class CountingBucket:
            def acquire(self, n=1):
                acquires.append(n)
                return 0.0

        monkeypatch.setattr(kclient, '_LIMITER', CountingBucket())
        with patch('urllib.request.urlopen',
                   _fake_urlopen({'market': {}}, [])):
            kclient._get('/markets/M', use_cache=False)
            kclient._get('/markets/M', use_cache=False)
        assert acquires == [1, 1]
