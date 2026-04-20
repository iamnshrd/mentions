"""Shared time-decay helpers for posterior recomputation."""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime, timezone

log = logging.getLogger('mentions')

DEFAULT_HALF_LIFE_DAYS = 180.0
_SECONDS_PER_DAY = 86_400.0


def _parse_ts(ts: str | None) -> float | None:
    if not ts:
        return None
    s = str(ts).strip().replace('T', ' ').rstrip('Z')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def _weight(applied_at: str | None, now_ts: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        return 1.0
    t = _parse_ts(applied_at)
    if t is None:
        return 1.0
    delta_days = max(0.0, (now_ts - t) / _SECONDS_PER_DAY)
    lam = math.log(2.0) / half_life_days
    return math.exp(-lam * delta_days)


def decayed_counts_from_rows(
    rows: list[tuple],
    *,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    now: datetime | None = None,
) -> tuple[float, float, int]:
    now_ts = (now or datetime.now(timezone.utc)).timestamp()
    alpha_adds = 0.0
    beta_adds = 0.0
    for outcome, applied_at in rows:
        w = _weight(applied_at, now_ts, half_life_days)
        if int(outcome) == 1:
            alpha_adds += w
        else:
            beta_adds += w
    return (1.0 + alpha_adds, 1.0 + beta_adds, len(rows))


def decayed_counts(
    conn: sqlite3.Connection,
    *,
    table: str,
    id_col: str,
    record_id: int,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    now: datetime | None = None,
) -> tuple[float, float, int]:
    try:
        rows = conn.execute(
            f'SELECT outcome, applied_at FROM {table} WHERE {id_col} = ?',
            (record_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('decayed_counts(%s) failed: %s', table, exc)
        return (1.0, 1.0, 0)
    return decayed_counts_from_rows(rows, half_life_days=half_life_days, now=now)
