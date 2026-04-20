"""Bayesian posterior updates for heuristic confidence."""
from __future__ import annotations

import logging
import math
import sqlite3

from mentions_domain.posteriors.time_decay import DEFAULT_HALF_LIFE_DAYS, decayed_counts as _decayed_counts

log = logging.getLogger('mentions')


def get_counts(conn: sqlite3.Connection, heuristic_id: int) -> tuple[float, float] | None:
    try:
        row = conn.execute(
            'SELECT alpha, beta FROM heuristics WHERE id = ?',
            (heuristic_id,),
        ).fetchone()
    except sqlite3.Error as exc:
        log.debug('get_counts failed: %s', exc)
        return None
    if not row:
        return None
    return (float(row[0] or 1.0), float(row[1] or 1.0))


def posterior_p(alpha: float, beta: float) -> float:
    total = float(alpha) + float(beta)
    if total <= 0:
        return 0.5
    return float(alpha) / total


def posterior_ci(alpha: float, beta: float, *, z: float = 1.96) -> tuple[float, float]:
    successes = max(0.0, float(alpha) - 1.0)
    failures = max(0.0, float(beta) - 1.0)
    n = successes + failures
    if n <= 0:
        return (0.0, 1.0)
    p_hat = successes / n
    denom = 1.0 + (z * z) / n
    centre = (p_hat + (z * z) / (2.0 * n)) / denom
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + (z * z) / (4 * n * n)) / denom)
    lo = max(0.0, centre - half)
    hi = min(1.0, centre + half)
    return (lo, hi)


def decayed_counts(
    conn: sqlite3.Connection,
    heuristic_id: int,
    *,
    half_life_days: float | None = None,
) -> tuple[float, float, int]:
    hl = DEFAULT_HALF_LIFE_DAYS if half_life_days is None else half_life_days
    return _decayed_counts(
        conn,
        table='heuristic_applications',
        id_col='heuristic_id',
        record_id=heuristic_id,
        half_life_days=hl,
    )


