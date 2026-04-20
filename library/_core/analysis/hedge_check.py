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

log = logging.getLogger('mentions')


# ── Ticker parsing ────────────────────────────────────────────────────────

def ticker_prefix(ticker: str) -> str:
    """Return the event stem of a Kalshi-style ticker.

    ``KXFED-25MAR-T25`` → ``KXFED-25MAR``. If the ticker has only
    one segment the whole string is returned (treated as its own
    event). Input is case-normalised to uppercase so comparisons work
    regardless of how the ticker was written into a decision row.
    """
    t = (ticker or '').strip().upper()
    if not t:
        return ''
    if '-' not in t:
        return t
    return t.rsplit('-', 1)[0]


def ticker_outcome(ticker: str) -> str:
    """Return the outcome suffix of a Kalshi-style ticker.

    ``KXFED-25MAR-T25`` → ``T25``. Empty string for single-segment
    tickers — they don't have a distinct outcome tag.
    """
    t = (ticker or '').strip().upper()
    if not t or '-' not in t:
        return ''
    return t.rsplit('-', 1)[1]


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


# ── Conflict detection ────────────────────────────────────────────────────

def detect_hedge_conflicts(
    current_ticker: str,
    current_decision: str,
    priors: list[dict],
) -> list[dict]:
    """Classify each prior as contradiction / stacked-yes / benign.

    Returns only the rows that are conflicts; benign priors are
    omitted so callers can treat a non-empty list as "there's
    something to warn about".

    Conflict types:

    * ``'contradiction'`` — same ticker, opposite decision.
    * ``'stacked_yes'``   — sibling ticker (shared prefix, different
                            outcome), both decisions are YES. Only
                            generated when the two outcomes are
                            distinct — re-issuing YES on the same
                            ticker is a no-op, not a conflict.
    * ``'stacked_no'``    — mirror of above for NO/NO stacking on
                            sibling outcomes (less common but also
                            logically suspicious for exhaustive
                            outcome sets).
    """
    current_ticker = (current_ticker or '').upper()
    current_decision = (current_decision or '').upper()
    current_outcome = ticker_outcome(current_ticker)
    conflicts: list[dict] = []
    for p in priors:
        pticker = (p.get('market_ticker') or '').upper()
        pdec    = (p.get('decision') or '').upper()
        if not pticker or not pdec:
            continue
        if pticker == current_ticker:
            if pdec != current_decision and pdec in {'YES', 'NO'}:
                conflicts.append({
                    'type':     'contradiction',
                    'prior':    p,
                    'note':    (f'Prior decision {pdec} on {pticker} '
                                f'conflicts with proposed '
                                f'{current_decision}.'),
                })
            continue
        # Different ticker but shared prefix — sibling outcomes.
        if ticker_outcome(pticker) == current_outcome:
            continue  # not actually a sibling; just same ticker in edge case
        if pdec == current_decision == 'YES':
            conflicts.append({
                'type':     'stacked_yes',
                'prior':    p,
                'note':    (f'YES on {pticker} and proposed YES on '
                            f'{current_ticker} are sibling outcomes — '
                            f'at most one can resolve YES.'),
            })
        elif pdec == current_decision == 'NO':
            conflicts.append({
                'type':     'stacked_no',
                'prior':    p,
                'note':    (f'NO on {pticker} and proposed NO on '
                            f'{current_ticker} are sibling outcomes — '
                            f'under an exhaustive outcome set this '
                            f'implies no resolution path.'),
            })
    return conflicts


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
