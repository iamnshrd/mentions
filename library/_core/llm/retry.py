"""Retry helpers + circuit breaker for LLM calls.

Two independent pieces:

* :func:`is_retryable` — true for transient failures we want to retry
  (rate-limit 429, server-side 5xx, connection/timeout errors). The
  check is string-based to avoid hard-importing ``anthropic`` — we
  never want this module to fail to import when the SDK is absent.
* :func:`with_retry` — generic exponential-backoff wrapper around any
  callable. Retries up to ``max_attempts`` times with delays
  ``base_delay, base_delay*2, base_delay*4, ...``. A custom ``sleep``
  function lets tests run instantly.
* :class:`CircuitBreaker` — after ``threshold`` consecutive failures
  the breaker *opens* and subsequent calls short-circuit with
  :class:`CircuitOpenError` for ``cooldown_seconds``. One successful
  call closes it again. Thread-safe.

Design choices:

* No SDK imports — the retry layer works for any callable. The
  ``anthropic`` error hierarchy is matched by name so we stay
  dependency-free here.
* Retries are counted, not attempts — ``max_attempts=3`` means at
  most 3 CALLS (original + 2 retries). Matches the convention in
  tenacity / urllib3.
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger('mentions')


# ── Retryability ───────────────────────────────────────────────────────────

# Error class names considered transient. Listed as strings so we don't
# have to import anthropic at module load.
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
    """Best-effort extraction of an HTTP status code from SDK exceptions."""
    for attr in ('status_code', 'status', 'code'):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            return v
    # anthropic.APIStatusError stores the response; try response.status_code
    resp = getattr(exc, 'response', None)
    if resp is not None:
        v = getattr(resp, 'status_code', None)
        if isinstance(v, int):
            return v
    return None


def is_retryable(exc: BaseException) -> bool:
    """True if *exc* represents a transient failure worth retrying."""
    cls_name = exc.__class__.__name__
    if cls_name in _RETRY_NAME_HINTS:
        return True
    code = _status_code(exc)
    if code is not None:
        # 408 request timeout, 425 too early, 429 rate limit, 5xx server.
        if code in (408, 425, 429) or 500 <= code < 600:
            return True
    return False


# ── Retry loop ─────────────────────────────────────────────────────────────

def with_retry(fn, *,
               max_attempts: int = 3,
               base_delay: float = 1.0,
               max_delay: float = 30.0,
               sleep=time.sleep,
               on_retry=None):
    """Call *fn* with exponential backoff on retryable failures.

    Returns the first successful result. If every attempt fails, the
    LAST exception is re-raised. Non-retryable exceptions propagate
    immediately without consuming attempts.

    * *max_attempts* — total call count (incl. the first).
    * *base_delay*   — seconds before the first retry; doubles each time.
    * *max_delay*    — cap per individual backoff.
    * *sleep*        — injectable sleep function; tests pass a stub.
    * *on_retry*     — optional callback ``(attempt_num, exc, delay)``.
    """
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
            log.debug('retryable failure on attempt %d/%d: %s (sleep %.2fs)',
                      attempt, max_attempts, exc, delay)
            if on_retry is not None:
                try:
                    on_retry(attempt, exc, delay)
                except Exception:  # pragma: no cover — defensive
                    pass
            sleep(delay)
    # Unreachable — either we returned or re-raised.
    if last_exc is not None:  # pragma: no cover
        raise last_exc
    raise RuntimeError('with_retry: no attempts executed')


# ── Circuit breaker ────────────────────────────────────────────────────────

class CircuitOpenError(RuntimeError):
    """Raised when the breaker refuses a call because it is open."""


class CircuitBreaker:
    """Consecutive-failure circuit breaker.

    State machine:

    * CLOSED    — calls flow normally.
    * OPEN      — all calls rejected for ``cooldown_seconds`` after
                  opening. Transitions to HALF_OPEN on the next call
                  made once the cooldown has elapsed.
    * HALF_OPEN — exactly one call is allowed through. Success →
                  CLOSED, failure → OPEN (cooldown restarts).

    Thread-safe. The ``clock`` parameter lets tests pin wall time.
    """

    CLOSED    = 'closed'
    OPEN      = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, *, threshold: int = 3,
                 cooldown_seconds: float = 30.0,
                 clock=time.monotonic):
        self._threshold = int(threshold)
        self._cooldown  = float(cooldown_seconds)
        self._clock     = clock
        self._lock      = threading.Lock()
        self._fail_count = 0
        self._opened_at: float | None = None
        self._state = self.CLOSED

    # -- state readback ----------------------------------------------------

    def state(self) -> str:
        with self._lock:
            self._maybe_half_open()
            return self._state

    # -- hook points -------------------------------------------------------

    def before_call(self) -> None:
        """Raise :class:`CircuitOpenError` if the breaker is open."""
        with self._lock:
            self._maybe_half_open()
            if self._state == self.OPEN:
                raise CircuitOpenError(
                    f'circuit open (fail_count={self._fail_count})'
                )

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

    # -- wrapper -----------------------------------------------------------

    def call(self, fn):
        """Execute *fn* through the breaker.

        Behaviour:
          * OPEN (cooldown not elapsed) → :class:`CircuitOpenError`.
          * Otherwise call *fn*. On retryable exception: record
            failure, re-raise. On success: record success.
        """
        self.before_call()
        try:
            result = fn()
        except Exception as exc:
            # Only count transient failures against the breaker;
            # programming errors should not trip it.
            if is_retryable(exc):
                self.record_failure()
            raise
        self.record_success()
        return result

    # -- internals ---------------------------------------------------------

    def _maybe_half_open(self) -> None:
        if self._state != self.OPEN or self._opened_at is None:
            return
        if (self._clock() - self._opened_at) >= self._cooldown:
            self._state = self.HALF_OPEN
