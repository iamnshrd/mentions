"""Event-date recency boost for retrieval-domain scoring."""
from __future__ import annotations

import math
from datetime import datetime, timezone

DEFAULT_HALF_LIFE_DAYS = 365.0
RECENCY_FLOOR = 0.1


def _parse_event_date(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    s = s.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s[:10], '%Y-%m-%d')
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def recency_weight(
    event_date: str | None,
    *,
    now: datetime | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    if half_life_days is None or half_life_days <= 0:
        return 1.0
    dt = _parse_event_date(event_date)
    if dt is None:
        return 1.0
    now_dt = now if now is not None else datetime.now(timezone.utc)
    delta_days = (now_dt - dt).total_seconds() / 86400.0
    if delta_days <= 0:
        return 1.0
    weight = math.exp(-math.log(2.0) * delta_days / half_life_days)
    return max(RECENCY_FLOOR, weight)


def apply_recency(hits, *, half_life_days: float | None = DEFAULT_HALF_LIFE_DAYS, now: datetime | None = None) -> None:
    if half_life_days is None or half_life_days <= 0:
        for h in hits:
            setattr(h, 'score_recency', 1.0)
        return
    now_dt = now if now is not None else datetime.now(timezone.utc)
    for h in hits:
        w = recency_weight(getattr(h, 'event_date', '') or '', now=now_dt, half_life_days=half_life_days)
        setattr(h, 'score_recency', round(w, 4))
        h.score_final *= w
