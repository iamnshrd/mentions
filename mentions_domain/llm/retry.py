"""Retry helpers + circuit breaker for LLM calls."""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger('mentions')

_RETRY_NAME_HINTS = {
    'RateLimitError',
    'APIConnectionError',
    'APIStatusError',
    'APITimeoutError',
    'InternalServerError',
    'ServiceUnavailableError',
    'ConnectionError',
    'Timeout',
    'TimeoutError',
    'ReadTimeout',
}


def _status_code(exc: BaseException) -> int | None:
    for attr in ('status_code', 'status', 'code'):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            return v
    resp = getattr(exc, 'response', None)
    if resp is not None:
        v = getattr(resp, 'status_code', None)
        if isinstance(v, int):
            return v
    return None


def is_retryable(exc: BaseException) -> bool:
    cls_name = exc.__class__.__name__
    if cls_name in _RETRY_NAME_HINTS:
        return True
    code = _status_code(exc)
    if code is not None and (code in (408, 425, 429) or 500 <= code < 600):
        return True
    return False


def with_retry(
    fn,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    sleep=time.sleep,
    on_retry=None,
):
    attempt = 0
    last_exc: BaseException | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not is_retryable(exc) or attempt >= max_attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            log.debug('retryable failure on attempt %d/%d: %s (sleep %.2fs)', attempt, max_attempts, exc, delay)
            if on_retry is not None:
                try:
                    on_retry(attempt, exc, delay)
                except Exception:
                    pass
            sleep(delay)
    if last_exc is not None:  # pragma: no cover
        raise last_exc
    raise RuntimeError('with_retry: no attempts executed')


class CircuitOpenError(RuntimeError):
    """Raised when the breaker refuses a call because it is open."""


class CircuitBreaker:
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, *, threshold: int = 3, cooldown_seconds: float = 30.0, clock=time.monotonic):
        self._threshold = int(threshold)
        self._cooldown = float(cooldown_seconds)
        self._clock = clock
        self._lock = threading.Lock()
        self._fail_count = 0
        self._opened_at: float | None = None
        self._state = self.CLOSED

    def state(self) -> str:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def before_call(self) -> None:
        with self._lock:
            self._maybe_half_open()
            if self._state == self.OPEN:
                raise CircuitOpenError(f'circuit open (fail_count={self._fail_count})')

    def record_success(self) -> None:
        with self._lock:
            self._fail_count = 0
            self._opened_at = None
            self._state = self.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._fail_count += 1
            if self._state == self.HALF_OPEN or self._fail_count >= self._threshold:
                self._state = self.OPEN
                self._opened_at = self._clock()

    def call(self, fn):
        self.before_call()
        try:
            result = fn()
        except Exception as exc:
            if is_retryable(exc):
                self.record_failure()
            raise
        self.record_success()
        return result

    def _maybe_half_open(self) -> None:
        if self._state != self.OPEN or self._opened_at is None:
            return
        if (self._clock() - self._opened_at) >= self._cooldown:
            self._state = self.HALF_OPEN
