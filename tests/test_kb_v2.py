"""Tests for v2 schema + PMT importer + structured query layer."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


V2_TABLES = {
    'speaker_profiles', 'event_formats', 'market_archetypes',
    'heuristics', 'heuristic_evidence',
    'pricing_signals', 'phase_logic',
    'crowd_mistakes', 'anti_patterns',
    'execution_patterns', 'dispute_patterns', 'live_trading_tells',
    'sizing_lessons', 'decision_cases',
    'case_principles', 'case_anti_patterns', 'case_crowd_mistakes',
    'case_dispute_patterns', 'case_execution_patterns',
    'case_live_trading_tells', 'case_pricing_signals',
    'case_speaker_profiles',
}

V2_TRANSCRIPT_DOC_COLS = {
    'external_id', 'source_type', 'language', 'sha256',
    'summary', 'title', 'source_url', 'channel', 'char_count', 'token_count',
}

V2_TRANSCRIPT_CHUNK_COLS = {
    'char_start', 'char_end', 'token_count',
    'timestamp_start', 'timestamp_end', 'speaker_turn_id', 'text_sha1',
}


def test_v2_tables_present(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r[0] for r in rows}
    missing = V2_TABLES - names
    assert not missing, f'missing v2 tables: {missing}'


def test_v2_extended_columns(tmp_db):
    with sqlite3.connect(tmp_db) as conn:
        doc_cols = {r[1] for r in conn.execute('PRAGMA table_info(transcript_documents)')}
        chk_cols = {r[1] for r in conn.execute('PRAGMA table_info(transcript_chunks)')}
    assert V2_TRANSCRIPT_DOC_COLS.issubset(doc_cols), (
        f'missing doc cols: {V2_TRANSCRIPT_DOC_COLS - doc_cols}')
    assert V2_TRANSCRIPT_CHUNK_COLS.issubset(chk_cols), (
        f'missing chunk cols: {V2_TRANSCRIPT_CHUNK_COLS - chk_cols}')


def test_schema_version_is_latest(tmp_db):
    from library._core.kb.migrate import LATEST_VERSION
    with sqlite3.connect(tmp_db) as conn:
        v = conn.execute('PRAGMA user_version').fetchone()[0]
    assert v == LATEST_VERSION
    # Sanity: v2 work must stay applied even as the latest advances.
    assert v >= 2


# ── Importer ───────────────────────────────────────────────────────────────

def _make_pmt_fixture(path: Path) -> Path:
    """Build a minimal PMT-shaped DB with one video + one heuristic."""
    db = path / 'pmt_fixture.db'
    with sqlite3.connect(db) as conn:
        conn.executescript('''
            CREATE TABLE videos (
                video_id TEXT PRIMARY KEY, title TEXT NOT NULL,
                source_channel TEXT, source_url TEXT NOT NULL,
                channel_url TEXT, local_txt_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ok',
                text_length INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL UNIQUE,
                clean_text TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                source_type TEXT NOT NULL DEFAULT 'youtube_auto',
                ingested_at TEXT NOT NULL
            );
            CREATE TABLE transcript_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                transcript_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                token_estimate INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE heuristics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                heuristic_text TEXT NOT NULL,
                heuristic_type TEXT NOT NULL,
                market_type TEXT, confidence REAL,
                recurring_count INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE heuristic_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                heuristic_id INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                chunk_id INTEGER,
                quote_text TEXT NOT NULL,
                evidence_strength REAL,
                context_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE speaker_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker_name TEXT NOT NULL UNIQUE,
                speaker_type TEXT, description TEXT,
                behavior_style TEXT, favored_topics TEXT, avoid_topics TEXT,
                qna_style TEXT, adaptation_notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE event_formats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                format_name TEXT NOT NULL UNIQUE,
                domain TEXT, description TEXT,
                has_prepared_remarks INTEGER, has_qna INTEGER,
                qna_probability TEXT, usual_market_effects TEXT,
                format_risk_notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE market_archetypes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE, archetype_type TEXT,
                description TEXT, pricing_drivers TEXT,
                common_edges TEXT, common_traps TEXT,
                liquidity_profile TEXT, repeatability TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE pricing_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_name TEXT NOT NULL UNIQUE, signal_type TEXT,
                description TEXT, interpretation TEXT,
                typical_action TEXT, confidence REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE phase_logic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_name TEXT NOT NULL, event_format_id INTEGER,
                description TEXT, what_becomes_more_likely TEXT,
                what_becomes_less_likely TEXT, common_pricing_errors TEXT,
                execution_notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(phase_name, event_format_id)
            );
            CREATE TABLE crowd_mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mistake_name TEXT NOT NULL UNIQUE, mistake_type TEXT,
                description TEXT, why_it_happens TEXT, how_to_exploit TEXT,
                example_video_id TEXT, example_chunk_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE anti_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_text TEXT NOT NULL, why_bad TEXT NOT NULL,
                example_video_id TEXT, example_chunk_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE execution_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL UNIQUE, execution_type TEXT,
                description TEXT, best_used_when TEXT, avoid_when TEXT,
                risk_note TEXT, example_video_id TEXT, example_chunk_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE dispute_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL UNIQUE, dispute_type TEXT,
                description TEXT, common_confusion TEXT,
                market_impact TEXT, mitigation TEXT,
                example_video_id TEXT, example_chunk_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE live_trading_tells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tell_name TEXT NOT NULL UNIQUE, tell_type TEXT,
                description TEXT, interpretation TEXT,
                typical_response TEXT, risk_note TEXT,
                example_video_id TEXT, example_chunk_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE sizing_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_text TEXT NOT NULL UNIQUE, lesson_type TEXT,
                description TEXT, applies_to TEXT, risk_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE decision_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL, chunk_id INTEGER,
                market_context TEXT, setup TEXT, decision TEXT,
                reasoning TEXT, risk_note TEXT, outcome_note TEXT,
                tags TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE case_principles (case_id INTEGER, heuristic_id INTEGER,
                PRIMARY KEY(case_id, heuristic_id));
            CREATE TABLE case_anti_patterns (case_id INTEGER, anti_pattern_id INTEGER,
                PRIMARY KEY(case_id, anti_pattern_id));
            CREATE TABLE case_crowd_mistakes (case_id INTEGER, crowd_mistake_id INTEGER,
                PRIMARY KEY(case_id, crowd_mistake_id));
            CREATE TABLE case_dispute_patterns (case_id INTEGER, dispute_pattern_id INTEGER,
                PRIMARY KEY(case_id, dispute_pattern_id));
            CREATE TABLE case_execution_patterns (case_id INTEGER, execution_pattern_id INTEGER,
                PRIMARY KEY(case_id, execution_pattern_id));
            CREATE TABLE case_live_trading_tells (case_id INTEGER, live_trading_tell_id INTEGER,
                PRIMARY KEY(case_id, live_trading_tell_id));
            CREATE TABLE case_pricing_signals (case_id INTEGER, pricing_signal_id INTEGER,
                PRIMARY KEY(case_id, pricing_signal_id));
            CREATE TABLE case_speaker_profiles (case_id INTEGER, speaker_profile_id INTEGER,
                PRIMARY KEY(case_id, speaker_profile_id));
        ''')
        conn.execute(
            '''INSERT INTO videos VALUES
               ('v1','Test Vid','TestChan','https://x/v1','https://x',
                '/tmp/v1.txt','ok',500,'2026-01-01','2026-01-01')''')
        conn.execute(
            '''INSERT INTO transcripts (video_id, clean_text, ingested_at)
               VALUES ('v1','Powell hints at rate cuts. Market reacts.','2026-01-01')''')
        conn.execute(
            '''INSERT INTO transcript_chunks
               (video_id, transcript_id, chunk_index, text, char_start,
                char_end, token_estimate, created_at)
               VALUES ('v1', 1, 0, 'Powell hints at rate cuts.',
                       0, 27, 6, '2026-01-01')''')
        conn.execute(
            '''INSERT INTO heuristics
               (heuristic_text, heuristic_type, market_type, confidence,
                recurring_count)
               VALUES ('Listen to what the chair says, not what the market does.',
                       'interpretation', 'fed', 0.8, 3)''')
        conn.execute(
            '''INSERT INTO heuristic_evidence
               (heuristic_id, video_id, chunk_id, quote_text, evidence_strength)
               VALUES (1, 'v1', 1, 'Powell hints at rate cuts.', 0.9)''')
        conn.execute(
            '''INSERT INTO speaker_profiles (speaker_name, speaker_type, description)
               VALUES ('Jerome Powell', 'central_banker', 'Fed chair')''')
        conn.execute(
            '''INSERT INTO decision_cases
               (video_id, chunk_id, market_context, setup, decision, reasoning)
               VALUES ('v1', 1, 'fed market', 'pre-presser', 'wait',
                       'liquidity usually thin before presser')''')
        conn.execute('INSERT INTO case_principles VALUES (1, 1)')
    return db


def test_pmt_import_small_fixture(tmp_db, tmp_path):
    """End-to-end: import a hand-crafted PMT DB and check counts."""
    from library._core.kb.import_pmt import import_pmt

    src = _make_pmt_fixture(tmp_path)
    report = import_pmt(src)

    assert report['status'] == 'ok'
    assert report['documents']['total'] == 1
    assert report['chunks']['total'] == 1
    assert report['heuristics']['total'] == 1
    assert report['decision_cases']['total'] == 1

    with sqlite3.connect(tmp_db) as conn:
        doc = conn.execute(
            "SELECT id, external_id, title FROM transcript_documents"
        ).fetchone()
        assert doc[1] == 'v1'
        assert doc[2] == 'Test Vid'

        chunk = conn.execute(
            'SELECT document_id, char_start, char_end, token_count, text_sha1 '
            'FROM transcript_chunks'
        ).fetchone()
        assert chunk[0] == doc[0]
        assert chunk[3] == 6
        assert chunk[4] is not None  # sha1 populated

        # Case-principle join remapped correctly
        row = conn.execute(
            '''SELECT dc.setup, h.heuristic_text
               FROM case_principles cp
               JOIN decision_cases dc ON dc.id = cp.case_id
               JOIN heuristics h ON h.id = cp.heuristic_id'''
        ).fetchone()
        assert row == ('pre-presser',
                       'Listen to what the chair says, not what the market does.')


def test_pmt_import_idempotent(tmp_db, tmp_path):
    from library._core.kb.import_pmt import import_pmt
    src = _make_pmt_fixture(tmp_path)
    import_pmt(src)
    import_pmt(src)  # second run must not duplicate

    with sqlite3.connect(tmp_db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM transcript_documents').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM transcript_chunks').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM heuristics').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM decision_cases').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM case_principles').fetchone()[0] == 1


# ── Query layer ────────────────────────────────────────────────────────────

@pytest.fixture
def seeded_db(tmp_db, tmp_path):
    from library._core.kb.import_pmt import import_pmt
    src = _make_pmt_fixture(tmp_path)
    import_pmt(src)
    return tmp_db


def test_query_heuristics_finds_by_substring(seeded_db):
    from library._core.kb.query import query_heuristics
    hits = query_heuristics('chair')
    assert hits and 'chair' in hits[0]['heuristic_text'].lower()


def test_query_decision_cases_finds_setup(seeded_db):
    from library._core.kb.query import query_decision_cases
    hits = query_decision_cases('presser')
    assert hits and 'presser' in hits[0]['setup']


def test_query_speaker_profile_by_canonical(seeded_db):
    from library._core.kb.query import query_speaker_profile
    p = query_speaker_profile('Jerome Powell')
    assert p is not None
    assert p['canonical_name'] == 'Jerome Powell'


def test_query_case_context_joins(seeded_db):
    from library._core.kb.query import query_case_context
    ctx = query_case_context(1)
    assert ctx['setup'] == 'pre-presser'
    assert ctx['heuristics'] and 'chair' in ctx['heuristics'][0]['heuristic_text'].lower()


def test_query_heuristic_evidence(seeded_db):
    from library._core.kb.query import query_heuristic_evidence
    ev = query_heuristic_evidence(1)
    assert ev and ev[0]['quote_text'].startswith('Powell hints')


def test_unified_query_returns_all_slices(seeded_db):
    from library._core.kb.query import query
    bundle = query('powell')
    assert 'heuristics' in bundle
    assert 'decision_cases' in bundle
    assert 'speaker_profile' in bundle
    assert 'pricing_signals' in bundle
    assert 'transcripts' in bundle
