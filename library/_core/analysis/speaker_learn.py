"""Bayesian posterior updates for speaker-stance reliability.

Analogue of :mod:`heuristic_learn` one level up. Each row in
``speaker_profiles`` carries a Beta(α, β) posterior over "signals
sourced from this speaker translated into correct directional calls".

Every time the analytical path grounds a decision in a speaker's
stance *and* the associated market resolves, we log the outcome and
update the posterior. Over time, speakers whose quotes consistently
precede winning calls rise to the top of any speaker-weighted ranking;
speakers whose stances don't translate into P&L sink.

The ``stance`` field on each application row is kept so callers can
slice "Powell, hawkish only" or "Lagarde, dovish only" posteriors
offline without us committing to that schema now — the coarse
per-speaker posterior is the production signal.
"""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger('mentions')


# ── Reads ──────────────────────────────────────────────────────────────────

def get_counts(conn: sqlite3.Connection, speaker_id: int
               ) -> tuple[float, float] | None:
    """Return ``(alpha, beta)`` for *speaker_id*, or None if missing."""
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


def posterior_p(alpha: float, beta: float) -> float:
    """Posterior mean — thin re-export of the heuristic_learn helper."""
    from library._core.analysis.heuristic_learn import posterior_p as _pp
    return _pp(alpha, beta)


def posterior_ci(alpha: float, beta: float, *,
                 z: float = 1.96) -> tuple[float, float]:
    """Wilson-score CI — thin re-export of the heuristic_learn helper."""
    from library._core.analysis.heuristic_learn import posterior_ci as _ci
    return _ci(alpha, beta, z=z)


def decayed_counts(conn: sqlite3.Connection, speaker_id: int, *,
                   half_life_days: float | None = None,
                   ) -> tuple[float, float, int]:
    """Time-decayed (α, β, n) for *speaker_id* — mirror of the
    heuristic helper. See :mod:`library._core.analysis.time_decay`.
    """
    from library._core.analysis.time_decay import (
        DEFAULT_HALF_LIFE_DAYS, decayed_counts as _dc,
    )
    hl = DEFAULT_HALF_LIFE_DAYS if half_life_days is None else half_life_days
    return _dc(conn, table='speaker_stance_applications',
               id_col='speaker_profile_id', record_id=speaker_id,
               half_life_days=hl)


def top_confident_speakers(conn: sqlite3.Connection, *, limit: int = 10,
                           min_applications: int = 3,
                           half_life_days: float | None = None,
                           ) -> list[dict]:
    """Return speakers ranked by posterior-CI lower bound.

    Only speakers with at least *min_applications* recorded outcomes
    are returned. Ranking by CI lower bound (not posterior mean)
    ensures well-evidenced speakers beat lucky one-shots.

    When *half_life_days* is set (v0.14.2), α/β are recomputed from
    the audit log with exponential decay so stale track records fade.
    """
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
            a, b, _n_decay = decayed_counts(
                conn, int(sid), half_life_days=half_life_days)
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        scored.append({
            'id':              int(sid),
            'canonical_name':  name,
            'speaker_type':    stype,
            'domain':          domain,
            'alpha':           float(a),
            'beta':            float(b),
            'n_applications':  int(n),
            'posterior_p':     round(p, 4),
            'ci_low':          round(lo, 4),
            'ci_high':         round(hi, 4),
        })
    scored.sort(key=lambda r: r['ci_low'], reverse=True)
    return scored[:limit]


# ── Writes ─────────────────────────────────────────────────────────────────

def record_speaker_application(
    conn: sqlite3.Connection, speaker_id: int, *,
    outcome: int,
    stance: str | None = None,
    predicted_direction: str | None = None,
    market_ticker: str | None = None,
    case_id: int | None = None,
    note: str | None = None,
    regime: str | None = None,
) -> bool:
    """Log an application and update the Beta posterior.

    Wrapped in a single transaction so audit and posterior can never
    diverge. Returns ``True`` on success, ``False`` if the speaker is
    missing, raises :class:`ValueError` on invalid outcome.
    """
    if outcome not in (0, 1):
        raise ValueError(f'outcome must be 0 or 1, got {outcome!r}')
    try:
        row = conn.execute(
            'SELECT id FROM speaker_profiles WHERE id = ?', (speaker_id,),
        ).fetchone()
        if not row:
            log.debug('record_speaker_application: speaker %s missing',
                      speaker_id)
            return False
        conn.execute(
            '''INSERT INTO speaker_stance_applications
               (speaker_profile_id, stance, predicted_direction, outcome,
                market_ticker, case_id, note, regime)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (speaker_id, stance, predicted_direction, int(outcome),
             market_ticker, case_id, note, regime),
        )
        if outcome == 1:
            conn.execute(
                'UPDATE speaker_profiles SET alpha = alpha + 1.0, '
                '    updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (speaker_id,),
            )
        else:
            conn.execute(
                'UPDATE speaker_profiles SET beta = beta + 1.0, '
                '    updated_at = CURRENT_TIMESTAMP WHERE id = ?',
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
    """Reset α / β to Beta(1, 1) prior.

    Admin tool — used when a speaker's role / mandate changes and the
    old outcome history no longer applies (e.g. Fed chair rotation).
    """
    try:
        conn.execute(
            'UPDATE speaker_profiles SET alpha = 1.0, beta = 1.0, '
            '    updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (speaker_id,),
        )
        conn.commit()
        return True
    except sqlite3.Error as exc:
        log.debug('reset_posterior failed: %s', exc)
        return False


def posterior_by_stance(
    conn: sqlite3.Connection, speaker_id: int,
) -> dict[str, dict]:
    """Offline slicer — recompute α/β conditioned on stance.

    Walks the application log for *speaker_id* and returns
    ``{stance: {alpha, beta, n, posterior_p, ci_low, ci_high}}`` for
    each distinct stance value, starting from the Beta(1, 1) prior.

    This is a *read-only* recomputation; it does not touch
    ``speaker_profiles``. Use it to ask "is Powell-hawkish reliable
    even though Powell-overall posterior is mediocre?" without
    committing the per-stance schema to stone.
    """
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
            'alpha':        a,
            'beta':         b,
            'n':            len(outcomes),
            'posterior_p':  round(p, 4),
            'ci_low':       round(lo, 4),
            'ci_high':      round(hi, 4),
        }
    return out
