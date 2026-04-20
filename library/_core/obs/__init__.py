"""Observability — metrics collection + JSONL event log.

Thin, zero-dependency layer. Every module that wants to emit a
signal imports :func:`get_collector` and either bumps a counter
(``incr``), records a numeric observation (``observe``), or times a
block (``timed``). The collector is process-global but stateless
between runs unless callers opt into :func:`persist_event` / the
CLI flush.
"""
from __future__ import annotations

from library._core.obs.metrics import (
    MetricsCollector,
    get_collector,
    reset_collector,
    persist_event,
    load_events,
    summarize_events,
)
from library._core.obs.trace import (
    new_trace,
    current_trace,
    with_trace,
    trace_event,
    iter_events,
    events_for_trace,
    list_traces,
)

__all__ = [
    'MetricsCollector',
    'get_collector',
    'reset_collector',
    'persist_event',
    'load_events',
    'summarize_events',
    'new_trace',
    'current_trace',
    'with_trace',
    'trace_event',
    'iter_events',
    'events_for_trace',
    'list_traces',
]
