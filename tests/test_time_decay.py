"""Tests for time-decayed Bayesian posterior recomputation (v0.14.2)."""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from library._core.analysis.heuristic_learn import (
    decayed_counts as heuristic_decayed_counts,
    record_application, top_confident,
)
from library._core.analysis.speaker_learn import (
    decayed_counts as speaker_decayed_counts,
    record_speaker_application, top_confident_speakers,
)
from library._core.analysis.time_decay import (
    _parse_ts, _weight, decayed_counts_from_rows,
)


# ── Pure helpers ──────────────────────────────────────────────────────────

class TestParseTs:
    def test_sqlite_default_format(self):
        t = _parse_ts('2024-06-01 12:00:00')
        assert t is not None
        assert t > 0

    def test_iso_t_separator(self):
        assert _parse_ts('2024-06-01T12:00:00') is not None

    def test_iso_with_z_suffix(self):
        assert _parse_ts('2024-06-01T12:00:00Z') is not None

    def test_date_only(self):
        assert _parse_ts('2024-06-01') is not None

    def test_garbage_returns_none(self):
        assert _parse_ts('not a date') is None
        assert _parse_ts('') is None
        assert _parse_ts(None) is None


class TestWeight:
    def test_zero_delta_is_one(self):
        now = datetime.now(timezone.utc)
        w = _weight(now.strftime('%Y-%m-%d %H:%M:%S'),
                    now.timestamp(), 180.0)
        assert w == pytest.approx(1.0, abs=0.01)

    def test_one_half_life_is_half(self):
        now = datetime.now(timezone.utc)
        ago = now - timedelta(days=180)
        w = _weight(ago.strftime('%Y-%m-%d %H:%M:%S'),
                    now.timestamp(), 180.0)
        assert w == pytest.approx(0.5, abs=0.01)

    def test_two_half_lives_is_quarter(self):
        now = datetime.now(timezone.utc)
        ago = now - timedelta(days=360)
        w = _weight(ago.strftime('%Y-%m-%d %H:%M:%S'),
                    now.timestamp(), 180.0)
        assert w == pytest.approx(0.25, abs=0.01)

    def test_half_life_zero_disables_decay(self):
        now = datetime.now(timezone.utc)
        ago = now - timedelta(days=10_000)
        w = _weight(ago.strftime('%Y-%m-%d %H:%M:%S'),
                    now.timestamp(), 0.0)
        assert w == 1.0

    def test_future_timestamps_capped_at_one(self):
        # Clock skew shouldn't upweight rows stamped in the future.
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        w = _weight(future.strftime('%Y-%m-%d %H:%M:%S'),
                    now.timestamp(), 180.0)
        assert w == pytest.approx(1.0, abs=0.01)


class TestDecayedCountsFromRows:
    def test_empty_returns_prior(self):
        a, b, n = decayed_counts_from_rows([])
        assert (a, b, n) == (1.0, 1.0, 0)

    def test_all_recent_matches_cumulative(self):
        # Five wins, zero losses, all stamped "now" → α = 1 + 5, β = 1.
        now = datetime.now(timezone.utc)
        ts = now.strftime('%Y-%m-%d %H:%M:%S')
        rows = [(1, ts)] * 5
        a, b, n = decayed_counts_from_rows(
            rows, half_life_days=180.0, now=now,
        )
        assert a == pytest.approx(6.0, abs=0.01)
        assert b == pytest.approx(1.0, abs=0.01)
        assert n == 5

    def test_old_wins_count_less(self):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=360)).strftime('%Y-%m-%d %H:%M:%S')
        # 4 wins, all 360 days old → each contributes ~0.25, so α ≈ 1 + 1
        rows = [(1, old)] * 4
        a, _, _ = decayed_counts_from_rows(
            rows, half_life_days=180.0, now=now,
        )
        assert a == pytest.approx(2.0, abs=0.05)

    def test_mixed_recency(self):
        now = datetime.now(timezone.utc)
        fresh = now.strftime('%Y-%m-%d %H:%M:%S')
        ancient = (now - timedelta(days=720)).strftime('%Y-%m-%d %H:%M:%S')
        rows = [(1, fresh), (1, fresh), (0, ancient), (0, ancient)]
        a, b, _ = decayed_counts_from_rows(
            rows, half_life_days=180.0, now=now,
        )
        # Recent wins dominate; ancient losses ≈ 2 × 0.0625 = 0.125 each ≈ 0.25
        assert a > 2.5   # ~1 + 2*1
        assert b < 1.5   # ~1 + 2*0.0625


# ── Heuristic DB integration ──────────────────────────────────────────────

