"""Tests for FTS5 sync triggers (v0.14.6 — D2)."""
from __future__ import annotations

import sqlite3

import pytest


def _insert_doc(conn, title='Doc'):
    conn.execute(
        "INSERT INTO transcript_documents (source_file, title) "
        "VALUES ('x.txt', ?)", (title,),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def _insert_chunk(conn, doc_id, *, text='hello world', speaker='Powell',
                   section='intro'):
    conn.execute(
        '''INSERT INTO transcript_chunks
           (document_id, chunk_index, text, speaker, section)
           VALUES (?, 0, ?, ?, ?)''',
        (doc_id, text, speaker, section),
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def _fts_match(conn, q):
    return conn.execute(
        "SELECT rowid FROM transcript_chunks_fts WHERE transcript_chunks_fts MATCH ?",
        (q,),
    ).fetchall()


class TestSchema:
    def test_version_is_eight(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            v = conn.execute('PRAGMA user_version').fetchone()[0]
        assert v >= 8

    def test_triggers_exist(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='trigger' AND name LIKE 'transcript_chunks_%'"
            ).fetchall()
        names = {r[0] for r in rows}
        assert {'transcript_chunks_ai',
                'transcript_chunks_ad',
                'transcript_chunks_au'} <= names


class TestInsertTrigger:
    def test_fresh_insert_indexed(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            doc = _insert_doc(conn)
            cid = _insert_chunk(conn, doc, text='interest rate cuts')
            conn.commit()
            hits = _fts_match(conn, 'cuts')
        assert cid in {r[0] for r in hits}

    def test_handles_null_speaker_and_section(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            doc = _insert_doc(conn)
            conn.execute(
                '''INSERT INTO transcript_chunks
                   (document_id, chunk_index, text)
                   VALUES (?, 0, ?)''',
                (doc, 'dovish pivot'),
            )
            conn.commit()
            hits = _fts_match(conn, 'dovish')
        assert hits


class TestDeleteTrigger:
    def test_delete_removes_from_fts(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            doc = _insert_doc(conn)
            cid = _insert_chunk(conn, doc, text='uniquetokenxyz')
            conn.commit()
            assert _fts_match(conn, 'uniquetokenxyz')
            conn.execute('DELETE FROM transcript_chunks WHERE id = ?', (cid,))
            conn.commit()
            hits = _fts_match(conn, 'uniquetokenxyz')
        assert hits == []


class TestUpdateTrigger:
    def test_update_refreshes_fts(self, tmp_db):
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            doc = _insert_doc(conn)
            cid = _insert_chunk(conn, doc, text='originalphrase')
            conn.commit()
            assert _fts_match(conn, 'originalphrase')
            conn.execute(
                'UPDATE transcript_chunks SET text = ? WHERE id = ?',
                ('updatedphrase', cid),
            )
            conn.commit()
            # Old text no longer hits.
            assert _fts_match(conn, 'originalphrase') == []
            # New text does.
            assert _fts_match(conn, 'updatedphrase')


class TestCascadeOnDocumentDelete:
    def test_document_delete_cascades_to_fts(self, tmp_db):
        # transcript_chunks cascades on document delete (FK ON DELETE
        # CASCADE); the AD trigger must still fire for each deleted
        # chunk row.
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            doc = _insert_doc(conn)
            _insert_chunk(conn, doc, text='cascadetokenaaa')
            _insert_chunk(conn, doc, text='cascadetokenbbb')
            conn.commit()
            assert _fts_match(conn, 'cascadetokenaaa')
            conn.execute(
                'DELETE FROM transcript_documents WHERE id = ?', (doc,),
            )
            conn.commit()
            assert _fts_match(conn, 'cascadetokenaaa') == []
            assert _fts_match(conn, 'cascadetokenbbb') == []


class TestBackcompatWithSyncHelper:
    def test_sync_document_idempotent_after_trigger_insert(self, tmp_db):
        """sync_document still works (emergency rebuild): it should
        leave the FTS index consistent even when triggers already
        populated it."""
        from agents.mentions.storage.knowledge.fts_sync import sync_document
        with sqlite3.connect(tmp_db) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            doc = _insert_doc(conn)
            _insert_chunk(conn, doc, text='emergencyrebuildtoken')
            conn.commit()
            sync_document(conn, doc)
            conn.commit()
            hits = _fts_match(conn, 'emergencyrebuildtoken')
        # Exactly one row should remain — not duplicated by the
        # rebuild-after-trigger sequence.
        assert len(hits) == 1
