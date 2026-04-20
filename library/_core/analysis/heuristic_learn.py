"""Bayesian posterior updates for heuristic confidence.

Pre-v0.13 the ``heuristics.confidence`` column was set once at import
time and never changed — a dead number that drifted from reality as
the corpus of applied cases grew. v0.13 schema adds ``alpha`` /
``beta`` columns holding a Beta(α, β) posterior over "this heuristic
is borne out in practice", initialised Beta(1, 1) (uniform).

Every time the analytical path *applies* a heuristic to a real market
and that market resolves, :func:`record_application` logs the
outcome and updates the posterior:

* Success → α += 1
* Failure → β += 1

Downstream consumers use :func:`posterior_p` (= α / (α+β)) instead of
the static column. This is a textbook Bayesian-Bernoulli update with
a conjugate prior — cheap, online, and self-correcting: a heuristic
that gets repeatedly disproven asymptotically drops to near-0
confidence and bubbles out of the "top by posterior" ranking.

We also expose :func:`posterior_ci` — a Wilson-score interval that
provides a sample-size-aware confidence range. A brand-new heuristic
has a wide interval (uninformative), a heuristic applied 50 times
has a tight one. Callers can use the lower bound to *shrink* coarse
scores toward the prior when data is thin.
"""
from __future__ import annotations

import logging
import math
import sqlite3

log = logging.getLogger('mentions')


# ── Reads ──────────────────────────────────────────────────────────────────

def get_counts(conn: sqlite3.Connection, heuristic_id: int
               ) -> tuple[float, float] | None:
    """Return ``(alpha, beta)`` for *heuristic_id*, or None if missing."""
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
    """Posterior mean of Beta(α, β) — the Bayes-optimal point estimate.

    Equivalent to the empirical success rate when α = successes+1
    and β = failures+1 (Laplace smoothing falls out naturally from
    the Beta(1,1) prior).
    """
    total = float(alpha) + float(beta)
    if total <= 0:
        return 0.5
    return float(alpha) / total


def posterior_ci(alpha: float, beta: float, *,
                 z: float = 1.96) -> tuple[float, float]:
    """Wilson-score interval around the posterior mean.

    *z* is the standard-normal quantile; 1.96 ≈ 95%. Narrow CI means
    "we've observed enough to be sure"; wide CI means "new heuristic,
    trust sparingly". Returns ``(lo, hi)`` both clamped to [0, 1].

    The Wilson formulation handles the ``n → 0`` edge cleanly,
    unlike the naive Gaussian approximation which blows up at the
    extremes.
    """
    # Treat α−1 and β−1 as observed successes/failures (conjugate to
    # the Beta(1, 1) prior).
    successes = max(0.0, float(alpha) - 1.0)
    failures  = max(0.0, float(beta)  - 1.0)
    n = successes + failures
    if n <= 0:
        return (0.0, 1.0)
    p_hat = successes / n
    denom = 1.0 + (z * z) / n
    centre = (p_hat + (z * z) / (2.0 * n)) / denom
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + (z * z) / (4 * n * n))
            / denom)
    lo = max(0.0, centre - half)
    hi = min(1.0, centre + half)
    return (lo, hi)


def decayed_counts(conn: sqlite3.Connection, heuristic_id: int, *,
                   half_life_days: float | None = None,
                   ) -> tuple[float, float, int]:
    """Return time-decayed ``(α, β, n)`` for *heuristic_id*.

    Walks ``heuristic_applications`` and weights each row by
    ``exp(-ln(2) × Δt / half_life_days)``. A half-life of 180 days
    (default when omitted but not None) means a one-year-old outcome
    contributes ~0.25 the weight of a fresh one.

    Pass ``half_life_days=0`` to explicitly disable decay (useful for
    tests asserting the recomputation matches stored counts exactly).
    """
    from library._core.analysis.time_decay import (
        DEFAULT_HALF_LIFE_DAYS, decayed_counts as _dc,
    )
    hl = DEFAULT_HALF_LIFE_DAYS if half_life_days is None else half_life_days
    return _dc(conn, table='heuristic_applications',
               id_col='heuristic_id', record_id=heuristic_id,
               half_life_days=hl)


def top_confident(conn: sqlite3.Connection, *, limit: int = 10,
                  min_applications: int = 3,
                  half_life_days: float | None = None) -> list[dict]:
    """Return heuristics ranked by posterior mean, with shrinkage.

    Only heuristics with at least *min_applications* recorded
    applications are returned — otherwise a new heuristic with one
    lucky hit would rank above a 50-case heuristic with 40 hits.

    When *half_life_days* is set (v0.14.2) the α/β used for ranking
    are recomputed from the audit log with exponential decay, so a
    heuristic that was once accurate but has gone cold drops even
    though its cumulative stored counts look strong.
    """
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
        # When a half-life is set, recompute α/β from the audit log
        # rather than using the stored cumulative values.
        if half_life_days is not None:
            a, b, _n_decay = decayed_counts(
                conn, int(hid), half_life_days=half_life_days)
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        scored.append({
            'id':              int(hid),
            'heuristic_text':  text,
            'heuristic_type':  htype,
            'market_type':     mtype,
            'alpha':           float(a),
            'beta':            float(b),
            'n_applications':  int(n),
            'posterior_p':     round(p, 4),
            'ci_low':          round(lo, 4),
            'ci_high':         round(hi, 4),
        })
    # Rank by lower-bound of CI to favour well-evidenced heuristics.
    scored.sort(key=lambda r: r['ci_low'], reverse=True)
    return scored[:limit]


