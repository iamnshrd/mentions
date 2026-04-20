"""Tests for regime-conditioned posteriors (v0.14.4)."""
from __future__ import annotations

import sqlite3

import pytest

from mentions_domain.posteriors.heuristic_learn import (
    posterior_by_regime, record_application, top_confident_for_regime,
)
from mentions_domain.posteriors.speaker_learn import record_speaker_application


# ── Schema ────────────────────────────────────────────────────────────────

class TestSchema:
    def test_version_is_seven_or_later(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            v = conn.execute('PRAGMA user_version').fetchone()[0]
        assert v >= 7

    def test_regime_column_on_heuristic_apps(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            cols = [r[1] for r in conn.execute(
                'PRAGMA table_info(heuristic_applications)').fetchall()]
        assert 'regime' in cols

    def test_regime_column_on_speaker_apps(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            cols = [r[1] for r in conn.execute(
                'PRAGMA table_info(speaker_stance_applications)').fetchall()]
        assert 'regime' in cols

    def test_outcome_column_on_decision_cases(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            cols = [r[1] for r in conn.execute(
                'PRAGMA table_info(decision_cases)').fetchall()]
        assert 'outcome' in cols


# ── Record path wires regime through ──────────────────────────────────────

def _insert_heuristic(conn):
    conn.execute(
        "INSERT INTO heuristics (heuristic_text, heuristic_type, "
        "market_type, confidence, recurring_count) "
        "VALUES ('h', 'entry', 'all', 0.5, 1)",
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def _insert_speaker(conn, name='Jerome Powell'):
    conn.execute(
        "INSERT INTO speaker_profiles (canonical_name) VALUES (?)",
        (name,),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


class TestRecordStoresRegime:
    def test_heuristic_regime_persisted(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            conn.commit()
            record_application(conn, hid, outcome=1, regime='high_vol')
            row = conn.execute(
                'SELECT regime FROM heuristic_applications '
                'WHERE heuristic_id = ?', (hid,),
            ).fetchone()
        assert row[0] == 'high_vol'

    def test_speaker_regime_persisted(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            sid = _insert_speaker(conn)
            conn.commit()
            record_speaker_application(conn, sid, outcome=0,
                                       regime='pre_fomc')
            row = conn.execute(
                'SELECT regime FROM speaker_stance_applications '
                'WHERE speaker_profile_id = ?', (sid,),
            ).fetchone()
        assert row[0] == 'pre_fomc'

    def test_regime_defaults_to_null(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            conn.commit()
            record_application(conn, hid, outcome=1)
            row = conn.execute(
                'SELECT regime FROM heuristic_applications '
                'WHERE heuristic_id = ?', (hid,),
            ).fetchone()
        assert row[0] is None


# ── posterior_by_regime slicer ────────────────────────────────────────────

class TestPosteriorByRegime:
    def test_empty_for_no_applications(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            conn.commit()
            out = posterior_by_regime(conn, hid)
        assert out == {}

    def test_separates_regimes(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            conn.commit()
            for _ in range(6):
                record_application(conn, hid, outcome=1, regime='high_vol')
            record_application(conn, hid, outcome=0, regime='high_vol')
            for _ in range(5):
                record_application(conn, hid, outcome=0, regime='low_vol')
            out = posterior_by_regime(conn, hid)
        assert 'high_vol' in out and 'low_vol' in out
        assert out['high_vol']['posterior_p'] > 0.7
        assert out['low_vol']['posterior_p']  < 0.3
        assert out['high_vol']['n'] == 7
        assert out['low_vol']['n']  == 5

    def test_null_regime_bucketed_as_empty_string(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            conn.commit()
            record_application(conn, hid, outcome=1)
            out = posterior_by_regime(conn, hid)
        assert '' in out


# ── top_confident_for_regime ──────────────────────────────────────────────

class TestTopConfidentForRegime:
    def test_filters_by_regime_and_min(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            h_strong = _insert_heuristic(conn)
            h_weak   = _insert_heuristic(conn)
            conn.commit()
            for _ in range(5):
                record_application(conn, h_strong, outcome=1, regime='bull')
            for _ in range(5):
                record_application(conn, h_weak,   outcome=0, regime='bull')
            top = top_confident_for_regime(conn, 'bull', min_applications=3)
        ids = [r['id'] for r in top]
        assert ids.index(h_strong) < ids.index(h_weak)

    def test_ignores_other_regimes(self, tmp_db):
        """A heuristic with only 'bear'-regime data shouldn't appear
        in the 'bull' ranking."""
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            conn.commit()
            for _ in range(10):
                record_application(conn, hid, outcome=1, regime='bear')
            top = top_confident_for_regime(conn, 'bull', min_applications=3)
        assert top == []

    def test_respects_min_applications(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            conn.commit()
            record_application(conn, hid, outcome=1, regime='bull')
            top = top_confident_for_regime(conn, 'bull', min_applications=3)
        assert top == []