class TestHeuristicDecayedCounts:
    def _insert_heuristic(self, conn):
        conn.execute(
            "INSERT INTO heuristics (heuristic_text, heuristic_type, "
            "market_type, confidence, recurring_count) "
            "VALUES ('test', 'entry', 'all', 0.5, 1)",
        )
        return conn.execute('SELECT last_insert_rowid()').fetchone()[0]

    def test_no_applications_returns_prior(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            hid = self._insert_heuristic(conn)
            conn.commit()
            a, b, n = heuristic_decayed_counts(conn, hid)
        assert (a, b, n) == (1.0, 1.0, 0)

    def test_recent_apps_weighted_full(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = self._insert_heuristic(conn)
            conn.commit()
            for _ in range(5):
                record_application(conn, hid, outcome=1)
            a, b, n = heuristic_decayed_counts(conn, hid)
        assert n == 5
        assert a == pytest.approx(6.0, abs=0.01)
        assert b == pytest.approx(1.0, abs=0.01)

    def test_old_apps_down_weighted(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = self._insert_heuristic(conn)
            # Insert 4 wins directly with a back-dated applied_at.
            old = (datetime.now(timezone.utc) - timedelta(days=360))
            old_s = old.strftime('%Y-%m-%d %H:%M:%S')
            for _ in range(4):
                conn.execute(
                    'INSERT INTO heuristic_applications '
                    '(heuristic_id, outcome, applied_at) VALUES (?, 1, ?)',
                    (hid, old_s),
                )
            conn.commit()
            a, _, n = heuristic_decayed_counts(
                conn, hid, half_life_days=180.0)
        assert n == 4
        # 4 × 0.25 ≈ 1.0 contribution → α ≈ 2.0 not 5.0
        assert a == pytest.approx(2.0, abs=0.05)

    def test_half_life_zero_matches_cumulative(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = self._insert_heuristic(conn)
            conn.commit()
            for _ in range(3):
                record_application(conn, hid, outcome=1)
            a, b, _ = heuristic_decayed_counts(conn, hid, half_life_days=0.0)
        # No decay → α = 1 + 3 = 4
        assert a == pytest.approx(4.0, abs=0.01)
        assert b == pytest.approx(1.0, abs=0.01)


# ── Heuristic ranking with decay ──────────────────────────────────────────

class TestTopConfidentDecay:
    def test_cold_heuristic_drops_below_fresh(self, tmp_db):
        """Two heuristics with identical cumulative 10/10 records — one
        from ancient history, one recent. With decay, the recent one
        should rank higher.
        """
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            for name in ('stale_winner', 'fresh_winner'):
                conn.execute(
                    f"INSERT INTO heuristics (heuristic_text, heuristic_type, "
                    f"market_type, confidence, recurring_count) "
                    f"VALUES ('{name}', 'entry', 'all', 0.5, 1)",
                )
            conn.commit()
            stale = conn.execute(
                "SELECT id FROM heuristics WHERE heuristic_text='stale_winner'",
            ).fetchone()[0]
            fresh = conn.execute(
                "SELECT id FROM heuristics WHERE heuristic_text='fresh_winner'",
            ).fetchone()[0]
            ancient = (datetime.now(timezone.utc) - timedelta(days=720)
                       ).strftime('%Y-%m-%d %H:%M:%S')
            now_s = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            for _ in range(10):
                conn.execute(
                    'INSERT INTO heuristic_applications '
                    '(heuristic_id, outcome, applied_at) VALUES (?, 1, ?)',
                    (stale, ancient),
                )
                conn.execute(
                    'INSERT INTO heuristic_applications '
                    '(heuristic_id, outcome, applied_at) VALUES (?, 1, ?)',
                    (fresh, now_s),
                )
            conn.commit()
            top = top_confident(conn, min_applications=3,
                                half_life_days=180.0)
        ids = [r['id'] for r in top]
        assert ids.index(fresh) < ids.index(stale)

    def test_no_half_life_uses_stored_counts(self, tmp_db):
        """Smoke check: default path still behaves as pre-v0.14.2."""
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute(
                "INSERT INTO heuristics (heuristic_text, heuristic_type, "
                "market_type, confidence, recurring_count) "
                "VALUES ('any', 'entry', 'all', 0.5, 1)",
            )
            hid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.commit()
            for _ in range(5):
                record_application(conn, hid, outcome=1)
            top = top_confident(conn, min_applications=3)
        assert top
        assert top[0]['id'] == hid


# ── Speaker mirror ────────────────────────────────────────────────────────

class TestSpeakerDecay:
    def test_decayed_counts_returns_prior_for_missing(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            a, b, n = speaker_decayed_counts(conn, 9_999_999)
        assert (a, b, n) == (1.0, 1.0, 0)

    def test_ranking_prefers_recent_speaker(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute(
                "INSERT INTO speaker_profiles (canonical_name) "
                "VALUES ('Stale Speaker'), ('Fresh Speaker')",
            )
            stale = conn.execute(
                "SELECT id FROM speaker_profiles "
                "WHERE canonical_name='Stale Speaker'",
            ).fetchone()[0]
            fresh = conn.execute(
                "SELECT id FROM speaker_profiles "
                "WHERE canonical_name='Fresh Speaker'",
            ).fetchone()[0]
            ancient = (datetime.now(timezone.utc) - timedelta(days=720)
                       ).strftime('%Y-%m-%d %H:%M:%S')
            now_s = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            for _ in range(10):
                conn.execute(
                    'INSERT INTO speaker_stance_applications '
                    '(speaker_profile_id, outcome, applied_at) '
                    'VALUES (?, 1, ?)',
                    (stale, ancient),
                )
                conn.execute(
                    'INSERT INTO speaker_stance_applications '
                    '(speaker_profile_id, outcome, applied_at) '
                    'VALUES (?, 1, ?)',
                    (fresh, now_s),
                )
            conn.commit()
            top = top_confident_speakers(conn, min_applications=3,
                                         half_life_days=180.0)
        ids = [r['id'] for r in top]
        assert ids.index(fresh) < ids.index(stale)
