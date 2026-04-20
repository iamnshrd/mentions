"""Tests for Bayesian heuristic posterior updates (v0.13)."""
from __future__ import annotations

import sqlite3

import pytest

from library._core.analysis.heuristic_learn import (
    get_counts, posterior_ci, posterior_p, record_application,
    record_case_outcomes, reset_posterior, top_confident,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

def _insert_heuristic(conn, text='scale in', htype='entry', market_type='all'):
    conn.execute(
        '''INSERT INTO heuristics
           (heuristic_text, heuristic_type, market_type,
            confidence, recurring_count)
           VALUES (?, ?, ?, 0.5, 1)''',
        (text, htype, market_type),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


@pytest.fixture
def seeded(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        hid = _insert_heuristic(conn)
        conn.commit()
    return {'hid': hid, 'db': tmp_db}


# ── Schema ────────────────────────────────────────────────────────────────

class TestSchema:
    def test_alpha_beta_default_one(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            a, b = get_counts(conn, seeded['hid'])
        assert a == 1.0
        assert b == 1.0

    def test_applications_table_exists(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                '''SELECT name FROM sqlite_master
                   WHERE type='table' AND name='heuristic_applications' ''',
            ).fetchone()
        assert row is not None


# ── Posterior math ────────────────────────────────────────────────────────

class TestPosteriorMath:
    def test_uniform_prior_is_half(self):
        assert posterior_p(1.0, 1.0) == 0.5

    def test_successes_push_up(self):
        assert posterior_p(5.0, 1.0) > 0.5

    def test_failures_push_down(self):
        assert posterior_p(1.0, 5.0) < 0.5

    def test_zero_counts_safe(self):
        assert posterior_p(0.0, 0.0) == 0.5

    def test_ci_widens_with_small_n(self):
        lo_small, hi_small = posterior_ci(3.0, 3.0)    # n=4 obs
        lo_big,   hi_big   = posterior_ci(51.0, 51.0)  # n=100 obs
        assert (hi_small - lo_small) > (hi_big - lo_big)

    def test_ci_no_data_full_range(self):
        lo, hi = posterior_ci(1.0, 1.0)  # 0 observations
        assert lo == 0.0
        assert hi == 1.0


# ── record_application ────────────────────────────────────────────────────

class TestRecordApplication:
    def test_success_increments_alpha(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            ok = record_application(conn, seeded['hid'], outcome=1)
            assert ok
            a, b = get_counts(conn, seeded['hid'])
        assert a == 2.0
        assert b == 1.0

    def test_failure_increments_beta(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            record_application(conn, seeded['hid'], outcome=0)
            a, b = get_counts(conn, seeded['hid'])
        assert a == 1.0
        assert b == 2.0

    def test_audit_row_inserted(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            record_application(conn, seeded['hid'], outcome=1,
                               market_ticker='KXFED', note='rate cut hit')
            row = conn.execute(
                'SELECT outcome, market_ticker, note '
                '  FROM heuristic_applications WHERE heuristic_id = ?',
                (seeded['hid'],),
            ).fetchone()
        assert row == (1, 'KXFED', 'rate cut hit')

    def test_invalid_outcome_raises(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            with pytest.raises(ValueError):
                record_application(conn, seeded['hid'], outcome=2)

    def test_missing_heuristic_returns_false(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            ok = record_application(conn, 9_999_999, outcome=1)
        assert ok is False

    def test_converges_with_repeated_outcomes(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            for _ in range(20):
                record_application(conn, seeded['hid'], outcome=1)
            a, b = get_counts(conn, seeded['hid'])
        assert posterior_p(a, b) > 0.9


# ── Reset ─────────────────────────────────────────────────────────────────

class TestReset:
    def test_reset_restores_uniform(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            for _ in range(5):
                record_application(conn, seeded['hid'], outcome=1)
            a, _ = get_counts(conn, seeded['hid'])
            assert a > 1.0
            reset_posterior(conn, seeded['hid'])
            a2, b2 = get_counts(conn, seeded['hid'])
        assert a2 == 1.0
        assert b2 == 1.0


# ── Ranking ───────────────────────────────────────────────────────────────

class TestTopConfident:
    def test_filters_under_min_applications(self, seeded):
        with sqlite3.connect(seeded['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            # Only 1 application — below default min=3.
            record_application(conn, seeded['hid'], outcome=1)
            top = top_confident(conn)
        assert top == []

    def test_ranks_well_evidenced_first(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            h_good = _insert_heuristic(conn, text='winner', htype='entry')
            h_bad  = _insert_heuristic(conn, text='loser',  htype='entry')
            conn.commit()
            for _ in range(10):
                record_application(conn, h_good, outcome=1)
            for _ in range(10):
                record_application(conn, h_bad, outcome=0)
            top = top_confident(conn, min_applications=3)
        # h_good should rank above h_bad.
        ids = [r['id'] for r in top]
        assert ids.index(h_good) < ids.index(h_bad)
        assert top[0]['posterior_p'] > 0.8

    def test_limit_respected(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            ids = [_insert_heuristic(conn, text=f'h{i}') for i in range(5)]
            conn.commit()
            for hid in ids:
                for _ in range(3):
                    record_application(conn, hid, outcome=1)
            top = top_confident(conn, limit=2, min_applications=3)
        assert len(top) == 2


# ── Case batch updates ────────────────────────────────────────────────────

class TestCaseOutcomes:
    def test_batch_updates_all_linked_heuristics(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            h1 = _insert_heuristic(conn, text='h1')
            h2 = _insert_heuristic(conn, text='h2')
            # Insert a decision_case + case_principles links.
            conn.execute(
                '''INSERT INTO decision_cases (document_id, setup, decision)
                   VALUES (NULL, 'demo', 'YES')''',
            )
            cid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.executemany(
                'INSERT INTO case_principles (case_id, heuristic_id) '
                'VALUES (?, ?)',
                [(cid, h1), (cid, h2)],
            )
            conn.commit()
            n = record_case_outcomes(conn, cid, outcome=1)
        assert n == 2
        with sqlite3.connect(tmp_db) as conn:
            for hid in (h1, h2):
                a, b = get_counts(conn, hid)
                assert a == 2.0
                assert b == 1.0
