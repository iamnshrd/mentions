"""Anti-pattern / crowd-mistake / dispute-pattern detector.

The structured knowledge layer imported in schema v2 includes three
tables that describe "what usually goes wrong" around a given setup:

* ``anti_patterns``    — trade patterns that look attractive but are
                         systematically unprofitable.
* ``crowd_mistakes``   — observations about how retail mispricing
                         happens; the agent should beware of the same
                         trap.
* ``dispute_patterns`` — resolution ambiguity patterns that increase
                         settlement risk.

Pre-v0.13 none of this was read by the analytical path — it was
imported and left on disk. This module pulls applicable rows from the
retrieve bundle (already joined to source documents) and projects them
onto two effects:

1. A **flag list** surfaced in the final response so the user sees
   "heads-up: crowd-mistake X applies here".
2. A **probability down-weight factor** fed into the same
   log-odds combinator used by :mod:`signal`. An active anti-pattern
   contributes p < 0.5 ("this looks less like clean signal"), and
   stacking multiple anti-patterns compounds that effect.

The matching policy is deliberately simple: **any** structured row in
the retrieved bundle is "applicable" to the current frame. The
retrieve layer already filters by document relevance, so every row
that survived RRF / MMR is treated as a warning worth surfacing.

Callers that want stricter matching can pre-filter the bundle before
calling :func:`check_anti_patterns`.
"""
from __future__ import annotations

import logging
import sqlite3

from mentions_domain.analysis.anti_patterns import (
    apply_anti_patterns_to_p_signal,
    build_anti_pattern_warnings,
)

log = logging.getLogger('mentions')


def check_anti_patterns(bundle: dict) -> dict:
    """Scan a retrieve bundle for applicable warnings.

    *bundle* is the dict returned by
    :func:`agents.mentions.services.retrieval.hybrid.hybrid_retrieve`, which
    already carries ``doc_ids`` and any attached structured rows.
    We don't call retrieve again — stay a pure consumer.

    Returns::

        {
            'anti_patterns':    list[dict],   # rows, verbatim
            'crowd_mistakes':   list[dict],
            'dispute_patterns': list[dict],
            'flags':            list[str],    # short human-readable bullets
            'factor_ps':        dict[str, float],
                # {factor_name: p} — ready to pass into
                # probability.combine_independent().
            'any_triggered':    bool,
        }
    """
    # The bundle shape pre-v0.13 only has 'heuristics' and
    # 'decision_cases'. We fetch the rest from the DB when doc_ids
    # are present.
    doc_ids = list(bundle.get('doc_ids') or [])
    ap = _fetch_for_documents('anti_patterns', doc_ids,
                              cols='id, pattern_text, why_bad')
    cm = _fetch_for_documents('crowd_mistakes', doc_ids,
                              cols='id, mistake_name, mistake_type, description')
    dp = _fetch_for_documents('dispute_patterns', doc_ids,
                              cols=('id, pattern_name, dispute_type, '
                                    'description, market_impact'))

    return build_anti_pattern_warnings(ap, cm, dp)


# ── DB helpers ────────────────────────────────────────────────────────────

def _fetch_for_documents(table: str, doc_ids: list[int],
                         *, cols: str) -> list[dict]:
    """Return rows from *table* whose ``example_document_id`` matches.

    All three target tables share the ``example_document_id`` FK
    convention (see migrate.py v2). Safe against missing tables /
    empty input — returns ``[]``.
    """
    if not doc_ids:
        return []
    placeholders = ','.join('?' * len(doc_ids))
    results: list[dict] = []
    try:
        from agents.mentions.db import connect, row_to_dict
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f'''SELECT {cols}
                      FROM {table}
                     WHERE example_document_id IN ({placeholders})''',
                doc_ids,
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except sqlite3.Error as exc:
        log.debug('_fetch_for_documents(%s) failed: %s', table, exc)
    except Exception as exc:  # pragma: no cover
        log.debug('_fetch_for_documents(%s) unexpected: %s', table, exc)
    return results


# ── Convenience: apply to a p_signal ──────────────────────────────────────

def apply_to_p_signal(p_signal: float | None,
                      warnings: dict) -> float | None:
    """Fold anti-pattern factors into an existing p_signal.

    Returns the updated probability, or the original input if no
    warnings triggered / p_signal is None.
    """
    return apply_anti_patterns_to_p_signal(p_signal, warnings)
