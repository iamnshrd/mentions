"""Trace propagation — one trace_id per logical request.

A *trace* is the chain of events produced by one top-level call
(``orchestrate(query)``, ``run_extraction(doc)``, ``run_eval(...)``).
Every hot path (intent, retrieve, LLM, extract, orchestrator) emits
structured events tagged with the current trace id, so a single user
request can be reconstructed end-to-end.

Design:

* :data:`_current_trace` is a :class:`contextvars.ContextVar`. Propagation
  is automatic across function calls within the same task/thread —
  callers do not thread a ``trace_id`` argument through every function.
* :func:`new_trace` generates a uuid4 hex and sets it on the current
  context. :func:`with_trace` is a context manager restoring the
  previous value on exit (so nested traces don't leak).
* :func:`trace_event` appends a JSONL line to :data:`TRACE_LOG` with
  the current trace id, a wall-clock timestamp, the event name, and
  arbitrary fields. Safe no-op when no trace is set.
* :func:`iter_events` / :func:`events_for_trace` read the log back for
  debugging.

The trace log is a SEPARATE file from the metrics snapshot log —
metrics are aggregate, traces are per-request. Both live in
``workspace/``.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

log = logging.getLogger('mentions')

# ── Context var ────────────────────────────────────────────────────────────

_current_trace: ContextVar[str] = ContextVar('mentions_trace_id', default='')


def new_trace() -> str:
    """Generate a fresh trace id and make it current."""
    tid = uuid.uuid4().hex
    _current_trace.set(tid)
    return tid


def current_trace() -> str:
    """Return the trace id set on the current context (or '')."""
    return _current_trace.get()


@contextmanager
def with_trace(trace_id: str | None = None):
    """Context manager that sets a trace id for the duration of a block.

    Usage::

        with with_trace() as tid:
            ...  # every trace_event() inside gets tid attached

    When *trace_id* is ``None`` a fresh uuid4 is generated; otherwise
    the supplied string is used (useful for replaying or joining
    external ids).
    """
    tid = trace_id or uuid.uuid4().hex
    token = _current_trace.set(tid)
    try:
        yield tid
    finally:
        _current_trace.reset(token)


# ── Event log ──────────────────────────────────────────────────────────────

def _default_trace_path() -> Path:
    from library.config import TRACE_LOG
    return TRACE_LOG


_write_lock = threading.Lock()


def trace_event(name: str, **fields) -> None:
    """Append an event line to the trace log.

    Emits ``{ts, trace_id, name, ...fields}`` as a single JSON line.
    When no trace is set the event still fires (with ``trace_id=''``);
    this lets callers turn on trace logging by simply running inside a
    :func:`with_trace` block without having to branch.

    Never raises — observability must never break the caller.
    """
    try:
        event = {
            'ts':       time.time(),
            'trace_id': _current_trace.get(),
            'name':     name,
        }
        event.update(fields)
        path = _default_trace_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, default=str)
        with _write_lock:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
    except OSError as exc:
        log.debug('trace_event write failed: %s', exc)
    except Exception as exc:  # pragma: no cover — defensive
        log.debug('trace_event unexpected failure: %s', exc)


def iter_events(path: Path | None = None,
                limit: int | None = None) -> list[dict]:
    """Read the trace log (newest first). At most *limit* rows."""
    path = path or _default_trace_path()
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
        log.debug('iter_events failed: %s', exc)
        return []
    rows.reverse()
    if limit is not None:
        rows = rows[: max(0, int(limit))]
    return rows


def events_for_trace(trace_id: str,
                     path: Path | None = None) -> list[dict]:
    """Return every event with *trace_id*, oldest first (reconstruction order).

    The JSONL log is append-only, so file order *is* chronological.
    We rely on that rather than sorting by ``ts`` — on Windows
    ``time.time()`` has ~16 ms resolution, so two back-to-back events
    can tie and a sort key would shuffle them.
    """
    if not trace_id:
        return []
    # iter_events reverses for newest-first; undo that to get oldest-first.
    newest_first = iter_events(path=path, limit=None)
    oldest_first = list(reversed(newest_first))
    return [r for r in oldest_first if r.get('trace_id') == trace_id]


def list_traces(path: Path | None = None,
                limit: int = 20) -> list[dict]:
    """Summarize recent traces — one row per trace id.

    Each row carries ``trace_id``, ``ts_start``, ``ts_end``,
    ``duration_ms``, ``n_events``, and the names of the first/last
    events (usually ``trace.start`` / ``trace.end``).
    """
    rows = iter_events(path=path, limit=None)
    by_trace: dict[str, list[dict]] = {}
    for r in rows:
        tid = r.get('trace_id') or ''
        if not tid:
            continue
        by_trace.setdefault(tid, []).append(r)

    summaries: list[dict] = []
    for tid, events in by_trace.items():
        events.sort(key=lambda r: r.get('ts', 0.0))
        ts_start = events[0].get('ts', 0.0)
        ts_end   = events[-1].get('ts', ts_start)
        summaries.append({
            'trace_id':    tid,
            'ts_start':    ts_start,
            'ts_end':      ts_end,
            'duration_ms': round((ts_end - ts_start) * 1000.0, 3),
            'n_events':    len(events),
            'first':       events[0].get('name', ''),
            'last':        events[-1].get('name', ''),
        })
    # newest first
    summaries.sort(key=lambda r: r['ts_start'], reverse=True)
    return summaries[:limit]
