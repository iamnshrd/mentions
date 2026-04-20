"""Tests for chunk-level canonical speaker attribution at ingest + retrieval."""
from __future__ import annotations

import json
import sqlite3

import pytest

from agents.mentions.services.speakers.canonicalize import invalidate_cache
from mentions_domain.retrieval import RetrievalHit
from agents.mentions.services.retrieval import reliability


@pytest.fixture(autouse=True)
def _fresh_cache():
    invalidate_cache()
    yield
    invalidate_cache()


def _insert_profile(conn, canonical, aliases=None, alpha=1.0, beta=1.0):
    conn.execute(
        '''INSERT INTO speaker_profiles
           (canonical_name, aliases, alpha, beta)
           VALUES (?, ?, ?, ?)''',
        (canonical, json.dumps(aliases) if aliases else None, alpha, beta),
    )
    conn.commit()


# ── Retrieval hit carries canonical ───────────────────────────────────────

class TestHitShape:
    def test_default_canonical_is_empty(self):
        h = RetrievalHit(chunk_id=1, document_id=1, text='', speaker='Powell',
                         section='', event='', event_date='', token_count=0)
        assert h.speaker_canonical == ''

    def test_canonical_explicit(self):
        h = RetrievalHit(chunk_id=1, document_id=1, text='', speaker='Powell',
                         section='', event='', event_date='', token_count=0,
                         speaker_canonical='Jerome Powell')
        assert h.speaker_canonical == 'Jerome Powell'


# ── apply_weights prefers canonical ───────────────────────────────────────

class TestApplyWeightsUsesCanonical:
    def test_canonical_key_beats_raw(self):
        h = RetrievalHit(chunk_id=1, document_id=1, text='',
                         speaker='Chair Powell',
                         section='', event='', event_date='', token_count=0,
                         speaker_canonical='Jerome Powell')
        h.score_final = 1.0
        reliability.apply_weights(
            [h], {'jerome powell': 1.4, 'chair powell': 0.8})
        # Canonical key wins — 1.4 applied, not 0.8.
        assert h.score_reliability == 1.4
        assert h.score_final == pytest.approx(1.4)

    def test_falls_back_to_raw_when_canonical_empty(self):
        h = RetrievalHit(chunk_id=1, document_id=1, text='',
                         speaker='Chair Powell',
                         section='', event='', event_date='', token_count=0)
        h.score_final = 1.0
        reliability.apply_weights([h], {'chair powell': 0.8})
        assert h.score_reliability == 0.8
        assert h.score_final == pytest.approx(0.8)


# ── Column is nullable ────────────────────────────────────────────────────

class TestColumnNullable:
    def test_manual_insert_without_canonical_ok(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute(
                "INSERT INTO transcript_documents (source_file) VALUES ('x.txt')"
            )
            doc = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.execute(
                '''INSERT INTO transcript_chunks
                   (document_id, chunk_index, text, speaker)
                   VALUES (?, 0, 'body', 'Unknown')''',
                (doc,),
            )
            conn.commit()
            val = conn.execute(
                'SELECT speaker_canonical FROM transcript_chunks'
            ).fetchone()[0]
        assert val is None
