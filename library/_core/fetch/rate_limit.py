"""Token-bucket rate limiter.

Thread-safe, injectable clock, cheap per-call. Used by the Kalshi
client to stay inside the public 10 req/s ceiling without relying on
server-side 429s.

Design:
* ``TokenBucket(capacity=10, refill_per_sec=10.0)`` fills continuously
  at ``refill_per_sec`` until it reaches ``capacity``. :meth:`acquire`
  withdraws ``n`` tokens, blocking (via the supplied ``sleep`` fn)
  when the bucket is empty. ``try_acquire`` returns ``False``
  non-blocking instead.
* The clock is injectable for deterministic tests — pass ``clock=``
  (e.g. a ``FakeClock.__call__``) and ``sleep=`` (e.g. a ``list.append``
  spy) to run the pacing logic without any real wall-clock dependency.
"""
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
        self._rate     = float(refill_per_sec)
        self._clock    = clock
        self._sleep    = sleep
        self._lock     = threading.Lock()
        self._tokens   = float(capacity)
        self._last     = self._clock()

    # -- helpers -----------------------------------------------------------

    def _refill_locked(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last = now

    # -- public API --------------------------------------------------------

    def try_acquire(self, n: int = 1) -> bool:
        """Take *n* tokens if available; return False otherwise."""
        if n <= 0:
            return True
        with self._lock:
            self._refill_locked()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    def acquire(self, n: int = 1) -> float:
        """Take *n* tokens, sleeping as needed. Returns total wait in seconds."""
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
                # Seconds needed to accrue `deficit` more tokens.
                wait = deficit / self._rate
            self._sleep(wait)
            waited += wait

    def tokens(self) -> float:
        """Current token count (for observability / tests)."""
        with self._lock:
            self._refill_locked()
            return self._tokens
