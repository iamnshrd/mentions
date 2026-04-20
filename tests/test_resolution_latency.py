"""Tests for resolution-latency analytics (v0.14.7 — D1)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from library._core.eval.resolution_latency import (
    case_latency_days, heuristic_latency_stats, set_case_outcome,
)


# ── Fixtures / helpers ────────────────────────────────────────────────────

def _insert_heuristic(conn):
    conn.execute(
        "INSERT INTO heuristics (heuristic_text, heuristic_type, "
        "market_type, confidence, recurring_count) "
        "VALUES ('h', 'entry', 'all', 0.5, 1)",
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def _insert_case(conn, *, created_at=None, heuristic_ids=()):
    if created_at:
        conn.execute(
            "INSERT INTO decision_cases (setup, decision, created_at) "
            "VALUES ('x', 'YES', ?)", (created_at,),
        )
    else:
        conn.execute(
            "INSERT INTO decision_cases (setup, decision) "
            "VALUES ('x', 'YES')",
        )
    cid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    for hid in heuristic_ids:
        conn.execute(
            'INSERT INTO case_principles (case_id, heuristic_id) '
            'VALUES (?, ?)', (cid, hid),
        )
    conn.commit()
    return cid


# ── Schema ────────────────────────────────────────────────────────────────

class TestSchema:
    def test_version_ten(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            v = conn.execute('PRAGMA user_version').fetchone()[0]
        assert v >= 10

    def test_outcome_resolved_at_column(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            cols = [r[1] for r in conn.execute(
                'PRAGMA table_info(decision_cases)').fetchall()]
        assert 'outcome_resolved_at' in cols


# ── set_case_outcome ──────────────────────────────────────────────────────

class TestSetCaseOutcome:
    def test_sets_both_columns(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            cid = _insert_case(conn)
            ok = set_case_outcome(conn, cid, 1,
                                   resolved_at='2025-03-01T10:00:00Z')
            row = conn.execute(
                'SELECT outcome, outcome_resolved_at FROM decision_cases '
                'WHERE id = ?', (cid,),
            ).fetchone()
        assert ok is True
        assert row[0] == 1
        assert row[1] == '2025-03-01T10:00:00Z'

    def test_default_resolved_at_is_now(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            cid = _insert_case(conn)
            before = datetime.now(timezone.utc)
            set_case_outcome(conn, cid, 0)
            row = conn.execute(
                'SELECT outcome_resolved_at FROM decision_cases WHERE id = ?',
                (cid,),
            ).fetchone()
        # Should be a parseable ISO timestamp roughly around "now".
        assert row[0]
        ts = row[0].replace('Z', '+00:00')
        parsed = datetime.fromisoformat(ts)
        assert (parsed - before).total_seconds() < 5

    def test_missing_case_returns_false(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            assert set_case_outcome(conn, 99999, 1) is False

    def test_rejects_non_binary_outcome(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            cid = _insert_case(conn)
            with pytest.raises(ValueError):
                set_case_outcome(conn, cid, 2)


# ── case_latency_days ─────────────────────────────────────────────────────

class TestCaseLatency:
    def test_computes_days(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            cid = _insert_case(conn, created_at='2025-03-01T10:00:00Z')
            set_case_outcome(conn, cid, 1,
                              resolved_at='2025-03-04T10:00:00Z')
            d = case_latency_days(conn, cid)
        assert d == pytest.approx(3.0, abs=1e-3)

    def test_missing_resolved_at_returns_none(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            cid = _insert_case(conn, created_at='2025-03-01T10:00:00Z')
            assert case_latency_days(conn, cid) is None

    def test_negative_delta_returns_none(self, tmp_db):
        # Resolved before created — corrupt row; refuse to emit.
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            cid = _insert_case(conn, created_at='2025-03-10T10:00:00Z')
            set_case_outcome(conn, cid, 1,
                              resolved_at='2025-03-01T10:00:00Z')
            assert case_latency_days(conn, cid) is None


# ── heuristic_latency_stats ───────────────────────────────────────────────

class TestHeuristicLatency:
    def test_splits_win_loss(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            # Wins cluster tight (1, 2 days); losses are spread (10, 20).
            for created, resolved, out in [
                ('2025-03-01T10:00:00Z', '2025-03-02T10:00:00Z', 1),
                ('2025-03-05T10:00:00Z', '2025-03-07T10:00:00Z', 1),
                ('2025-03-01T10:00:00Z', '2025-03-11T10:00:00Z', 0),
                ('2025-03-01T10:00:00Z', '2025-03-21T10:00:00Z', 0),
            ]:
                cid = _insert_case(conn, created_at=created,
                                    heuristic_ids=[hid])
                set_case_outcome(conn, cid, out, resolved_at=resolved)
            stats = heuristic_latency_stats(conn, hid)
        assert stats['win']['n'] == 2
        assert stats['loss']['n'] == 2
        assert stats['win']['median'] == pytest.approx(1.5, abs=1e-3)
        assert stats['loss']['median'] == pytest.approx(15.0, abs=1e-3)

    def test_ignores_unresolved_cases(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            cid = _insert_case(conn, created_at='2025-03-01T10:00:00Z',
                                heuristic_ids=[hid])
            # Never call set_case_outcome.
            stats = heuristic_latency_stats(conn, hid)
        assert stats['win']['n'] == 0
        assert stats['loss']['n'] == 0

    def test_empty_on_unknown_heuristic(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            stats = heuristic_latency_stats(conn, 99999)
        assert stats['win']['n'] == 0
        assert stats['loss']['mean'] is None
