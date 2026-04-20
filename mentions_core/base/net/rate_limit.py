"""Token-bucket rate limiter."""
from __future__ import annotations

import threading
import time


class TokenBucket:
    """Classic token-bucket limiter."""

    def __init__(self, *,
                 capacity: int = 10,
                 refill_per_sec: float = 10.0,
                 clock=time.monotonic,
                 sleep=time.sleep):
        if capacity <= 0:
            raise ValueError('capacity must be positive')
        if refill_per_sec <= 0:
            raise ValueError('refill_per_sec must be positive')
        self._capacity = float(capacity)
        self._rate = float(refill_per_sec)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._tokens = float(capacity)
        self._last = self._clock()

    def _refill_locked(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last = now

    def try_acquire(self, n: int = 1) -> bool:
        if n <= 0:
            return True
        with self._lock:
            self._refill_locked()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    def acquire(self, n: int = 1) -> float:
        if n <= 0:
            return 0.0
        if n > self._capacity:
            raise ValueError(f'cannot acquire {n} tokens (capacity={self._capacity})')
        waited = 0.0
        while True:
            with self._lock:
                self._refill_locked()
                if self._tokens >= n:
                    self._tokens -= n
                    return waited
                deficit = n - self._tokens
                wait = deficit / self._rate
            self._sleep(wait)
            waited += wait

    def tokens(self) -> float:
        with self._lock:
            self._refill_locked()
            return self._tokens

