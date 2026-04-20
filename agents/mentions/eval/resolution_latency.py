"""Resolution-latency analytics (v0.14.7 — D1).

A third axis for heuristic evaluation alongside the posterior mean
(how often does it work?) and the counterfactual lift (does it add
signal?). This one asks: **when** does a heuristic win or lose?

Given ``decision_cases.created_at`` and the new
``decision_cases.outcome_resolved_at`` (v10), for each heuristic we
compute the time elapsed between decision and market resolution,
grouped by win/loss. A heuristic whose winning resolutions cluster
in 1-3 days but whose losing resolutions stretch across weeks is
telling you something the posterior mean hides: it's good for
short-horizon calls, misleading for longer ones.

Writers should set ``outcome_resolved_at`` at the same moment they
write ``outcome``. :func:`set_case_outcome` is the canonical
helper — it wraps both writes in one transaction and preserves the
audit invariant ``outcome IS NULL ↔ outcome_resolved_at IS NULL``.

Read helpers:

* :func:`case_latency_days(conn, case_id)` — one case.
* :func:`heuristic_latency_stats(conn, heuristic_id)` — aggregate over
  every case linked to the heuristic via ``case_principles``. Returns
  ``{win: {n, mean, median}, loss: {...}}`` in days.

Both are read-only and skip cases without both timestamps. No
dependencies beyond the stdlib.
"""
from __future__ import annotations

import logging
import sqlite3
import statistics
from datetime import datetime, timezone

log = logging.getLogger('mentions')


# ── Write helper ──────────────────────────────────────────────────────────

def set_case_outcome(conn: sqlite3.Connection, case_id: int, outcome: int,
                      *, resolved_at: str | None = None) -> bool:
    """Atomically set ``outcome`` and ``outcome_resolved_at`` on a case.

    *resolved_at* defaults to ``datetime.now(UTC).isoformat()``.
    Use this wrapper rather than a raw ``UPDATE`` so the two columns
    stay in sync. Returns False if the case is missing.
    """
    if outcome not in (0, 1):
        raise ValueError(f'outcome must be 0 or 1, got {outcome!r}')
    ts = resolved_at or datetime.now(timezone.utc).isoformat()
    try:
        cur = conn.execute(
            'UPDATE decision_cases SET outcome = ?, outcome_resolved_at = ? '
            'WHERE id = ?',
            (int(outcome), ts, case_id),
        )
        if cur.rowcount == 0:
            return False
        conn.commit()
        return True
    except sqlite3.Error as exc:
        log.debug('set_case_outcome failed: %s', exc)
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return False


# ── Read helpers ──────────────────────────────────────────────────────────

def _parse_ts(s: str | None) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    t = s.strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        # Allow space-separated SQLite default.
        if len(t) == 19 and t[10] == ' ':
            try:
                dt = datetime.fromisoformat(t.replace(' ', 'T', 1))
            except ValueError:
                return None
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def case_latency_days(conn: sqlite3.Connection, case_id: int
                       ) -> float | None:
    """Return days between ``created_at`` and ``outcome_resolved_at``.

    None when either column is missing / unparseable, or when
    resolved_at predates created_at (corrupt row).
    """
    try:
        row = conn.execute(
            'SELECT created_at, outcome_resolved_at FROM decision_cases '
            'WHERE id = ?', (case_id,),
        ).fetchone()
    except sqlite3.Error as exc:
        log.debug('case_latency_days failed: %s', exc)
        return None
    if not row:
        return None
    a, b = _parse_ts(row[0]), _parse_ts(row[1])
    if a is None or b is None:
        return None
    delta = (b - a).total_seconds() / 86400.0
    if delta < 0:
        return None
    return delta


def heuristic_latency_stats(conn: sqlite3.Connection, heuristic_id: int
                             ) -> dict:
    """Aggregate win/loss latency for one heuristic across its cases.

    Returns::

        {
            'win':  {'n': int, 'mean': float, 'median': float},
            'loss': {'n': int, 'mean': float, 'median': float},
        }

    Missing group → ``{'n': 0, 'mean': None, 'median': None}``.
    """
    try:
        rows = conn.execute(
            '''SELECT dc.outcome, dc.created_at, dc.outcome_resolved_at
                 FROM decision_cases dc
                 JOIN case_principles cp ON cp.case_id = dc.id
                WHERE cp.heuristic_id = ?
                  AND dc.outcome IS NOT NULL
                  AND dc.outcome_resolved_at IS NOT NULL''',
            (heuristic_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('heuristic_latency_stats failed: %s', exc)
        return _empty_stats()

    wins: list[float] = []
    losses: list[float] = []
    for outcome, created, resolved in rows:
        a, b = _parse_ts(created), _parse_ts(resolved)
        if a is None or b is None:
            continue
        days = (b - a).total_seconds() / 86400.0
        if days < 0:
            continue
        (wins if outcome == 1 else losses).append(days)

    return {'win': _summarise(wins), 'loss': _summarise(losses)}


def _summarise(xs: list[float]) -> dict:
    if not xs:
        return {'n': 0, 'mean': None, 'median': None}
    return {
        'n':      len(xs),
        'mean':   round(statistics.fmean(xs), 4),
        'median': round(statistics.median(xs), 4),
    }


def _empty_stats() -> dict:
    return {'win': _summarise([]), 'loss': _summarise([])}
