#!/usr/bin/env python3
"""Shared utility functions used across multiple modules."""
from __future__ import annotations

import json
import logging
import time
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

log = logging.getLogger('mentions')


# -- timing / observability ------------------------------------------------

_timing_ctx: threading.local = threading.local()


@contextmanager
def timing_context():
    """Context manager that collects ``@timed`` measurements.

    Usage::

        with timing_context() as timings:
            result = orchestrate(query)
        print(timings)   # {'fetch': 120.3, 'analyze': 45.1, ...}
    """
    prev = getattr(_timing_ctx, 'timings', None)
    _timing_ctx.timings = {}
    try:
        yield _timing_ctx.timings
    finally:
        _timing_ctx.timings = prev


def _record_timing(stage: str, elapsed_ms: float):
    timings = getattr(_timing_ctx, 'timings', None)
    if timings is not None:
        timings[stage] = round(elapsed_ms, 2)


def timed(stage: str):
    """Decorator that logs and records execution time for *stage*."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed_ms = (time.monotonic() - t0) * 1000
                _record_timing(stage, elapsed_ms)
                log.debug('%s completed in %.1f ms', stage,
                          elapsed_ms,
                          extra={'stage': stage, 'elapsed_ms': round(elapsed_ms, 2)})
        return wrapper
    return decorator


def now_iso():
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    """Read and parse a JSON file, returning *default* if it is missing or broken.

    If the file contains JSON ``null``, *default* is returned as well.
    """
    p = Path(path)
    if not p.exists():
        return default if default is not None else {}
    try:
        result = json.loads(p.read_text(encoding='utf-8'))
        if result is None:
            return default if default is not None else {}
        return result
    except (json.JSONDecodeError, OSError) as exc:
        log.warning('Failed to load %s: %s', path, exc)
        return default if default is not None else {}


def save_json(path, data, ensure_ascii=False, indent=2):
    """Atomically write *data* as pretty-printed JSON via tmp+rename."""
    import os, tempfile
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        os.replace(tmp, str(target))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_checkpoints(path):
    """Read a JSONL checkpoint file into a list of dicts."""
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def slugify(name):
    """Produce a filesystem-safe slug from *name*."""
    out = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (' ', '-', '_', '.'):
            out.append('-')
    slug = ''.join(out)
    while '--' in slug:
        slug = slug.replace('--', '-')
    return slug.strip('-')


def fts_query(text):
    """Build an OR-based FTS5 query from *text*."""
    max_tokens = get_threshold('fts_query_max_tokens', 8)
    words = [
        w
        for w in ''.join(
            ch if ch.isalnum() or ch.isspace() else ' ' for ch in text.lower()
        ).split()
        if len(w) >= 3
    ][:max_tokens]
    return ' OR '.join(words) if words else ''


_thresholds_cache: dict | None = None


def get_threshold(key: str, default=None):
    """Read a named threshold from thresholds.json (cached)."""
    global _thresholds_cache
    if _thresholds_cache is None:
        from agents.mentions.config import THRESHOLDS
        raw = load_json(THRESHOLDS, default={})
        _thresholds_cache = raw if isinstance(raw, dict) else {}
    return _thresholds_cache.get(key, default)
