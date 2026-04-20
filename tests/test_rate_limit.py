"""Tests for the TokenBucket rate limiter."""
from __future__ import annotations

import pytest

from library._core.fetch.rate_limit import TokenBucket


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestInit:
    def test_starts_full(self):
        bucket = TokenBucket(capacity=5, refill_per_sec=1.0,
                             clock=FakeClock(), sleep=lambda _d: None)
        assert bucket.tokens() == 5.0

    def test_rejects_zero_capacity(self):
        with pytest.raises(ValueError):
            TokenBucket(capacity=0, refill_per_sec=1.0)

    def test_rejects_zero_rate(self):
        with pytest.raises(ValueError):
            TokenBucket(capacity=1, refill_per_sec=0)


class TestTryAcquire:
    def test_success_when_full(self):
        bucket = TokenBucket(capacity=3, refill_per_sec=1.0,
                             clock=FakeClock(), sleep=lambda _d: None)
        assert bucket.try_acquire(1) is True
        assert bucket.tokens() == 2.0

    def test_fails_when_empty(self):
        clock = FakeClock()
        bucket = TokenBucket(capacity=2, refill_per_sec=1.0,
                             clock=clock, sleep=lambda _d: None)
        assert bucket.try_acquire(2) is True
        assert bucket.try_acquire(1) is False

    def test_refills_over_time(self):
        clock = FakeClock()
        bucket = TokenBucket(capacity=5, refill_per_sec=2.0,
                             clock=clock, sleep=lambda _d: None)
        # Drain.
        assert bucket.try_acquire(5) is True
        clock.advance(2.0)  # 2s * 2 tok/s = 4 tokens refilled
        assert bucket.try_acquire(4) is True
        assert bucket.try_acquire(1) is False


class TestAcquireBlocking:
    def test_no_wait_when_full(self):
        sleeps = []
        bucket = TokenBucket(capacity=3, refill_per_sec=1.0,
                             clock=FakeClock(), sleep=sleeps.append)
        waited = bucket.acquire(1)
        assert waited == 0.0
        assert sleeps == []

    def test_sleeps_when_empty(self):
        sleeps = []
        clock = FakeClock()

        def fake_sleep(dt):
            sleeps.append(dt)
            clock.advance(dt)

        bucket = TokenBucket(capacity=2, refill_per_sec=1.0,
                             clock=clock, sleep=fake_sleep)
        assert bucket.acquire(2) == 0.0
        # Next acquire empties further — must wait 1s for 1 refill.
        waited = bucket.acquire(1)
        assert waited == pytest.approx(1.0, abs=1e-6)
        assert sum(sleeps) == pytest.approx(1.0, abs=1e-6)

    def test_exceeding_capacity_raises(self):
        bucket = TokenBucket(capacity=2, refill_per_sec=1.0,
                             clock=FakeClock(), sleep=lambda _d: None)
        with pytest.raises(ValueError):
            bucket.acquire(3)

    def test_zero_n_is_free(self):
        bucket = TokenBucket(capacity=2, refill_per_sec=1.0,
                             clock=FakeClock(), sleep=lambda _d: None)
        assert bucket.acquire(0) == 0.0
        assert bucket.try_acquire(0) is True


class TestCapacityCap:
    def test_does_not_refill_past_capacity(self):
        clock = FakeClock()
        bucket = TokenBucket(capacity=5, refill_per_sec=10.0,
                             clock=clock, sleep=lambda _d: None)
        clock.advance(100)  # Wildly more than needed.
        assert bucket.tokens() == 5.0
