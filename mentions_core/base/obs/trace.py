"""Trace propagation — one trace_id per logical request."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

log = logging.getLogger('mentions')

_current_trace: ContextVar[str] = ContextVar('mentions_trace_id', default='')


def new_trace() -> str:
    tid = uuid.uuid4().hex
    _current_trace.set(tid)
    return tid


def current_trace() -> str:
    return _current_trace.get()


@contextmanager
def with_trace(trace_id: str | None = None):
    tid = trace_id or uuid.uuid4().hex
    token = _current_trace.set(tid)
    try:
        yield tid
    finally:
        _current_trace.reset(token)


def _default_trace_path() -> Path:
    from mentions_core.base.config import TRACE_LOG
    return TRACE_LOG


_write_lock = threading.Lock()


def trace_event(name: str, **fields) -> None:
    try:
        event = {
            'ts': time.time(),
            'trace_id': _current_trace.get(),
            'name': name,
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
    except Exception as exc:  # pragma: no cover
        log.debug('trace_event unexpected failure: %s', exc)


def iter_events(path: Path | None = None,
                limit: int | None = None) -> list[dict]:
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
    if not trace_id:
        return []
    newest_first = iter_events(path=path, limit=None)
    oldest_first = list(reversed(newest_first))
    return [r for r in oldest_first if r.get('trace_id') == trace_id]


def list_traces(path: Path | None = None,
                limit: int = 20) -> list[dict]:
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
        ts_end = events[-1].get('ts', ts_start)
        summaries.append({
            'trace_id': tid,
            'ts_start': ts_start,
            'ts_end': ts_end,
            'duration_ms': round((ts_end - ts_start) * 1000.0, 3),
            'n_events': len(events),
            'first': events[0].get('name', ''),
            'last': events[-1].get('name', ''),
        })
    summaries.sort(key=lambda r: r['ts_start'], reverse=True)
    return summaries[:limit]
