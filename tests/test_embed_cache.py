"""Tests for the persistent chunk-embedding cache."""
from __future__ import annotations

import sqlite3

import pytest

from library._core.retrieve import embed_cache


# ── Pack / unpack ──────────────────────────────────────────────────────────

class TestPackUnpack:
    def test_round_trip_preserves_values(self):
        vec = [0.0, 1.5, -3.25, 1e-6, -42.0]
        blob = embed_cache._pack(vec)
        out = embed_cache._unpack(blob, dim=len(vec))
        assert out == pytest.approx(vec, abs=1e-6)

    def test_pack_is_four_bytes_per_dim(self):
        vec = [1.0] * 384
        blob = embed_cache._pack(vec)
        assert len(blob) == 384 * 4

    def test_unpack_rejects_wrong_dim(self):
        blob = embed_cache._pack([1.0, 2.0, 3.0])
        with pytest.raises(ValueError):
            embed_cache._unpack(blob, dim=4)


# ── DB round trip ──────────────────────────────────────────────────────────

class TestPersistence:
    def test_put_then_get(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            # chunk row must exist for the FK, but we skip by disabling FK.
            # Keep it simple: FK off.
            conn.execute('PRAGMA foreign_keys = OFF')
            n = embed_cache.put_many(conn, 'm1', [
                (1, [0.1, 0.2, 0.3]),
                (2, [0.4, 0.5, 0.6]),
            ])
            assert n == 2
            out = embed_cache.get_many(conn, [1, 2], 'm1')
            assert set(out.keys()) == {1, 2}
            assert out[1] == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)
            assert out[2] == pytest.approx([0.4, 0.5, 0.6], abs=1e-6)

    def test_partial_hit(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = OFF')
            embed_cache.put_many(conn, 'm1', [(1, [1.0, 2.0])])
            out = embed_cache.get_many(conn, [1, 2, 3], 'm1')
            assert set(out.keys()) == {1}

    def test_different_models_do_not_collide(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = OFF')
            embed_cache.put_many(conn, 'small', [(1, [1.0, 2.0])])
            embed_cache.put_many(conn, 'big',   [(1, [9.0, 9.0, 9.0, 9.0])])
            got_s = embed_cache.get_many(conn, [1], 'small')
            got_b = embed_cache.get_many(conn, [1], 'big')
            assert len(got_s[1]) == 2
            assert len(got_b[1]) == 4

    def test_upsert_overwrites(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = OFF')
            embed_cache.put_many(conn, 'm', [(1, [1.0, 2.0])])
            embed_cache.put_many(conn, 'm', [(1, [9.0, 8.0])])
            out = embed_cache.get_many(conn, [1], 'm')
            assert out[1] == pytest.approx([9.0, 8.0], abs=1e-6)

    def test_empty_inputs_safe(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            assert embed_cache.put_many(conn, 'm', []) == 0
            assert embed_cache.put_many(conn, '', [(1, [1.0])]) == 0
            assert embed_cache.get_many(conn, [], 'm') == {}
            assert embed_cache.get_many(conn, [1], '') == {}

    def test_mixed_dims_rejected(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = OFF')
            n = embed_cache.put_many(conn, 'm', [
                (1, [1.0, 2.0]),
                (2, [1.0, 2.0, 3.0]),
            ])
            assert n == 0

    def test_count_and_clear(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = OFF')
            embed_cache.put_many(conn, 'a', [(1, [1.0])])
            embed_cache.put_many(conn, 'b', [(1, [1.0]), (2, [1.0])])
            assert embed_cache.count(conn) == 3
            assert embed_cache.count(conn, 'a') == 1
            assert embed_cache.count(conn, 'b') == 2
            deleted = embed_cache.clear(conn, 'a')
            assert deleted == 1
            assert embed_cache.count(conn) == 2
            embed_cache.clear(conn)
            assert embed_cache.count(conn) == 0


# ── Migration presence ────────────────────────────────────────────────────

class TestMigration:
    def test_table_exists_at_v3(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                '''SELECT name FROM sqlite_master
                   WHERE type='table' AND name='chunk_embeddings' ''',
            ).fetchone()
            assert row is not None
            ver = conn.execute('PRAGMA user_version').fetchone()[0]
            assert ver >= 3
