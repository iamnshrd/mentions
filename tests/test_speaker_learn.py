"""Tests for Bayesian posterior updates on speaker stance (v0.13.2)."""
from __future__ import annotations

import sqlite3

import pytest

from library._core.analysis.speaker_learn import (
    get_counts, posterior_by_stance, posterior_p, record_speaker_application,
    reset_posterior, top_confident_speakers,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

def _insert_speaker(conn, name='Jerome Powell',
                    stype='central_banker', domain='monetary'):
    conn.execute(
        '''INSERT INTO speaker_profiles
           (canonical_name, speaker_type, domain)
           VALUES (?, ?, ?)''',
        (name, stype, domain),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


@pytest.fixture
def seeded_speaker(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        sid = _insert_speaker(conn)
        conn.commit()
    return {'sid': sid, 'db': tmp_db}


# ── Schema ────────────────────────────────────────────────────────────────

class TestSchema:
    def test_alpha_beta_default_one(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            a, b = get_counts(conn, seeded_speaker['sid'])
        assert a == 1.0
        assert b == 1.0

    def test_applications_table_exists(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                '''SELECT name FROM sqlite_master
                   WHERE type='table'
                     AND name='speaker_stance_applications' ''',
            ).fetchone()
        assert row is not None

    def test_schema_version_bumped(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            v = conn.execute('PRAGMA user_version').fetchone()[0]
        assert v >= 5


# ── Record ────────────────────────────────────────────────────────────────

class TestRecordApplication:
    def test_success_increments_alpha(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            ok = record_speaker_application(
                conn, seeded_speaker['sid'], outcome=1, stance='hawkish',
            )
            assert ok
            a, b = get_counts(conn, seeded_speaker['sid'])
        assert a == 2.0
        assert b == 1.0

    def test_failure_increments_beta(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            record_speaker_application(
                conn, seeded_speaker['sid'], outcome=0, stance='dovish',
            )
            a, b = get_counts(conn, seeded_speaker['sid'])
        assert a == 1.0
        assert b == 2.0

    def test_audit_row_inserted(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            record_speaker_application(
                conn, seeded_speaker['sid'], outcome=1,
                stance='hawkish', market_ticker='KXFED', note='rate hike',
            )
            row = conn.execute(
                'SELECT stance, outcome, market_ticker, note '
                '  FROM speaker_stance_applications '
                ' WHERE speaker_profile_id = ?',
                (seeded_speaker['sid'],),
            ).fetchone()
        assert row == ('hawkish', 1, 'KXFED', 'rate hike')

    def test_invalid_outcome_raises(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            with pytest.raises(ValueError):
                record_speaker_application(
                    conn, seeded_speaker['sid'], outcome=7,
                )

    def test_missing_speaker_returns_false(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            ok = record_speaker_application(conn, 9_999_999, outcome=1)
        assert ok is False

    def test_converges_with_repeated_outcomes(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            for _ in range(20):
                record_speaker_application(
                    conn, seeded_speaker['sid'], outcome=1,
                )
            a, b = get_counts(conn, seeded_speaker['sid'])
        assert posterior_p(a, b) > 0.9


# ── Reset ─────────────────────────────────────────────────────────────────

class TestReset:
    def test_reset_restores_uniform(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            for _ in range(5):
                record_speaker_application(
                    conn, seeded_speaker['sid'], outcome=1,
                )
            a, _ = get_counts(conn, seeded_speaker['sid'])
            assert a > 1.0
            reset_posterior(conn, seeded_speaker['sid'])
            a2, b2 = get_counts(conn, seeded_speaker['sid'])
        assert a2 == 1.0
        assert b2 == 1.0


# ── Ranking ───────────────────────────────────────────────────────────────

class TestTopConfidentSpeakers:
    def test_filters_under_min_applications(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            record_speaker_application(
                conn, seeded_speaker['sid'], outcome=1,
            )
            top = top_confident_speakers(conn)
        assert top == []

    def test_ranks_well_evidenced_first(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            s_good = _insert_speaker(conn, name='Accurate Sage')
            s_bad  = _insert_speaker(conn, name='Noisy Pundit')
            conn.commit()
            for _ in range(10):
                record_speaker_application(conn, s_good, outcome=1)
            for _ in range(10):
                record_speaker_application(conn, s_bad, outcome=0)
            top = top_confident_speakers(conn, min_applications=3)
        ids = [r['id'] for r in top]
        assert ids.index(s_good) < ids.index(s_bad)
        assert top[0]['posterior_p'] > 0.8


# ── Per-stance slicer ─────────────────────────────────────────────────────

class TestPosteriorByStance:
    def test_slices_by_stance(self, seeded_speaker):
        sid = seeded_speaker['sid']
        with sqlite3.connect(seeded_speaker['db']) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            # Hawkish: 5 wins, 1 loss.
            for _ in range(5):
                record_speaker_application(conn, sid, outcome=1,
                                           stance='hawkish')
            record_speaker_application(conn, sid, outcome=0,
                                       stance='hawkish')
            # Dovish: 1 win, 4 losses.
            record_speaker_application(conn, sid, outcome=1,
                                       stance='dovish')
            for _ in range(4):
                record_speaker_application(conn, sid, outcome=0,
                                           stance='dovish')
            sliced = posterior_by_stance(conn, sid)
        assert 'hawkish' in sliced
        assert 'dovish' in sliced
        assert sliced['hawkish']['n'] == 6
        assert sliced['dovish']['n']  == 5
        assert sliced['hawkish']['posterior_p'] > sliced['dovish']['posterior_p']

    def test_empty_when_no_applications(self, seeded_speaker):
        with sqlite3.connect(seeded_speaker['db']) as conn:
            sliced = posterior_by_stance(conn, seeded_speaker['sid'])
        assert sliced == {}
