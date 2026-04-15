"""Shared base-layer utility functions."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

log = logging.getLogger('mentions_core')

_timing_ctx: threading.local = threading.local()
_BASE_THRESHOLDS = {
    'progress_repeat_stuck_threshold': 3,
}


@contextmanager
def timing_context():
    """Collect timings from ``@timed``-decorated functions."""
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
    """Decorator that records timing information for *stage*."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed_ms = (time.monotonic() - t0) * 1000
                _record_timing(stage, elapsed_ms)
                log.debug(
                    '%s completed in %.1f ms',
                    stage,
                    elapsed_ms,
                    extra={'stage': stage, 'elapsed_ms': round(elapsed_ms, 2)},
                )
        return wrapper
    return decorator


def now_iso():
    """Return the current UTC time as ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    """Read JSON from *path*, returning *default* on error."""
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


def save_json(path, data, ensure_ascii: bool = False, indent: int = 2):
    """Atomically write *data* as JSON."""
    import tempfile

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=ensure_ascii, indent=indent)
        os.replace(tmp, str(target))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def slugify(name: str) -> str:
    """Produce a filesystem-safe slug."""
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


def get_threshold(key: str, default=None):
    """Read a generic base threshold with env override support."""
    env_key = f'OPENCLAW_{key.upper()}'
    raw = os.environ.get(env_key)
    if raw is not None:
        for caster in (int, float):
            try:
                return caster(raw)
            except ValueError:
                continue
        return raw
    return _BASE_THRESHOLDS.get(key, default)


def load_dotenv_files(root: str | Path | None = None,
                      filenames: tuple[str, ...] = ('.env', '.env.local')) -> list[str]:
    """Load simple KEY=VALUE pairs from dotenv files if present.

    Existing environment variables are preserved and take precedence.
    Returns the list of loaded file paths.
    """
    base = Path(root or Path.cwd()).resolve()
    loaded: list[str] = []
    candidates = [base, *base.parents]
    for directory in candidates:
        found_here = False
        for name in filenames:
            path = directory / name
            if not path.exists() or not path.is_file():
                continue
            for raw_line in path.read_text(encoding='utf-8').splitlines():
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                os.environ[key] = _normalize_dotenv_value(value.strip())
            loaded.append(str(path))
            found_here = True
        if found_here:
            break
    return loaded


def _normalize_dotenv_value(value: str) -> str:
    """Normalize a dotenv value by trimming optional matching quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
