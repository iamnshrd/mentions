from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mentions_core.base.config import WORKSPACE

log = logging.getLogger('mentions')


TRACE_PATH = Path(
    os.getenv('MENTIONS_TRACE_LOG', str(WORKSPACE / 'mentions' / 'trace.jsonl'))
)


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def trace_log(stage: str, run_id: str = '', **fields: Any) -> None:
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'stage': stage,
            'run_id': run_id,
        }
        for key, value in fields.items():
            payload[key] = _safe(value)
        with TRACE_PATH.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + '\n')
    except Exception as exc:
        log.debug('trace_log failed for stage=%s run_id=%s: %s', stage, run_id, exc)
        return


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    return str(value)
