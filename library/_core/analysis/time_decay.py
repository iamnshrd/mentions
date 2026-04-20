"""Shared time-decay helper for Bayesian posterior recomputation.

Pre-v0.14.2 the α/β counters on ``heuristics`` and ``speaker_profiles``
incremented monotonically — every outcome weighed the same forever.
That's wrong in a non-stationary world: a rate-setting regime from
five years ago is not evidence about today's Fed. A heuristic that
was 80 % accurate in 2020 and 40 % accurate since 2024 deserves to
look mediocre, not strong.

Rather than decay the *stored* α/β at write time (which erases
information and bakes the half-life into state), we recompute them
at read time by walking the audit log with an exponential weight:

    weight_i = exp(-ln(2) × Δt_i / half_life_days)
    α = 1 + Σ outcome_i × weight_i         (plus Beta(1, 1) prior)
    β = 1 + Σ (1 - outcome_i) × weight_i

Downstream consumers (``top_confident``, ``top_confident_speakers``)
gain a ``half_life_days`` kwarg; omitting it falls back to the
stored cumulative α/β (infinite half-life — the original behaviour).
"""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime, timezone

log = logging.getLogger('mentions')


DEFAULT_HALF_LIFE_DAYS = 180.0
_SECONDS_PER_DAY = 86_400.0


def _parse_ts(ts: str | None) -> float | None:
    """Best-effort parse of the ``applied_at`` strings SQLite produces.

    SQLite's ``CURRENT_TIMESTAMP`` emits ``'YYYY-MM-DD HH:MM:SS'`` in
    UTC. We also accept ISO-8601 with a ``T`` separator and optional
    ``'Z'`` suffix so callers that insert their own timestamps aren't
    forced into the SQLite format.
    """
    if not ts:
        return None
    s = str(ts).strip().replace('T', ' ').rstrip('Z')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).replace(
                tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def _weight(applied_at: str | None, now_ts: float,
            half_life_days: float) -> float:
    """Return the exponential-decay weight for a row at *applied_at*.

    Rows with unparseable timestamps fall back to weight 1.0 — we'd
    rather overweight mystery data than silently drop it.
    """
    if half_life_days <= 0:
        return 1.0  # no decay requested
    t = _parse_ts(applied_at)
    if t is None:
        return 1.0
    delta_days = max(0.0, (now_ts - t) / _SECONDS_PER_DAY)
    lam = math.log(2.0) / half_life_days
    return math.exp(-lam * delta_days)


def decayed_counts_from_rows(rows: list[tuple], *,
                             half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
                             now: datetime | None = None
                             ) -> tuple[float, float, int]:
    """Pure helper — reduce ``[(outcome, applied_at), ...]`` to (α, β, n).

    Includes the Beta(1, 1) prior so the return value is directly
    usable with :func:`posterior_p` / :func:`posterior_ci` from
    :mod:`heuristic_learn`.
    """
    now_ts = (now or datetime.now(timezone.utc)).timestamp()
    alpha_adds = 0.0
    beta_adds  = 0.0
    for outcome, applied_at in rows:
        w = _weight(applied_at, now_ts, half_life_days)
        if int(outcome) == 1:
            alpha_adds += w
        else:
            beta_adds += w
    return (1.0 + alpha_adds, 1.0 + beta_adds, len(rows))


def decayed_counts(conn: sqlite3.Connection, *,
                   table: str, id_col: str, record_id: int,
                   half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
                   now: datetime | None = None
                   ) -> tuple[float, float, int]:
    """Walk *table* for *record_id* and compute decayed (α, β, n).

    *table* must carry ``outcome`` and ``applied_at`` columns and
    filter by ``id_col = ?`` — the same shape for
    ``heuristic_applications`` and ``speaker_stance_applications``.
    """
    try:
        rows = conn.execute(
            f'SELECT outcome, applied_at FROM {table} WHERE {id_col} = ?',
            (record_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('decayed_counts(%s) failed: %s', table, exc)
        return (1.0, 1.0, 0)
    return decayed_counts_from_rows(
        rows, half_life_days=half_life_days, now=now,
    )
