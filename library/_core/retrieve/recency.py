"""Event-date recency boost for hybrid retrieval (v0.14.7 — T4).

The retrieval pipeline (hybrid.py) scores chunks by lexical (BM25) +
semantic (embedding) + reliability (speaker posterior). Nothing so
far considered *when* the source transcript was spoken. For
forward-looking prediction markets this is often the dominant signal:
a 2019 Powell speech on policy normalisation has almost no predictive
value for a 2025 rate-cut market, however high its BM25 score.

T4 adds an exponential recency multiplier on ``transcript_documents.
event_date``. Same shape as the time_decay helper used for posterior
α/β (v0.14.2) — one half-life parameter, pure math:

    weight = exp(-ln(2) * days_since_event / half_life_days)

Default half-life is 365 days (a one-year-old speech gets half the
weight of today's). Knobable per-call; pass ``half_life_days=None``
to disable the boost entirely.

Design choices:

* **Multiplicative**, not additive — keeps RRF-fused scores on the
  same scale while scaling relative ranking. A 0.5 recency weight is
  the same effect on a 0.1 fused score as on a 0.9 one.
* **Floor at 0.1** — we don't drive ancient content to literally
  zero. There may be exactly one seminal pre-2010 speech that still
  matters; we want BM25 to be able to promote it.
* **Unparseable / missing dates** — weight 1.0 (neutral). Corpora
  with no ``event_date`` metadata aren't penalised.
* **Future dates** — weight 1.0. Scheduled-but-not-spoken transcripts
  (unusual but not impossible in our pipeline) shouldn't be
  up-weighted for time travel.

Returns a ``{chunk_id: weight}`` dict that callers apply in place,
mirroring the reliability-weighting pattern. Tested in isolation
and via hybrid integration.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

log = logging.getLogger('mentions')

DEFAULT_HALF_LIFE_DAYS = 365.0
RECENCY_FLOOR = 0.1


def _parse_event_date(value: str | None) -> datetime | None:
    """Best-effort ISO / date-only parser → aware UTC datetime."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Normalise common shapes.
    s = s.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Try pure date YYYY-MM-DD.
        try:
            dt = datetime.strptime(s[:10], '%Y-%m-%d')
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def recency_weight(event_date: str | None, *,
                   now: datetime | None = None,
                   half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
                   ) -> float:
    """Return a multiplicative recency weight in ``[RECENCY_FLOOR, 1.0]``.

    Exponential decay from ``event_date`` to *now*. Neutral (1.0) for
    missing / unparseable / future dates so malformed metadata never
    penalises a chunk.
    """
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


def apply_recency(hits, *,
                  half_life_days: float | None = DEFAULT_HALF_LIFE_DAYS,
                  now: datetime | None = None) -> None:
    """In-place: multiply ``hit.score_final`` by the per-hit recency weight.

    Also attaches ``hit.score_recency`` for introspection. A
    ``half_life_days`` of ``None`` or ``0`` short-circuits (no
    modification, weights recorded as 1.0) so callers can toggle via
    the same code path used in hybrid.
    """
    if half_life_days is None or half_life_days <= 0:
        for h in hits:
            setattr(h, 'score_recency', 1.0)
        return
    now_dt = now if now is not None else datetime.now(timezone.utc)
    for h in hits:
        w = recency_weight(getattr(h, 'event_date', '') or '',
                           now=now_dt, half_life_days=half_life_days)
        setattr(h, 'score_recency', round(w, 4))
        h.score_final *= w
