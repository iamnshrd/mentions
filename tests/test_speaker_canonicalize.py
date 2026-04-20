"""Tests for surface-name → canonical-profile resolver (v0.14.6 — T1)."""
from __future__ import annotations

import json
import sqlite3

import pytest

from agents.mentions.services.speakers.canonicalize import (
    canonicalize, canonicalize_batch, invalidate_cache,
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    invalidate_cache()
    yield
    invalidate_cache()


def _insert_profile(conn, canonical, aliases=None):
    conn.execute(
        '''INSERT INTO speaker_profiles (canonical_name, aliases)
           VALUES (?, ?)''',
        (canonical, json.dumps(aliases) if aliases else None),
    )
    conn.commit()


# ── Schema ────────────────────────────────────────────────────────────────

class TestSchema:
    def test_version_at_least_nine(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            v = conn.execute('PRAGMA user_version').fetchone()[0]
        assert v >= 9

    def test_speaker_canonical_column(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            cols = [r[1] for r in conn.execute(
                'PRAGMA table_info(transcript_chunks)').fetchall()]
        assert 'speaker_canonical' in cols


# ── Canonicalize matching ─────────────────────────────────────────────────

class TestExactMatch:
    def test_exact_canonical_ignoring_case(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            _insert_profile(conn, 'Jerome Powell')
            assert canonicalize('jerome powell', conn=conn) == 'Jerome Powell'
            assert canonicalize('JEROME POWELL', conn=conn) == 'Jerome Powell'
            assert canonicalize('Jerome Powell', conn=conn) == 'Jerome Powell'


class TestAliasMatch:
    def test_alias_resolves(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            _insert_profile(conn, 'Jerome Powell',
                            aliases=['Chair Powell', 'J. Powell'])
            invalidate_cache()
            assert canonicalize('Chair Powell', conn=conn) == 'Jerome Powell'
            assert canonicalize('j. powell', conn=conn) == 'Jerome Powell'

    def test_malformed_aliases_ignored(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute(
                "INSERT INTO speaker_profiles (canonical_name, aliases) "
                "VALUES ('X', 'not-json')"
            )
            conn.commit()
            # Exact still works, aliases silently dropped.
            assert canonicalize('X', conn=conn) == 'X'


class TestSuffixMatch:
    def test_unique_suffix_resolves(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            _insert_profile(conn, 'Jerome Powell')
            invalidate_cache()
            assert canonicalize('Powell', conn=conn) == 'Jerome Powell'
            assert canonicalize('Chair Powell', conn=conn) == 'Jerome Powell'

    def test_ambiguous_suffix_returns_none(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            _insert_profile(conn, 'Jerome Powell')
            _insert_profile(conn, 'Colin Powell')
            invalidate_cache()
            # Two canonicals end in 'Powell' — we refuse to guess.
            assert canonicalize('Powell', conn=conn) is None


class TestNoMatch:
    def test_unknown_returns_none(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            _insert_profile(conn, 'Jerome Powell')
            invalidate_cache()
            assert canonicalize('Janet Yellen', conn=conn) is None

    def test_empty_surface_returns_none(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            _insert_profile(conn, 'Jerome Powell')
            assert canonicalize('', conn=conn) is None
            assert canonicalize('   ', conn=conn) is None

    def test_no_conn_or_profiles(self):
        assert canonicalize('Powell') is None


# ── Batch ─────────────────────────────────────────────────────────────────

class TestBatch:
    def test_batch_resolves_all_forms(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            _insert_profile(conn, 'Jerome Powell',
                            aliases=['Chair Powell'])
            _insert_profile(conn, 'Janet Yellen')
            invalidate_cache()
            out = canonicalize_batch(
                ['Jerome Powell', 'Chair Powell', 'Powell',
                 'Yellen', 'Nobody'],
                conn)
        assert out['Jerome Powell'] == 'Jerome Powell'
        assert out['Chair Powell'] == 'Jerome Powell'
        assert out['Powell'] == 'Jerome Powell'
        assert out['Yellen'] == 'Janet Yellen'
        assert out['Nobody'] is None


# ── Cache invalidation ────────────────────────────────────────────────────

class TestCache:
    def test_invalidate_picks_up_new_profile(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            # No profile yet → miss.
            assert canonicalize('Powell', conn=conn) is None
            _insert_profile(conn, 'Jerome Powell')
            # Without invalidation, the cached empty list is still used.
            # Contract: callers must invalidate after profile writes.
            invalidate_cache()
            assert canonicalize('Powell', conn=conn) == 'Jerome Powell'
