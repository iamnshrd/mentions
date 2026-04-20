"""Cross-market hedge / contradiction detection.

Two risks this module addresses:

* **Direct contradiction** — the agent is about to recommend NO on a
  market it recommended YES on three days ago (or vice-versa),
  typically because the evidence window shifted. Worth a big neon
  flag.
* **Stacked mutually-exclusive YES** — the agent issues YES on both
  "Fed cuts 25 bp in March" *and* "Fed pauses in March". These are
  sibling Kalshi markets resolving to the same event; at most one
  can win, so stacking YES implies the agent thinks both are
  simultaneously likely, which is incoherent.

We detect siblings via Kalshi's ticker convention: the portion of
the ticker *before* the final ``-segment`` names the event, the
final segment names the specific outcome. ``KXFED-25MAR-T25`` and
``KXFED-25MAR-PAUSE`` share prefix ``KXFED-25MAR`` and are therefore
sibling outcomes of the same event.

The module is a read-only consumer of ``decision_cases``; callers
decide what to do with the returned list. A typical pattern is to
surface any conflict in the ``warnings`` block of the synthesis dict
and let the UI render a neon banner.
"""
from __future__ import annotations

import logging
import sqlite3

from mentions_domain.analysis.hedge_check import (
    detect_hedge_conflicts,
    ticker_outcome,
    ticker_prefix,
)

log = logging.getLogger('mentions')


# ── DB read ───────────────────────────────────────────────────────────────

def find_recent_decisions(
    conn: sqlite3.Connection, *,
    ticker_prefix_value: str,
    lookback_days: int = 30,
) -> list[dict]:
    """Return recent ``decision_cases`` rows whose ticker shares a prefix.

    We compare ``UPPER(market_ticker) LIKE prefix || '-%'`` so a
    query on ``'KXFED-25MAR'`` pulls both ``T25`` and ``PAUSE``
    siblings. Lookback uses SQLite's ``datetime('now', '-N days')``;
    tests that back-date rows still pick them up while genuinely old
    decisions are ignored.
    """
    if not ticker_prefix_value:
        return []
    try:
        rows = conn.execute(
            '''SELECT id, market_ticker, decision, setup, created_at
                 FROM decision_cases
                WHERE market_ticker IS NOT NULL
                  AND UPPER(market_ticker) LIKE ? || '-%'
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC''',
            (ticker_prefix_value.upper(), f'-{int(lookback_days)} days'),
        ).fetchall()
    except sqlite3.Error as exc:
        log.debug('find_recent_decisions failed: %s', exc)
        return []
    return [
        {'id':            int(r[0]),
         'market_ticker': r[1],
         'decision':      (r[2] or '').upper(),
         'setup':         r[3],
         'created_at':    r[4]}
        for r in rows
    ]


# ── One-call facade ───────────────────────────────────────────────────────

def check_hedge_conflict(
    conn: sqlite3.Connection, *,
    ticker: str,
    decision: str,
    lookback_days: int = 30,
) -> dict:
    """End-to-end: find priors, classify, return a synthesis-friendly dict.

    Shape mirrors :func:`anti_patterns.check_anti_patterns` so
    callers can fold both into the same ``warnings`` block::

        {
            'conflicts':     [...],          # list of conflict dicts
            'flags':         ['...'],         # human-readable bullets
            'any_triggered': bool,
        }
    """
    prefix = ticker_prefix(ticker)
    priors = find_recent_decisions(
        conn, ticker_prefix_value=prefix, lookback_days=lookback_days,
    )
    conflicts = detect_hedge_conflicts(ticker, decision, priors)
    flags = [c['note'] for c in conflicts]
    return {
        'conflicts':     conflicts,
        'flags':         flags,
        'any_triggered': bool(conflicts),
    }
