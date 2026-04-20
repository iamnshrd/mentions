"""Tests for the LLM retry + circuit-breaker helpers."""
from __future__ import annotations

import pytest

from mentions_domain.llm.retry import (
    is_retryable, with_retry,
    CircuitBreaker, CircuitOpenError,
)


# ── Retryability ───────────────────────────────────────────────────────────

class _FakeStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f'status {status_code}')
        self.status_code = status_code


class RateLimitError(Exception):
    """Matches anthropic.RateLimitError by name."""


class APIConnectionError(Exception):
    pass


class TestIsRetryable:
    def test_by_class_name(self):
        assert is_retryable(RateLimitError('too many'))
        assert is_retryable(APIConnectionError('down'))

    def test_by_status_5xx(self):
        assert is_retryable(_FakeStatusError(503))
        assert is_retryable(_FakeStatusError(500))

    def test_by_status_429(self):
        assert is_retryable(_FakeStatusError(429))

    def test_2xx_not_retryable(self):
        assert not is_retryable(_FakeStatusError(200))

    def test_4xx_non_429_not_retryable(self):
        assert not is_retryable(_FakeStatusError(400))
        assert not is_retryable(_FakeStatusError(401))

    def test_random_exception_not_retryable(self):
        assert not is_retryable(ValueError('nope'))


# ── with_retry ─────────────────────────────────────────────────────────────

class TestWithRetry:
    def test_success_first_try(self):
        calls = []

        def fn():
            calls.append(1)
            return 'ok'

        assert with_retry(fn, max_attempts=3, sleep=lambda _d: None) == 'ok'
        assert calls == [1]

    def test_retries_then_succeeds(self):
        calls = []
        sleeps = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise RateLimitError()
            return 'done'

        result = with_retry(fn, max_attempts=5,
                            base_delay=0.1, sleep=sleeps.append)
        assert result == 'done'
        assert len(calls) == 3
        # Exponential: 0.1, 0.2 before the successful third call.
        assert sleeps == [0.1, 0.2]

    def test_non_retryable_propagates_immediately(self):
        calls = []

        def fn():
            calls.append(1)
            raise ValueError('fatal')

        with pytest.raises(ValueError):
            with_retry(fn, max_attempts=5, sleep=lambda _d: None)
        assert calls == [1]

    def test_exhausts_and_reraises(self):
        calls = []

        def fn():
            calls.append(1)
            raise RateLimitError('keep failing')

        with pytest.raises(RateLimitError):
            with_retry(fn, max_attempts=3,
                       base_delay=0.01, sleep=lambda _d: None)
        assert len(calls) == 3

    def test_on_retry_callback(self):
        events = []
        calls = [0]

        def fn():
            calls[0] += 1
            if calls[0] < 3:
                raise RateLimitError()
            return 'ok'

        with_retry(fn, max_attempts=5, base_delay=0.1,
                   sleep=lambda _d: None,
                   on_retry=lambda n, e, d: events.append((n, d)))
        # Two retries → callback invoked twice.
        assert events == [(1, 0.1), (2, 0.2)]

    def test_max_delay_cap(self):
        sleeps = []

        def fn():
            raise RateLimitError()

        with pytest.raises(RateLimitError):
            with_retry(fn, max_attempts=6, base_delay=10.0,
                       max_delay=15.0, sleep=sleeps.append)
        # Delays capped at 15 once exponential exceeds it.
        assert all(d <= 15.0 for d in sleeps)
        assert max(sleeps) == 15.0


# ── CircuitBreaker ─────────────────────────────────────────────────────────

class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestCircuitBreaker:
    def test_closed_initially(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=10)
        assert cb.state() == CircuitBreaker.CLOSED

    def test_opens_after_threshold_failures(self):
        clock = FakeClock()
        cb = CircuitBreaker(threshold=3, cooldown_seconds=10, clock=clock)
        for _ in range(3):
            with pytest.raises(RateLimitError):
                cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        assert cb.state() == CircuitBreaker.OPEN

    def test_open_rejects_calls(self):
        clock = FakeClock()
        cb = CircuitBreaker(threshold=2, cooldown_seconds=10, clock=clock)
        for _ in range(2):
            with pytest.raises(RateLimitError):
                cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: 'never')

    def test_half_open_after_cooldown(self):
        clock = FakeClock()
        cb = CircuitBreaker(threshold=2, cooldown_seconds=10, clock=clock)
        for _ in range(2):
            with pytest.raises(RateLimitError):
                cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        # Still open before cooldown elapses.
        clock.advance(5)
        assert cb.state() == CircuitBreaker.OPEN
        # Half-open after cooldown.
        clock.advance(6)
        assert cb.state() == CircuitBreaker.HALF_OPEN

    def test_half_open_success_closes(self):
        clock = FakeClock()
        cb = CircuitBreaker(threshold=2, cooldown_seconds=10, clock=clock)
        for _ in range(2):
            with pytest.raises(RateLimitError):
                cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        clock.advance(11)
        # One successful call while half-open → closed.
        assert cb.call(lambda: 'ok') == 'ok'
        assert cb.state() == CircuitBreaker.CLOSED

    def test_half_open_failure_reopens(self):
        clock = FakeClock()
        cb = CircuitBreaker(threshold=2, cooldown_seconds=10, clock=clock)
        for _ in range(2):
            with pytest.raises(RateLimitError):
                cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        clock.advance(11)
        # Failed call while half-open → re-opens.
        with pytest.raises(RateLimitError):
            cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        assert cb.state() == CircuitBreaker.OPEN

    def test_non_retryable_failure_does_not_trip(self):
        clock = FakeClock()
        cb = CircuitBreaker(threshold=2, cooldown_seconds=10, clock=clock)
        for _ in range(5):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError('bug')))
        # Programming errors don't open the breaker.
        assert cb.state() == CircuitBreaker.CLOSED

    def test_success_resets_fail_count(self):
        clock = FakeClock()
        cb = CircuitBreaker(threshold=3, cooldown_seconds=10, clock=clock)
        # One failure then a success.
        with pytest.raises(RateLimitError):
            cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        cb.call(lambda: 'ok')
        # Fail counter reset — need full threshold again to open.
        for _ in range(2):
            with pytest.raises(RateLimitError):
                cb.call(lambda: (_ for _ in ()).throw(RateLimitError()))
        assert cb.state() == CircuitBreaker.CLOSED
