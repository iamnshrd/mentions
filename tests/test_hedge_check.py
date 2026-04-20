"""Tests for cross-market hedge / contradiction detection (v0.14.3)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from library._core.analysis.hedge_check import (
    check_hedge_conflict, detect_hedge_conflicts, find_recent_decisions,
    ticker_outcome, ticker_prefix,
)


# ── Parsing ───────────────────────────────────────────────────────────────

class TestTickerParsing:
    def test_prefix_kalshi_three_segment(self):
        assert ticker_prefix('KXFED-25MAR-T25') == 'KXFED-25MAR'

    def test_prefix_kalshi_two_segment(self):
        assert ticker_prefix('KXFED-T25') == 'KXFED'

    def test_prefix_single_segment(self):
        assert ticker_prefix('BTC') == 'BTC'

    def test_prefix_lowercase_normalised(self):
        assert ticker_prefix('kxfed-25mar-t25') == 'KXFED-25MAR'

    def test_prefix_empty(self):
        assert ticker_prefix('') == ''
        assert ticker_prefix(None) == ''

    def test_outcome_segment(self):
        assert ticker_outcome('KXFED-25MAR-T25') == 'T25'
        assert ticker_outcome('KXFED-25MAR-PAUSE') == 'PAUSE'

    def test_outcome_single_segment(self):
        assert ticker_outcome('BTC') == ''


# ── Conflict classification ───────────────────────────────────────────────

class TestDetectConflicts:
    def test_same_ticker_opposite_decision_is_contradiction(self):
        priors = [{'id': 1, 'market_ticker': 'KXFED-25MAR-T25',
                   'decision': 'YES', 'setup': 'x', 'created_at': 'y'}]
        out = detect_hedge_conflicts('KXFED-25MAR-T25', 'NO', priors)
        assert len(out) == 1
        assert out[0]['type'] == 'contradiction'

    def test_same_ticker_same_decision_no_conflict(self):
        priors = [{'id': 1, 'market_ticker': 'KXFED-25MAR-T25',
                   'decision': 'YES', 'setup': 'x', 'created_at': 'y'}]
        out = detect_hedge_conflicts('KXFED-25MAR-T25', 'YES', priors)
        assert out == []

    def test_sibling_both_yes_is_stacked(self):
        priors = [{'id': 1, 'market_ticker': 'KXFED-25MAR-T25',
                   'decision': 'YES', 'setup': 'x', 'created_at': 'y'}]
        out = detect_hedge_conflicts('KXFED-25MAR-PAUSE', 'YES', priors)
        assert len(out) == 1
        assert out[0]['type'] == 'stacked_yes'

    def test_sibling_both_no_is_stacked_no(self):
        priors = [{'id': 1, 'market_ticker': 'KXFED-25MAR-T25',
                   'decision': 'NO', 'setup': 'x', 'created_at': 'y'}]
        out = detect_hedge_conflicts('KXFED-25MAR-PAUSE', 'NO', priors)
        assert len(out) == 1
        assert out[0]['type'] == 'stacked_no'

    def test_sibling_opposing_decisions_benign(self):
        priors = [{'id': 1, 'market_ticker': 'KXFED-25MAR-T25',
                   'decision': 'YES', 'setup': 'x', 'created_at': 'y'}]
        out = detect_hedge_conflicts('KXFED-25MAR-PAUSE', 'NO', priors)
        assert out == []

    def test_different_event_no_conflict(self):
        # Different prefix entirely.
        priors = [{'id': 1, 'market_ticker': 'KXBTC-25MAR-100K',
                   'decision': 'YES', 'setup': 'x', 'created_at': 'y'}]
        out = detect_hedge_conflicts('KXFED-25MAR-T25', 'YES', priors)
        # These won't be siblings even if passed in; callers usually
        # pre-filter by prefix, but the classifier shouldn't
        # misidentify them.
        assert out == [] or out[0]['type'] != 'contradiction'

    def test_empty_priors(self):
        assert detect_hedge_conflicts('KXFED-25MAR-T25', 'YES', []) == []


# ── DB query ──────────────────────────────────────────────────────────────

def _seed_case(conn, ticker, decision, days_ago=0):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)
          ).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        '''INSERT INTO decision_cases (market_ticker, decision, setup,
                                       created_at)
           VALUES (?, ?, 'demo', ?)''',
        (ticker, decision, ts),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


class TestFindRecentDecisions:
    def test_empty_prefix_returns_empty(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            assert find_recent_decisions(
                conn, ticker_prefix_value='') == []

    def test_pulls_sibling_tickers(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            _seed_case(conn, 'KXFED-25MAR-T25', 'YES')
            _seed_case(conn, 'KXFED-25MAR-PAUSE', 'YES')
            _seed_case(conn, 'KXBTC-25MAR-100K', 'YES')  # different event
            conn.commit()
            priors = find_recent_decisions(
                conn, ticker_prefix_value='KXFED-25MAR')
        tickers = {p['market_ticker'] for p in priors}
        assert tickers == {'KXFED-25MAR-T25', 'KXFED-25MAR-PAUSE'}

    def test_lookback_cutoff(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            _seed_case(conn, 'KXFED-25MAR-T25', 'YES', days_ago=60)
            _seed_case(conn, 'KXFED-25MAR-PAUSE', 'YES', days_ago=5)
            conn.commit()
            priors = find_recent_decisions(
                conn, ticker_prefix_value='KXFED-25MAR',
                lookback_days=30)
        # Only the 5-day-old one should come back.
        assert len(priors) == 1
        assert priors[0]['market_ticker'] == 'KXFED-25MAR-PAUSE'

    def test_null_ticker_ignored(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            # Pre-v6 row with NULL ticker.
            conn.execute(
                "INSERT INTO decision_cases (decision, setup) "
                "VALUES ('YES', 'legacy')",
            )
            conn.commit()
            priors = find_recent_decisions(
                conn, ticker_prefix_value='KXFED-25MAR')
        assert priors == []


# ── End-to-end facade ─────────────────────────────────────────────────────

class TestCheckHedgeConflict:
    def test_no_priors_no_conflict(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            out = check_hedge_conflict(
                conn, ticker='KXFED-25MAR-T25', decision='YES')
        assert out['any_triggered'] is False
        assert out['conflicts'] == []

    def test_contradiction_surfaced(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            _seed_case(conn, 'KXFED-25MAR-T25', 'YES', days_ago=2)
            conn.commit()
            out = check_hedge_conflict(
                conn, ticker='KXFED-25MAR-T25', decision='NO')
        assert out['any_triggered']
        assert out['conflicts'][0]['type'] == 'contradiction'
        assert out['flags']
        assert 'conflict' in out['flags'][0].lower()

    def test_stacked_yes_surfaced(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            _seed_case(conn, 'KXFED-25MAR-T25', 'YES', days_ago=2)
            conn.commit()
            out = check_hedge_conflict(
                conn, ticker='KXFED-25MAR-PAUSE', decision='YES')
        assert out['any_triggered']
        assert out['conflicts'][0]['type'] == 'stacked_yes'

    def test_schema_v6_applied(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            v = conn.execute('PRAGMA user_version').fetchone()[0]
        assert v >= 6

    def test_market_ticker_column_exists(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            cols = [row[1] for row in conn.execute(
                'PRAGMA table_info(decision_cases)').fetchall()]
        assert 'market_ticker' in cols