# ── Writes ─────────────────────────────────────────────────────────────────

def record_application(
    conn: sqlite3.Connection, heuristic_id: int, *,
    outcome: int,
    predicted_direction: str | None = None,
    market_ticker: str | None = None,
    case_id: int | None = None,
    note: str | None = None,
    regime: str | None = None,
) -> bool:
    """Log an application and update the Beta posterior.

    Wrapped in a single transaction so the audit row and the α/β
    update can never diverge. Returns ``True`` on success.
    """
    if outcome not in (0, 1):
        raise ValueError(f'outcome must be 0 or 1, got {outcome!r}')
    try:
        # Verify the heuristic exists (FK does this implicitly, but we
        # want a cleaner error than SQLITE_CONSTRAINT).
        row = conn.execute(
            'SELECT id FROM heuristics WHERE id = ?', (heuristic_id,),
        ).fetchone()
        if not row:
            log.debug('record_application: heuristic %s missing', heuristic_id)
            return False
        conn.execute(
            '''INSERT INTO heuristic_applications
               (heuristic_id, predicted_direction, outcome,
                market_ticker, case_id, note, regime)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (heuristic_id, predicted_direction, int(outcome),
             market_ticker, case_id, note, regime),
        )
        if outcome == 1:
            conn.execute(
                'UPDATE heuristics SET alpha = alpha + 1.0, '
                '    updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (heuristic_id,),
            )
        else:
            conn.execute(
                'UPDATE heuristics SET beta = beta + 1.0, '
                '    updated_at = CURRENT_TIMESTAMP WHERE id = ?',
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
    """Reset α / β back to the Beta(1, 1) prior.

    Admin tool — used when a heuristic's meaning changes (text edit)
    and the old outcome history no longer applies.
    """
    try:
        conn.execute(
            'UPDATE heuristics SET alpha = 1.0, beta = 1.0, '
            '    updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (heuristic_id,),
        )
        conn.commit()
        return True
    except sqlite3.Error as exc:
        log.debug('reset_posterior failed: %s', exc)
        return False


# ── Regime-conditioned posteriors (v0.14.4) ───────────────────────────────

def posterior_by_regime(
    conn: sqlite3.Connection, heuristic_id: int,
) -> dict[str, dict]:
    """Walk the audit log and return ``{regime: Beta stats}``.

    Starts from the Beta(1, 1) prior per regime bucket. The key is
    the literal ``regime`` string from the row (or ``''`` for
    regime-agnostic rows). Use this to ask "is heuristic X strong
    under high-vol but noise under low-vol?".

    Read-only — does not touch ``heuristics.alpha/beta``.
    """
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
            'alpha':        a,
            'beta':         b,
            'n':            len(outcomes),
            'posterior_p':  round(p, 4),
            'ci_low':       round(lo, 4),
            'ci_high':      round(hi, 4),
        }
    return out


def top_confident_for_regime(
    conn: sqlite3.Connection, regime: str, *,
    limit: int = 10, min_applications: int = 3,
) -> list[dict]:
    """Rank heuristics by their conditional posterior for *regime*.

    Only rows from ``heuristic_applications`` tagged with matching
    ``regime`` (exact string match) are counted. Untagged (NULL /
    empty) rows are *excluded* from conditional ranking — that's
    the point: a heuristic with only regime-agnostic history has no
    evidence for this specific regime and shouldn't surface.
    """
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
    for r in rows:
        hid, text, htype, mtype, wins, losses, n = r
        if (n or 0) < min_applications:
            continue
        a = 1.0 + float(wins or 0)
        b = 1.0 + float(losses or 0)
        p = posterior_p(a, b)
        lo, hi = posterior_ci(a, b)
        scored.append({
            'id':              int(hid),
            'heuristic_text':  text,
            'heuristic_type':  htype,
            'market_type':     mtype,
            'regime':          regime,
            'alpha':           a,
            'beta':            b,
            'n_applications':  int(n),
            'posterior_p':     round(p, 4),
            'ci_low':          round(lo, 4),
            'ci_high':         round(hi, 4),
        })
    scored.sort(key=lambda r: r['ci_low'], reverse=True)
    return scored[:limit]


# ── Batch helper ──────────────────────────────────────────────────────────

def record_case_outcomes(
    conn: sqlite3.Connection, case_id: int, outcome: int,
) -> int:
    """Record the same *outcome* for every heuristic linked to *case_id*.

    The v2 schema ties a decision_case to heuristics via the
    ``case_principles`` junction table. When a case resolves you
    typically know every supporting heuristic worked or every one
    failed together — this batches that update.

    Returns the number of heuristics updated.
    """
    try:
        hids = [row[0] for row in conn.execute(
            'SELECT heuristic_id FROM case_principles WHERE case_id = ?',
            (case_id,),
        ).fetchall()]
    except sqlite3.Error as exc:
        log.debug('record_case_outcomes lookup failed: %s', exc)
        return 0
    count = 0
    for hid in hids:
        if record_application(conn, hid, outcome=outcome, case_id=case_id):
            count += 1
    return count
