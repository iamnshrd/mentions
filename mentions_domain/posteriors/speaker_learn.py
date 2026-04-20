"""Bayesian posterior updates for speaker-stance reliability."""
from __future__ import annotations

import logging
import sqlite3

from mentions_domain.posteriors.heuristic_learn import posterior_ci, posterior_p
from mentions_domain.posteriors.time_decay import DEFAULT_HALF_LIFE_DAYS, decayed_counts as _decayed_counts

log = logging.getLogger('mentions')


def get_counts(conn: sqlite3.Connection, speaker_id: int) -> tuple[float, float] | None:
    try:
        row = conn.execute(
            'SELECT alpha, beta FROM speaker_profiles WHERE id = ?',
            (speaker_id,),
        ).fetchone()
    except sqlite3.Error as exc:
        log.debug('get_counts failed: %s', exc)
        return None
    if not row:
        return None
    return (float(row[0] or 1.0), float(row[1] or 1.0))


def decayed_counts(
    conn: sqlite3.Connection,
    speaker_id: int,
    *,
    half_life_days: float | None = None,
) -> tuple[float, float, int]:
    hl = DEFAULT_HALF_LIFE_DAYS if half_life_days is None else half_life_days
    return _decayed_counts(
        conn,
        table='speaker_stance_applications',
        id_col='speaker_profile_id',
        record_id=speaker_id,
        half_life_days=hl,
    )


def top_confident_speakers(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
    min_applications: int = 3,
    half_life_days: float | None = None,
) -> list[dict]:
    try:
        rows = conn.execute(
            '''SELECT s.id, s.canonical_name, s.speaker_type, s.domain,
                      s.alpha, s.beta,
                      (SELECT COUNT(*) FROM speaker_stance_applications a
                        WHERE a.speaker_profile_id = s.id) AS n
                 FROM speaker_profiles s''',
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('top_confident_speakers failed: %s', exc)
        return []

    scored: list[dict] = []
    for r in rows:
        sid, name, stype, domain, a, b, n = r
        if (n or 0) < min_applications:
            continue
        if half_life_days is not None:
            a, b, _ = decayed_counts(conn, int(sid), half_life_days=half_life_days)
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        scored.append({
            'id': int(sid),
            'canonical_name': name,
            'speaker_type': stype,
            'domain': domain,
            'alpha': float(a),
            'beta': float(b),
            'n_applications': int(n),
            'posterior_p': round(p, 4),
            'ci_low': round(lo, 4),
            'ci_high': round(hi, 4),
        })
    scored.sort(key=lambda r: r['ci_low'], reverse=True)
    return scored[:limit]


def record_speaker_application(
    conn: sqlite3.Connection,
    speaker_id: int,
    *,
    outcome: int,
    stance: str | None = None,
    predicted_direction: str | None = None,
    market_ticker: str | None = None,
    case_id: int | None = None,
    note: str | None = None,
    regime: str | None = None,
) -> bool:
    if outcome not in (0, 1):
        raise ValueError(f'outcome must be 0 or 1, got {outcome!r}')
    try:
        row = conn.execute('SELECT id FROM speaker_profiles WHERE id = ?', (speaker_id,)).fetchone()
        if not row:
            log.debug('record_speaker_application: speaker %s missing', speaker_id)
            return False
        conn.execute(
            '''INSERT INTO speaker_stance_applications
               (speaker_profile_id, stance, predicted_direction, outcome,
                market_ticker, case_id, note, regime)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (speaker_id, stance, predicted_direction, int(outcome), market_ticker, case_id, note, regime),
        )
        if outcome == 1:
            conn.execute(
                'UPDATE speaker_profiles SET alpha = alpha + 1.0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (speaker_id,),
            )
        else:
            conn.execute(
                'UPDATE speaker_profiles SET beta = beta + 1.0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (speaker_id,),
            )
        conn.commit()
        return True
    except sqlite3.Error as exc:
        log.debug('record_speaker_application failed: %s', exc)
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return False


def reset_posterior(conn: sqlite3.Connection, speaker_id: int) -> bool:
    try:
        conn.execute(
            'UPDATE speaker_profiles SET alpha = 1.0, beta = 1.0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (speaker_id,),
        )
        conn.commit()
        return True
    except sqlite3.Error as exc:
        log.debug('reset_posterior failed: %s', exc)
        return False


def posterior_by_stance(conn: sqlite3.Connection, speaker_id: int) -> dict[str, dict]:
    try:
        rows = conn.execute(
            '''SELECT stance, outcome FROM speaker_stance_applications
                WHERE speaker_profile_id = ?''',
            (speaker_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('posterior_by_stance failed: %s', exc)
        return {}

    buckets: dict[str, list[int]] = {}
    for stance, outcome in rows:
        key = stance or ''
        buckets.setdefault(key, []).append(int(outcome))

    out: dict[str, dict] = {}
    for stance, outcomes in buckets.items():
        wins = sum(outcomes)
        losses = len(outcomes) - wins
        a = 1.0 + wins
        b = 1.0 + losses
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        out[stance] = {
            'alpha': a,
            'beta': b,
            'n': len(outcomes),
            'posterior_p': round(p, 4),
            'ci_low': round(lo, 4),
            'ci_high': round(hi, 4),
        }
    return out
