"""Tests for anti-pattern / crowd-mistake / dispute-pattern detection."""
from __future__ import annotations

import sqlite3

import pytest

from agents.mentions.services.analysis.anti_patterns import (
    check_anti_patterns,
)
from mentions_domain.analysis.anti_patterns import (
    apply_anti_patterns_to_p_signal as apply_to_p_signal,
)


def _seed_doc(db_path, idx: int) -> int:
    """Insert a transcript document and return its id."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''INSERT INTO transcript_documents
               (speaker, event, source_file, status, source_type)
               VALUES ('', ?, ?, 'indexed', 'file')''',
            (f'event-{idx}', f'/tmp/doc-{idx}.txt'),
        )
        doc_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.commit()
    return doc_id


def _seed_anti_pattern(db_path, doc_id: int, text: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''INSERT INTO anti_patterns
               (pattern_text, why_bad, example_document_id)
               VALUES (?, ?, ?)''',
            (text, 'because reasons', doc_id),
        )
        conn.commit()


def _seed_crowd_mistake(db_path, doc_id: int, name: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''INSERT INTO crowd_mistakes
               (mistake_name, mistake_type, description, example_document_id)
               VALUES (?, ?, ?, ?)''',
            (name, 'entry_timing', 'retail piles in too early', doc_id),
        )
        conn.commit()


def _seed_dispute(db_path, doc_id: int, name: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''INSERT INTO dispute_patterns
               (pattern_name, dispute_type, description,
                example_document_id)
               VALUES (?, ?, ?, ?)''',
            (name, 'settlement_ambiguity', 'rules unclear', doc_id),
        )
        conn.commit()


# ── Detection ──────────────────────────────────────────────────────────────

class TestDetection:
    def test_empty_bundle_returns_no_warnings(self, tmp_db):
        w = check_anti_patterns({'doc_ids': []})
        assert w['any_triggered'] is False
        assert w['flags'] == []
        assert w['factor_ps'] == {}

    def test_no_doc_ids_key_is_safe(self, tmp_db):
        w = check_anti_patterns({})
        assert w['any_triggered'] is False

    def test_matched_anti_pattern_surfaces(self, tmp_db):
        doc_id = _seed_doc(tmp_db, 1)
        _seed_anti_pattern(tmp_db, doc_id,
                           'Piling in at round numbers like 50¢')
        w = check_anti_patterns({'doc_ids': [doc_id]})
        assert w['any_triggered'] is True
        assert len(w['anti_patterns']) == 1
        assert any('Anti-pattern' in f for f in w['flags'])
        assert 'anti_pattern' in w['factor_ps']

    def test_all_three_categories(self, tmp_db):
        doc_id = _seed_doc(tmp_db, 2)
        _seed_anti_pattern(tmp_db, doc_id, 'a bad idea')
        _seed_crowd_mistake(tmp_db, doc_id, 'M1')
        _seed_dispute(tmp_db, doc_id, 'D1')
        w = check_anti_patterns({'doc_ids': [doc_id]})
        assert len(w['anti_patterns']) == 1
        assert len(w['crowd_mistakes']) == 1
        assert len(w['dispute_patterns']) == 1
        assert set(w['factor_ps'].keys()) == {
            'anti_pattern', 'crowd_mistake', 'dispute_pattern',
        }
        assert len(w['flags']) == 3

    def test_unrelated_doc_no_match(self, tmp_db):
        doc_a = _seed_doc(tmp_db, 10)
        doc_b = _seed_doc(tmp_db, 11)
        _seed_anti_pattern(tmp_db, doc_a, 'applies to A')
        # Query only for doc_b → no rows.
        w = check_anti_patterns({'doc_ids': [doc_b]})
        assert w['any_triggered'] is False


# ── p_signal adjustment ────────────────────────────────────────────────────

class TestApplyToSignal:
    def test_no_warnings_passes_through(self, tmp_db):
        w = {'factor_ps': {}, 'any_triggered': False}
        assert apply_to_p_signal(0.7, w) == 0.7

    def test_warnings_lower_signal(self, tmp_db):
        w = {'factor_ps': {'anti_pattern': 0.42}, 'any_triggered': True}
        adjusted = apply_to_p_signal(0.7, w)
        assert adjusted is not None
        assert adjusted < 0.7

    def test_multiple_warnings_compound_downweight(self, tmp_db):
        one = apply_to_p_signal(0.7, {
            'factor_ps': {'anti_pattern': 0.42},
            'any_triggered': True,
        })
        two = apply_to_p_signal(0.7, {
            'factor_ps': {'anti_pattern': 0.42, 'dispute_pattern': 0.40},
            'any_triggered': True,
        })
        assert two < one

    def test_none_signal_stays_none(self, tmp_db):
        w = {'factor_ps': {'anti_pattern': 0.42}, 'any_triggered': True}
        assert apply_to_p_signal(None, w) is None
