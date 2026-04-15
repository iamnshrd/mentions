"""Structured JSON logging configuration for the local Mentions runtime.

Call ``setup()`` once at startup.  Every log record produced by the
configured logger hierarchies is formatted as a single-line JSON object
with keys: ``ts``, ``level``, ``logger``, ``msg``, and any ``extra``
fields passed via ``log.info("...", extra={...})``.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit each log record as a compact JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            'ts': datetime.fromtimestamp(record.created, tz=timezone.utc)
                         .isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        for key in ('user_id', 'request_id', 'stage', 'elapsed_ms'):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info and record.exc_info[1]:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup(level: int = logging.INFO):
    """Configure runtime loggers with JSON output to stderr."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    for name in ('mentions_core', 'mentions'):
        root = logging.getLogger(name)
        if root.handlers:
            continue
        root.addHandler(handler)
        root.setLevel(level)
