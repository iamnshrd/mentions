"""In-process metrics collector + JSONL event log.

:class:`MetricsCollector` is intentionally minimal:

* ``incr(name, n=1, tags={})``   — integer counters.
* ``observe(name, value, tags={})`` — numeric observations (used for
  latency histograms, token counts, candidate-pool sizes).
* ``timed(name, tags={})``       — context manager measuring wall
  time in milliseconds and calling :meth:`observe` with the result.
* ``snapshot()``                 — returns a JSON-safe dict with
  counters + per-histogram summary (count / min / max / mean / p50 /
  p95 / p99).
* ``reset()``                    — clears in-memory state.

A process-global singleton lives behind :func:`get_collector`. Tests
call :func:`reset_collector` (which recreates the singleton) so state
does not bleed between tests.

Events can be persisted by calling :func:`persist_event` (appends a
single JSON line to ``METRICS_LOG``). The CLI flushes a snapshot on
demand — callers don't need to manage files directly.
"""
from __future__ import annotations

import bisect
import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from statistics import mean

log = logging.getLogger('mentions')


def _tag_key(tags: dict | None) -> str:
    if not tags:
        return ''
    return '|'.join(f'{k}={tags[k]}' for k in sorted(tags.keys()))


def _percentile(values: list[float], pct: float) -> float:
    """Classic nearest-rank percentile on a sorted list."""
    if not values:
        return 0.0
    k = max(0, min(len(values) - 1, int(round(pct / 100.0 * (len(values) - 1)))))
    return values[k]


class MetricsCollector:
    """Thread-safe in-memory counter + histogram store."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, str], int] = {}
        self._histograms: dict[tuple[str, str], list[float]] = {}

    # -- recording ----------------------------------------------------------

    def incr(self, name: str, n: int = 1, tags: dict | None = None) -> None:
        key = (name, _tag_key(tags))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + int(n)

    def observe(self, name: str, value: float,
                tags: dict | None = None) -> None:
        key = (name, _tag_key(tags))
        with self._lock:
            bucket = self._histograms.setdefault(key, [])
            bisect.insort(bucket, float(value))

    @contextmanager
    def timed(self, name: str, tags: dict | None = None):
        """Measure wall time of the wrapped block in ms."""
        t0 = time.monotonic()
        try:
            yield
        finally:
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            self.observe(name, elapsed_ms, tags=tags)

    # -- readback -----------------------------------------------------------

    def snapshot(self) -> dict:
        with self._lock:
            counters = [
                {'name': k[0], 'tags': k[1], 'value': v}
                for k, v in sorted(self._counters.items())
            ]
            histograms = []
            for k, values in sorted(self._histograms.items()):
                if not values:
                    continue
                # values is maintained sorted by observe().
                histograms.append({
                    'name': k[0],
                    'tags': k[1],
                    'count': len(values),
                    'min':   round(values[0], 3),
                    'max':   round(values[-1], 3),
                    'mean':  round(mean(values), 3),
                    'p50':   round(_percentile(values, 50), 3),
                    'p95':   round(_percentile(values, 95), 3),
                    'p99':   round(_percentile(values, 99), 3),
                })
        return {'counters': counters, 'histograms': histograms}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()


# ── Process singleton ──────────────────────────────────────────────────────

_collector: MetricsCollector | None = None
_singleton_lock = threading.Lock()


def get_collector() -> MetricsCollector:
    global _collector
    if _collector is None:
        with _singleton_lock:
            if _collector is None:
                _collector = MetricsCollector()
    return _collector


def reset_collector() -> MetricsCollector:
    """Drop the process-global collector and return a fresh one.

    Used by tests to isolate state between cases; callers in
    production code should prefer :meth:`MetricsCollector.reset`.
    """
    global _collector
    with _singleton_lock:
        _collector = MetricsCollector()
    return _collector


# ── JSONL event log ────────────────────────────────────────────────────────

def _default_log_path() -> Path:
    from library.config import METRICS_LOG
    return METRICS_LOG


def persist_event(event: dict, path: Path | None = None) -> None:
    """Append *event* as one JSON line to the metrics log.

    The log is append-only and rotation-friendly. Failures are logged
    but never raised — observability must never break the caller.
    """
    path = path or _default_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except OSError as exc:
        log.debug('persist_event failed: %s', exc)


def load_events(path: Path | None = None,
                limit: int | None = None) -> list[dict]:
    """Read the JSONL event log, newest first. Returns at most *limit* rows."""
    path = path or _default_log_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        log.debug('load_events failed: %s', exc)
        return []
    rows.reverse()
    if limit is not None:
        rows = rows[: max(0, int(limit))]
    return rows


def summarize_events(events: list[dict]) -> dict:
    """Aggregate a batch of persisted snapshot events into a single view.

    Each *event* is typically the output of
    :meth:`MetricsCollector.snapshot` plus a ``timestamp``.  Counters
    sum across events; histograms are merged element-wise and the
    combined distribution is re-summarized.
    """
    counter_totals: dict[tuple[str, str], int] = {}
    hist_values:    dict[tuple[str, str], list[float]] = {}

    for ev in events:
        for c in ev.get('counters') or []:
            key = (c.get('name', ''), c.get('tags', ''))
            counter_totals[key] = counter_totals.get(key, 0) + int(c.get('value', 0))
        for h in ev.get('histograms') or []:
            key = (h.get('name', ''), h.get('tags', ''))
            # We no longer have the raw values, so fake a rough spread
            # by replaying the reported summary: count × mean as a
            # single bucket keeps counters honest without pretending to
            # preserve the original distribution.
            count = int(h.get('count', 0))
            if count <= 0:
                continue
            hist_values.setdefault(key, []).extend([float(h['mean'])] * count)

    counters = [
        {'name': k[0], 'tags': k[1], 'value': v}
        for k, v in sorted(counter_totals.items())
    ]
    histograms = []
    for k, values in sorted(hist_values.items()):
        values.sort()
        histograms.append({
            'name': k[0], 'tags': k[1], 'count': len(values),
            'min':  round(values[0], 3),
            'max':  round(values[-1], 3),
            'mean': round(mean(values), 3),
            'p50':  round(_percentile(values, 50), 3),
            'p95':  round(_percentile(values, 95), 3),
            'p99':  round(_percentile(values, 99), 3),
        })
    return {'n_events': len(events), 'counters': counters,
            'histograms': histograms}
