"""Counterfactual heuristic-lift analysis.

Takes the ``decision_cases`` audit log as ground truth and asks, for
each heuristic, **"did decisions that invoked this heuristic win more
often than decisions that didn't?"**.

The classical Bayesian posterior on ``heuristics.alpha/beta`` answers
"when we applied it, how often did it work?" — which conflates
heuristic quality with decision-quality. If the agent only invokes
heuristic H when the decision was already easy, H's posterior looks
stellar even though H contributed no signal.

Counterfactual analysis compares:

* ``p_with``    — win rate of cases where heuristic H was in
                  ``case_principles``
* ``p_without`` — win rate of cases where H was *not* linked

and emits ``lift = p_with − p_without``. A heuristic with lift ≈ 0
is riding along on good decisions, not adding signal. A heuristic
with lift < 0 is actively *negative* — its invocation correlates
with losses, which is the strongest kind of "retire this heuristic"
evidence.

We include Wilson 95 % CIs on both rates so callers can tell a
small-sample fluke from a real effect. The schema v7 column
``decision_cases.outcome`` (binary 0/1, NULL for unresolved) is the
sole input — rows without an outcome are simply skipped.
"""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger('mentions')


def _wilson_ci(wins: int, n: int, *, z: float = 1.96
               ) -> tuple[float, float, float]:
    """Return ``(p_hat, lo, hi)`` via the Wilson-score interval.

    Handles the ``n == 0`` edge by returning the uninformative
    (0.0, 0.0, 1.0) triple.
    """
    if n <= 0:
        return (0.0, 0.0, 1.0)
    p_hat = wins / n
    denom = 1.0 + (z * z) / n
    centre = (p_hat + (z * z) / (2.0 * n)) / denom
    import math
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + (z * z) / (4 * n * n))
            / denom)
    lo = max(0.0, centre - half)
    hi = min(1.0, centre + half)
    return (p_hat, lo, hi)


def heuristic_lift(
    conn: sqlite3.Connection, heuristic_id: int,
) -> dict | None:
    """Compute counterfactual lift for one heuristic.

    Returns ``None`` if the heuristic has zero resolved cases on
    either side of the comparison — there's nothing to compare and
    returning fabricated zeros would mislead rankings.
    """
    try:
        # Cases where this heuristic was applied AND resolved.
        with_row = conn.execute(
            '''SELECT
                 SUM(CASE WHEN dc.outcome = 1 THEN 1 ELSE 0 END) AS wins,
                 SUM(CASE WHEN dc.outcome IS NOT NULL THEN 1 ELSE 0 END) AS n
               FROM decision_cases dc
               JOIN case_principles cp ON cp.case_id = dc.id
               WHERE cp.heuristic_id = ?''',
            (heuristic_id,),
        ).fetchone()
        # All resolved cases NOT linked to this heuristic.
        without_row = conn.execute(
            '''SELECT
                 SUM(CASE WHEN dc.outcome = 1 THEN 1 ELSE 0 END) AS wins,
                 SUM(CASE WHEN dc.outcome IS NOT NULL THEN 1 ELSE 0 END) AS n
               FROM decision_cases dc
               WHERE dc.outcome IS NOT NULL
                 AND dc.id NOT IN (
                   SELECT case_id FROM case_principles WHERE heuristic_id = ?
                 )''',
            (heuristic_id,),
        ).fetchone()
    except sqlite3.Error as exc:
        log.debug('heuristic_lift query failed: %s', exc)
        return None

    wins_with    = int(with_row[0]    or 0)
    n_with       = int(with_row[1]    or 0)
    wins_without = int(without_row[0] or 0)
    n_without    = int(without_row[1] or 0)

    if n_with == 0 or n_without == 0:
        return None

    p_with,    lo_with,    hi_with    = _wilson_ci(wins_with,    n_with)
    p_without, lo_without, hi_without = _wilson_ci(wins_without, n_without)
    lift = p_with - p_without
    # CI on the difference — conservative via the additive combination
    # of half-widths (a sum-of-CIs approximation, not a proper delta
    # method, but it's well-defined on [−1, +1] and cheap).
    lift_lo = max(-1.0, lo_with - hi_without)
    lift_hi = min( 1.0, hi_with - lo_without)
    return {
        'heuristic_id': int(heuristic_id),
        'n_with':       n_with,
        'n_without':    n_without,
        'wins_with':    wins_with,
        'wins_without': wins_without,
        'p_with':       round(p_with,    4),
        'p_without':    round(p_without, 4),
        'lift':         round(lift,      4),
        'lift_ci':      (round(lift_lo, 4), round(lift_hi, 4)),
        'with_ci':      (round(lo_with,    4), round(hi_with,    4)),
        'without_ci':   (round(lo_without, 4), round(hi_without, 4)),
    }


def all_heuristic_lifts(
    conn: sqlite3.Connection, *,
    min_n_with: int = 3,
) -> list[dict]:
    """Compute lift for every heuristic with ≥ *min_n_with* invoked cases.

    Returns a list sorted by lift descending. Heuristics for which
    lift can't be computed (empty with/without side) are silently
    omitted — they aren't ranked alongside real evidence.

    Use case: once a quarter, produce a "kill list" of heuristics
    whose lift is ≤ 0. Keeping them active pollutes synthesis with
    principles that don't discriminate winners from losers.
    """
    try:
        ids = [r[0] for r in conn.execute(
            'SELECT id FROM heuristics').fetchall()]
    except sqlite3.Error as exc:
        log.debug('all_heuristic_lifts lookup failed: %s', exc)
        return []
    out: list[dict] = []
    for hid in ids:
        r = heuristic_lift(conn, hid)
        if r is None or r['n_with'] < min_n_with:
            continue
        out.append(r)
    out.sort(key=lambda r: r['lift'], reverse=True)
    return out


def kill_list(
    conn: sqlite3.Connection, *,
    min_n_with: int = 5,
    lift_threshold: float = 0.0,
) -> list[dict]:
    """Heuristics whose lift upper-bound is ≤ *lift_threshold*.

    Using the *upper* CI bound (not the point estimate) means we only
    flag heuristics we're confident are non-positive — a heuristic
    with lift = −0.05 but wide CI stretching to +0.2 isn't killed
    yet. Defaults: threshold 0.0 (i.e. "useless or worse"), min 5
    invoked cases before we even consider evidence.
    """
    all_rows = all_heuristic_lifts(conn, min_n_with=min_n_with)
    return [r for r in all_rows if r['lift_ci'][1] <= lift_threshold]
