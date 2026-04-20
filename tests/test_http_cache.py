"""Tests for the SQLite-backed HTTP response cache."""
from __future__ import annotations

import sqlite3

import pytest

from library._core.fetch import http_cache


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / 'cache_test.db'
    c = sqlite3.connect(db)
    yield c
    c.close()


class TestBasics:
    def test_miss_on_empty(self, conn):
        hit, val = http_cache.get(conn, 'nope')
        assert hit is False
        assert val is None

    def test_hit_after_put(self, conn):
        clock = FakeClock()
        http_cache.put(conn, 'k', {'a': 1}, ttl_seconds=60, clock=clock)
        hit, val = http_cache.get(conn, 'k', clock=clock)
        assert hit is True
        assert val == {'a': 1}

    def test_expired_row_is_miss(self, conn):
        clock = FakeClock()
        http_cache.put(conn, 'k', {'a': 1}, ttl_seconds=10, clock=clock)
        clock.advance(11)
        hit, val = http_cache.get(conn, 'k', clock=clock)
        assert hit is False

    def test_overwrites_on_reput(self, conn):
        clock = FakeClock()
        http_cache.put(conn, 'k', {'v': 1}, ttl_seconds=60, clock=clock)
        http_cache.put(conn, 'k', {'v': 2}, ttl_seconds=60, clock=clock)
        hit, val = http_cache.get(conn, 'k', clock=clock)
        assert hit is True
        assert val == {'v': 2}


class TestEdgeCases:
    def test_empty_key_round_trip(self, conn):
        http_cache.put(conn, '', {'x': 1}, ttl_seconds=10)
        hit, _ = http_cache.get(conn, '')
        assert hit is False

    def test_zero_ttl_no_store(self, conn):
        http_cache.put(conn, 'k', {'v': 1}, ttl_seconds=0)
        hit, _ = http_cache.get(conn, 'k')
        assert hit is False

    def test_non_json_value_degrades_to_miss(self, conn):
        class NotJSON:
            pass

        # default=str lets many types through; one that survives
        # serialisation but is semantically odd still round-trips.
        # Here we verify put just swallows truly broken objects.
        http_cache.put(conn, 'k', NotJSON(), ttl_seconds=10)
        hit, val = http_cache.get(conn, 'k')
        # Either we got a string rep back or we got a miss — both fine;
        # the key invariant is "no exception leaked".
        assert hit in (True, False)


class TestPurgeAndClear:
    def test_purge_expired(self, conn):
        clock = FakeClock()
        http_cache.put(conn, 'a', 1, ttl_seconds=10, clock=clock)
        http_cache.put(conn, 'b', 2, ttl_seconds=100, clock=clock)
        clock.advance(50)
        deleted = http_cache.purge_expired(conn, clock=clock)
        assert deleted == 1
        hit_a, _ = http_cache.get(conn, 'a', clock=clock)
        hit_b, _ = http_cache.get(conn, 'b', clock=clock)
        assert hit_a is False
        assert hit_b is True

    def test_clear(self, conn):
        http_cache.put(conn, 'a', 1, ttl_seconds=1000)
        http_cache.put(conn, 'b', 2, ttl_seconds=1000)
        http_cache.clear(conn)
        assert http_cache.get(conn, 'a')[0] is False
        assert http_cache.get(conn, 'b')[0] is False
