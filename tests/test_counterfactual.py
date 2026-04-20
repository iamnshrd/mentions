"""Tests for counterfactual heuristic-lift analysis (v0.14.4)."""
from __future__ import annotations

import sqlite3

import pytest

from library._core.eval.counterfactual import (
    _wilson_ci, all_heuristic_lifts, heuristic_lift, kill_list,
)


# ── Pure Wilson helper ────────────────────────────────────────────────────

class TestWilsonCi:
    def test_zero_n_is_uninformative(self):
        p, lo, hi = _wilson_ci(0, 0)
        assert lo == 0.0 and hi == 1.0

    def test_perfect_wins_high_p(self):
        p, lo, hi = _wilson_ci(10, 10)
        assert p == 1.0
        assert lo > 0.6  # tight-ish lower bound

    def test_zero_wins_low_p(self):
        p, lo, hi = _wilson_ci(0, 10)
        assert p == 0.0
        assert hi < 0.4

    def test_half_wins_centred(self):
        p, lo, hi = _wilson_ci(5, 10)
        assert p == 0.5
        assert lo < 0.5 < hi


# ── DB fixtures ───────────────────────────────────────────────────────────

def _insert_heuristic(conn, text='h'):
    conn.execute(
        "INSERT INTO heuristics (heuristic_text, heuristic_type, "
        "market_type, confidence, recurring_count) "
        "VALUES (?, 'entry', 'all', 0.5, 1)",
        (text,),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def _insert_case(conn, *, outcome, linked_heuristics=()):
    conn.execute(
        "INSERT INTO decision_cases (setup, decision, outcome) "
        "VALUES ('x', 'YES', ?)",
        (outcome,),
    )
    cid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    for hid in linked_heuristics:
        conn.execute(
            'INSERT INTO case_principles (case_id, heuristic_id) '
            'VALUES (?, ?)',
            (cid, hid),
        )
    return cid


# ── heuristic_lift ────────────────────────────────────────────────────────

class TestHeuristicLift:
    def test_none_when_no_applied_cases(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            # A case not linked to hid.
            _insert_case(conn, outcome=1)
            conn.commit()
            r = heuristic_lift(conn, hid)
        assert r is None

    def test_none_when_no_baseline_cases(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            _insert_case(conn, outcome=1, linked_heuristics=[hid])
            conn.commit()
            # No cases *without* this heuristic.
            r = heuristic_lift(conn, hid)
        assert r is None

    def test_positive_lift_when_heuristic_wins_more(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            good = _insert_heuristic(conn, text='good')
            # Cases where good fires: 4/5 win.
            for _ in range(4):
                _insert_case(conn, outcome=1, linked_heuristics=[good])
            _insert_case(conn, outcome=0, linked_heuristics=[good])
            # Cases without good: 2/6 win.
            for _ in range(2):
                _insert_case(conn, outcome=1)
            for _ in range(4):
                _insert_case(conn, outcome=0)
            conn.commit()
            r = heuristic_lift(conn, good)
        assert r is not None
        assert r['n_with'] == 5
        assert r['n_without'] == 6
        assert r['wins_with'] == 4
        assert r['wins_without'] == 2
        assert r['lift'] > 0.3
        assert r['p_with'] > r['p_without']

    def test_negative_lift_when_heuristic_correlates_with_losses(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            bad = _insert_heuristic(conn, text='bad')
            # With bad: 1/5 win.
            _insert_case(conn, outcome=1, linked_heuristics=[bad])
            for _ in range(4):
                _insert_case(conn, outcome=0, linked_heuristics=[bad])
            # Without bad: 4/5 win.
            for _ in range(4):
                _insert_case(conn, outcome=1)
            _insert_case(conn, outcome=0)
            conn.commit()
            r = heuristic_lift(conn, bad)
        assert r['lift'] < -0.3

    def test_unresolved_cases_skipped(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            # Unresolved case with heuristic — should be ignored.
            cid = _insert_case(conn, outcome=None, linked_heuristics=[hid])
            # Resolved cases.
            _insert_case(conn, outcome=1, linked_heuristics=[hid])
            _insert_case(conn, outcome=0)
            conn.commit()
            r = heuristic_lift(conn, hid)
        assert r is not None
        assert r['n_with'] == 1   # unresolved row didn't count


# ── all_heuristic_lifts ───────────────────────────────────────────────────

class TestAllLifts:
    def test_ranks_by_lift_descending(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            good = _insert_heuristic(conn, text='good')
            bad  = _insert_heuristic(conn, text='bad')
            # good: 4/4 wins with, 1/4 wins without
            for _ in range(4):
                _insert_case(conn, outcome=1, linked_heuristics=[good])
            _insert_case(conn, outcome=1, linked_heuristics=[bad])
            for _ in range(3):
                _insert_case(conn, outcome=0, linked_heuristics=[bad])
            conn.commit()
            rows = all_heuristic_lifts(conn, min_n_with=3)
        ids = [r['heuristic_id'] for r in rows]
        assert ids.index(good) < ids.index(bad)

    def test_respects_min_n_with(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            hid = _insert_heuristic(conn)
            _insert_case(conn, outcome=1, linked_heuristics=[hid])
            _insert_case(conn, outcome=0)
            conn.commit()
            rows = all_heuristic_lifts(conn, min_n_with=5)
        assert rows == []


# ── kill_list ─────────────────────────────────────────────────────────────

class TestKillList:
    def test_flags_confidently_negative_lift(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            bad = _insert_heuristic(conn, text='bad')
            # Strong evidence bad is bad: 1/10 vs 9/10.
            _insert_case(conn, outcome=1, linked_heuristics=[bad])
            for _ in range(9):
                _insert_case(conn, outcome=0, linked_heuristics=[bad])
            for _ in range(9):
                _insert_case(conn, outcome=1)
            _insert_case(conn, outcome=0)
            conn.commit()
            kl = kill_list(conn, min_n_with=5)
        ids = {r['heuristic_id'] for r in kl}
        assert bad in ids

    def test_spares_high_lift(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            good = _insert_heuristic(conn, text='good')
            for _ in range(9):
                _insert_case(conn, outcome=1, linked_heuristics=[good])
            _insert_case(conn, outcome=0, linked_heuristics=[good])
            _insert_case(conn, outcome=1)
            for _ in range(9):
                _insert_case(conn, outcome=0)
            conn.commit()
            kl = kill_list(conn, min_n_with=5)
        ids = {r['heuristic_id'] for r in kl}
        assert good not in ids
