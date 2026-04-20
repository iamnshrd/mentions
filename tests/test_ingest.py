"""End-to-end tests for agents.mentions.ingest.transcript.

Exercises the full pipeline:
  read file → normalise → chunk → upsert document → insert chunks → FTS sync

Against a temp DB via the `tmp_db` fixture. Uses a .txt fixture (PDF
extraction is mocked out by pointing at plain text).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT = '''Alice: Welcome everyone to the podcast. Today we are discussing prediction markets and the role of Kalshi.
Bob: Thanks for having me. I have been trading on Kalshi for about two years now and the pricing is getting tighter.
Alice: Let us talk about entry pricing. What do you do when a contract is at eighty cents and you think it should be ninety?
Bob: I usually scale in rather than going full size. Liquidity is the main constraint. If I see a big book I will sweep it.
Alice: And what about exits? When do you close out?
Bob: I have a rule. If the thesis plays out faster than expected I take profit early. Time decay is brutal on these contracts.
Alice: [Applause] Great insights. Let us move to a specific case study.
Bob: Sure. Take the election night 2024 contracts. Spread was fifteen cents at open which is enormous.
Alice: So what was your play?
Bob: I waited for the announcer to call the state and then scaled in. Classic post-event drift pattern.
Alice: Makes sense. Thanks for joining us today.
Bob: My pleasure.'''


def _write_transcript(tmp_path: Path, name: str = 'sample.txt',
                      content: str = SAMPLE_TRANSCRIPT) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding='utf-8')
    return p


# ── register() ─────────────────────────────────────────────────────────────

class TestRegister:
    def test_happy_path_creates_document_and_chunks(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        result = register(str(src), speaker='Bob', event='Podcast 2024',
                          event_date='2024-05-01')

        assert result['status'] == 'indexed'
        assert result['document_id'] > 0
        assert result['chunks'] >= 1
        assert result['tokens'] > 0
        assert result['language'] == 'en'
        assert result['trace']['document_id'] == result['document_id']
        assert result['trace']['chunk_count'] == result['chunks']
        assert len(result['trace']['chunk_ids']) == result['chunks']

    def test_register_returns_traceability_payload(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        result = register(str(src), speaker='Bob')

        trace = result['trace']
        assert trace['source_file'] == str(src)
        assert len(trace['sha256']) == 64
        assert trace['chunk_count'] >= 1
        assert trace['chunk_preview']
        assert trace['chunk_preview'][0]['chunk_id'] == trace['chunk_ids'][0]

    def test_document_row_has_v2_columns_populated(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        result = register(str(src), speaker='Bob', event='Podcast')

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                '''SELECT source_file, speaker, event, status, source_type,
                          language, sha256, summary, char_count, token_count
                   FROM transcript_documents WHERE id = ?''',
                (result['document_id'],),
            ).fetchone()
        assert row is not None
        (source_file, speaker, event, status, source_type,
         language, sha256, summary, char_count, token_count) = row
        assert source_file == str(src)
        assert speaker == 'Bob'
        assert event == 'Podcast'
        assert status == 'indexed'
        assert source_type == 'file'
        assert language == 'en'
        assert len(sha256) == 64       # sha256 hex
        assert len(summary) > 0
        assert char_count > 0
        assert token_count > 0

    def test_chunk_rows_have_v2_columns_populated(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        result = register(str(src), speaker='Bob')

        with sqlite3.connect(tmp_db) as conn:
            rows = conn.execute(
                '''SELECT chunk_index, text, speaker, char_start, char_end,
                          token_count, speaker_turn_id, text_sha1
                   FROM transcript_chunks
                   WHERE document_id = ?
                   ORDER BY chunk_index''',
                (result['document_id'],),
            ).fetchall()

        assert len(rows) == result['chunks']
        for idx, (ci, text, speaker, cs, ce, tok, turn_id, sha) in enumerate(rows):
            assert ci == idx
            assert text.strip()
            assert cs >= 0
            assert ce >= cs
            assert tok > 0
            assert len(sha) == 40       # sha1 hex
            # speaker can be empty for monologue-ish mixes; turn_id should
            # be a non-negative int.
            assert turn_id is None or turn_id >= 0

    def test_stage_directions_stripped_from_chunks(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        result = register(str(src), speaker='Bob')
        with sqlite3.connect(tmp_db) as conn:
            joined = ' '.join(
                r[0] for r in conn.execute(
                    'SELECT text FROM transcript_chunks WHERE document_id = ?',
                    (result['document_id'],),
                ).fetchall()
            )
        # '[Applause]' was in the source — clean_transcript_text removes it.
        assert '[Applause]' not in joined

    def test_fts_index_contains_document(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        result = register(str(src), speaker='Bob')

        with sqlite3.connect(tmp_db) as conn:
            # FTS lookup for a word we know is in the transcript.
            rows = conn.execute(
                '''SELECT rowid FROM transcript_chunks_fts
                   WHERE transcript_chunks_fts MATCH 'Kalshi' '''
            ).fetchall()
        assert len(rows) >= 1
        # And those rowids belong to the freshly-indexed document.
        with sqlite3.connect(tmp_db) as conn:
            matched_doc_ids = {r[0] for r in conn.execute(
                f'''SELECT document_id FROM transcript_chunks
                    WHERE id IN ({','.join(str(r[0]) for r in rows)})'''
            ).fetchall()}
        assert result['document_id'] in matched_doc_ids

    def test_idempotent_second_call_skips_reindex(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        first  = register(str(src), speaker='Bob')
        second = register(str(src), speaker='Bob')

        assert first['status']  == 'indexed'
        assert second['status'] == 'already_indexed'
        assert first['document_id'] == second['document_id']

        # Chunk count should not double.
        with sqlite3.connect(tmp_db) as conn:
            n = conn.execute(
                'SELECT COUNT(*) FROM transcript_chunks WHERE document_id = ?',
                (first['document_id'],),
            ).fetchone()[0]
        assert n == first['chunks']

    def test_sha_change_reindexes_chunks_and_metadata(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        src = _write_transcript(tmp_path)
        first = register(str(src), speaker='Bob')

        with sqlite3.connect(tmp_db) as conn:
            sha_before = conn.execute(
                'SELECT sha256 FROM transcript_documents WHERE id = ?',
                (first['document_id'],),
            ).fetchone()[0]
            chunks_before = conn.execute(
                'SELECT COUNT(*) FROM transcript_chunks WHERE document_id = ?',
                (first['document_id'],),
            ).fetchone()[0]

        # Modify file on disk; register should notice.
        src.write_text(SAMPLE_TRANSCRIPT + '\nAlice: One more thing.\n',
                       encoding='utf-8')
        second = register(str(src), speaker='Bob')

        with sqlite3.connect(tmp_db) as conn:
            sha_after = conn.execute(
                'SELECT sha256 FROM transcript_documents WHERE id = ?',
                (first['document_id'],),
            ).fetchone()[0]
            chunks_after = conn.execute(
                'SELECT COUNT(*) FROM transcript_chunks WHERE document_id = ?',
                (first['document_id'],),
            ).fetchone()[0]

        assert sha_before != sha_after
        assert second['status'] == 'reindexed'
        assert second['document_id'] == first['document_id']
        assert second['content_changed'] is True
        assert chunks_after >= chunks_before
        assert second['trace']['chunk_count'] == chunks_after

    def test_register_errors_on_invalid_transcript_schema(self, tmp_path, monkeypatch):
        from agents.mentions import config as cfg
        from agents.mentions.ingest.transcript import register
        broken_db = tmp_path / 'broken.db'
        monkeypatch.setattr(cfg, 'DB_PATH', broken_db)
        src = _write_transcript(tmp_path)

        with sqlite3.connect(broken_db) as conn:
            conn.executescript('''
                CREATE TABLE transcript_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT UNIQUE,
                    status TEXT
                );
                CREATE TABLE transcript_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    chunk_index INTEGER,
                    text TEXT
                );
                PRAGMA user_version = 10;
            ''')

        result = register(str(src), speaker='Bob')
        assert result['status'] == 'error'
        assert result['error_code'] == 'schema_invalid'
        assert 'Transcript schema contract' in result['error']

    def test_missing_file_returns_error(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        result = register(str(tmp_path / 'does_not_exist.txt'))
        assert result['status'] == 'error'
        assert 'not found' in result['error'].lower()

    def test_unsupported_format_returns_error(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register
        p = tmp_path / 'weird.xyz'
        p.write_text('hello', encoding='utf-8')
        result = register(str(p))
        assert result['status'] == 'error'

    def test_relative_path_resolves_via_transcripts_dir(
        self, tmp_db, tmp_path, monkeypatch,
    ):
        """When source_file isn't absolute, it's resolved under TRANSCRIPTS."""
        from agents.mentions import config as cfg
        monkeypatch.setattr(cfg, 'TRANSCRIPTS', tmp_path)
        src = _write_transcript(tmp_path, 'mytranscript.txt')

        from agents.mentions.ingest.transcript import register
        result = register('mytranscript.txt', speaker='Bob')
        assert result['status'] == 'indexed'
        # Stored path should be the resolved absolute one.
        assert src.name in result['file']


# ── rechunk() ──────────────────────────────────────────────────────────────

class TestRechunk:
    def test_rechunk_replaces_chunks(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register, rechunk
        src = _write_transcript(tmp_path)
        first = register(str(src), speaker='Bob')

        with sqlite3.connect(tmp_db) as conn:
            sha_ids_before = {r[0] for r in conn.execute(
                'SELECT text_sha1 FROM transcript_chunks WHERE document_id = ?',
                (first['document_id'],),
            ).fetchall()}

        result = rechunk(first['document_id'])
        assert result['status'] == 'rechunked'
        assert result['document_id'] == first['document_id']
        assert result['chunks'] >= 1

        with sqlite3.connect(tmp_db) as conn:
            sha_ids_after = {r[0] for r in conn.execute(
                'SELECT text_sha1 FROM transcript_chunks WHERE document_id = ?',
                (first['document_id'],),
            ).fetchall()}
        # Same source → same content → same sha1s. If this ever fails it
        # signals non-determinism in the chunker, which we do NOT want.
        assert sha_ids_before == sha_ids_after

    def test_rechunk_unknown_doc_returns_error(self, tmp_db):
        from agents.mentions.ingest.transcript import rechunk
        result = rechunk(99999)
        assert result['status'] == 'error'
        assert '99999' in result['error']

    def test_rechunk_missing_source_returns_error(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register, rechunk
        src = _write_transcript(tmp_path)
        first = register(str(src), speaker='Bob')
        src.unlink()

        result = rechunk(first['document_id'])
        assert result['status'] == 'error'
        assert 'missing' in result['error'].lower()

    def test_rechunk_all_via_api(self, tmp_db, tmp_path):
        """Bulk rechunk can be composed from the canonical transcript API."""
        from agents.mentions.ingest.transcript import register, rechunk
        # Seed a couple of documents.
        src1 = _write_transcript(tmp_path, 'a.txt')
        src2 = _write_transcript(tmp_path, 'b.txt',
                                 content=SAMPLE_TRANSCRIPT + '\nAlice: extra.')
        register(str(src1), speaker='Bob')
        register(str(src2), speaker='Bob')

        from agents.mentions.db import connect
        with connect() as conn:
            doc_ids = [r[0] for r in conn.execute(
                'SELECT id FROM transcript_documents ORDER BY id'
            ).fetchall()]
        results = [rechunk(doc_id) for doc_id in doc_ids]
        summary = {
            'status': 'rechunked_all',
            'total_docs': len(results),
            'ok': sum(1 for r in results if r['status'] == 'rechunked'),
            'errors': sum(1 for r in results if r['status'] == 'error'),
            'total_chunks': sum(r.get('chunks', 0) for r in results),
        }
        assert summary['status'] == 'rechunked_all'
        assert summary['total_docs'] == 2
        assert summary['ok'] == 2
        assert summary['errors'] == 0
        assert summary['total_chunks'] >= 2

    def test_rechunk_single_via_api(self, tmp_db, tmp_path):
        from agents.mentions.ingest.transcript import register, rechunk
        src = _write_transcript(tmp_path)
        r = register(str(src), speaker='Bob')
        payload = rechunk(r['document_id'])
        assert payload['status'] == 'rechunked'
        assert payload['document_id'] == r['document_id']
        assert payload['trace']['document_id'] == r['document_id']

    def test_rechunk_syncs_fts(self, tmp_db, tmp_path):
        """After rechunk, FTS rows should match current chunks."""
        from agents.mentions.ingest.transcript import register, rechunk
        src = _write_transcript(tmp_path)
        first = register(str(src), speaker='Bob')
        rechunk(first['document_id'])

        with sqlite3.connect(tmp_db) as conn:
            n_chunks = conn.execute(
                'SELECT COUNT(*) FROM transcript_chunks WHERE document_id = ?',
                (first['document_id'],),
            ).fetchone()[0]
            n_fts = conn.execute(
                '''SELECT COUNT(*) FROM transcript_chunks_fts
                   WHERE rowid IN (
                     SELECT id FROM transcript_chunks WHERE document_id = ?
                   )''',
                (first['document_id'],),
            ).fetchone()[0]
        assert n_chunks == n_fts