def top_confident(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
    min_applications: int = 3,
    half_life_days: float | None = None,
) -> list[dict]:
    try:
        rows = conn.execute(
            '''SELECT h.id, h.heuristic_text, h.heuristic_type, h.market_type,
                      h.alpha, h.beta,
                      (SELECT COUNT(*) FROM heuristic_applications a
                        WHERE a.heuristic_id = h.id) AS n
                 FROM heuristics h''',
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('top_confident query failed: %s', exc)
        return []

    scored: list[dict] = []
    for r in rows:
        hid, text, htype, mtype, a, b, n = r
        if (n or 0) < min_applications:
            continue
        if half_life_days is not None:
            a, b, _ = decayed_counts(conn, int(hid), half_life_days=half_life_days)
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        scored.append({
            'id': int(hid),
            'heuristic_text': text,
            'heuristic_type': htype,
            'market_type': mtype,
            'alpha': float(a),
            'beta': float(b),
            'n_applications': int(n),
            'posterior_p': round(p, 4),
            'ci_low': round(lo, 4),
            'ci_high': round(hi, 4),
        })
    scored.sort(key=lambda r: r['ci_low'], reverse=True)
    return scored[:limit]


def record_application(
    conn: sqlite3.Connection,
    heuristic_id: int,
    *,
    outcome: int,
    predicted_direction: str | None = None,
    market_ticker: str | None = None,
    case_id: int | None = None,
    note: str | None = None,
    regime: str | None = None,
) -> bool:
    if outcome not in (0, 1):
        raise ValueError(f'outcome must be 0 or 1, got {outcome!r}')
    try:
        row = conn.execute('SELECT id FROM heuristics WHERE id = ?', (heuristic_id,)).fetchone()
        if not row:
            log.debug('record_application: heuristic %s missing', heuristic_id)
            return False
        conn.execute(
            '''INSERT INTO heuristic_applications
               (heuristic_id, predicted_direction, outcome,
                market_ticker, case_id, note, regime)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (heuristic_id, predicted_direction, int(outcome), market_ticker, case_id, note, regime),
        )
        if outcome == 1:
            conn.execute(
                'UPDATE heuristics SET alpha = alpha + 1.0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (heuristic_id,),
            )
        else:
            conn.execute(
                'UPDATE heuristics SET beta = beta + 1.0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (heuristic_id,),
            )
        conn.commit()
        return True
    except sqlite3.Error as exc:
        log.debug('record_application failed: %s', exc)
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return False


def reset_posterior(conn: sqlite3.Connection, heuristic_id: int) -> bool:
    try:
        conn.execute(
            'UPDATE heuristics SET alpha = 1.0, beta = 1.0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (heuristic_id,),
        )
        conn.commit()
        return True
    except sqlite3.Error as exc:
        log.debug('reset_posterior failed: %s', exc)
        return False


def posterior_by_regime(conn: sqlite3.Connection, heuristic_id: int) -> dict[str, dict]:
    try:
        rows = conn.execute(
            '''SELECT regime, outcome FROM heuristic_applications
                WHERE heuristic_id = ?''',
            (heuristic_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('posterior_by_regime failed: %s', exc)
        return {}

    buckets: dict[str, list[int]] = {}
    for regime, outcome in rows:
        key = regime or ''
        buckets.setdefault(key, []).append(int(outcome))

    out: dict[str, dict] = {}
    for regime, outcomes in buckets.items():
        wins = sum(outcomes)
        losses = len(outcomes) - wins
        a = 1.0 + wins
        b = 1.0 + losses
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        out[regime] = {
            'alpha': a,
            'beta': b,
            'n': len(outcomes),
            'posterior_p': round(p, 4),
            'ci_low': round(lo, 4),
            'ci_high': round(hi, 4),
        }
    return out


def top_confident_for_regime(
    conn: sqlite3.Connection,
    regime: str,
    *,
    limit: int = 10,
    min_applications: int = 3,
) -> list[dict]:
    try:
        rows = conn.execute(
            '''SELECT h.id, h.heuristic_text, h.heuristic_type, h.market_type,
                      SUM(CASE WHEN a.outcome = 1 THEN 1 ELSE 0 END) AS wins,
                      SUM(CASE WHEN a.outcome = 0 THEN 1 ELSE 0 END) AS losses,
                      COUNT(a.id) AS n
                 FROM heuristics h
                 JOIN heuristic_applications a
                      ON a.heuristic_id = h.id AND a.regime = ?
                GROUP BY h.id''',
            (regime,),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('top_confident_for_regime failed: %s', exc)
        return []

    scored: list[dict] = []
    for hid, text, htype, mtype, wins, losses, n in rows:
        if (n or 0) < min_applications:
            continue
        a = 1.0 + float(wins or 0)
        b = 1.0 + float(losses or 0)
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        scored.append({
            'id': int(hid),
            'heuristic_text': text,
            'heuristic_type': htype,
            'market_type': mtype,
            'alpha': a,
            'beta': b,
            'n_applications': int(n),
            'posterior_p': round(p, 4),
            'ci_low': round(lo, 4),
            'ci_high': round(hi, 4),
        })
    scored.sort(key=lambda r: r['ci_low'], reverse=True)
    return scored[:limit]


def record_case_outcomes(conn: sqlite3.Connection, case_id: int, outcome: int) -> int:
    try:
        hids = [
            row[0]
            for row in conn.execute(
                'SELECT heuristic_id FROM case_principles WHERE case_id = ?',
                (case_id,),
            ).fetchall()
        ]
    except sqlite3.Error as exc:
        log.debug('record_case_outcomes lookup failed: %s', exc)
        return 0
    count = 0
    for hid in hids:
        if record_application(conn, hid, outcome=outcome, case_id=case_id):
            count += 1
    return count
