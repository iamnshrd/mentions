"""Import structured knowledge from a PMT knowledge database export.

Typical source schema: ``workspace/mentions/pmt_trader_knowledge.db``
Target schema: the canonical Mentions knowledge database (v2+)

Idempotent: re-running the importer will skip already-imported documents
(matched by ``external_id``) and will not duplicate join-table rows.

Usage::

    from agents.mentions.storage.importers.pmt import import_pmt
    report = import_pmt(src_path='workspace/mentions/pmt_trader_knowledge.db')

Report shape::

    {
        'status': 'ok',
        'documents': {'inserted': N, 'skipped': M},
        'chunks': {'inserted': N, 'skipped': M},
        'heuristics': {'inserted': N, 'skipped': M},
        ...
    }
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

from agents.mentions.db import connect
from agents.mentions.utils import now_iso

log = logging.getLogger('mentions')


def import_pmt(src_path: str | Path) -> dict:
    """Copy videos → transcript_documents, chunks, and all structured tables."""
    src_path = Path(src_path)
    if not src_path.exists():
        return {'status': 'error', 'error': f'Source DB not found: {src_path}'}

    src = sqlite3.connect(f'file:{src_path}?mode=ro', uri=True)
    src.row_factory = sqlite3.Row

    try:
        with connect() as dst:
            dst.row_factory = sqlite3.Row

            doc_map    = _import_documents(src, dst)
            chunk_map  = _import_chunks(src, dst, doc_map)

            heur_map   = _import_heuristics(src, dst)
            _import_heuristic_evidence(src, dst, heur_map, doc_map, chunk_map)

            speaker_map = _import_speaker_profiles(src, dst)
            format_map  = _import_event_formats(src, dst)
            arch_map    = _import_market_archetypes(src, dst)
            signal_map  = _import_pricing_signals(src, dst)
            phase_map   = _import_phase_logic(src, dst, format_map)
            crowd_map   = _import_crowd_mistakes(src, dst, doc_map, chunk_map)
            anti_map    = _import_anti_patterns(src, dst, doc_map, chunk_map)
            exec_map    = _import_execution_patterns(src, dst, doc_map, chunk_map)
            disp_map    = _import_dispute_patterns(src, dst, doc_map, chunk_map)
            tell_map    = _import_live_trading_tells(src, dst, doc_map, chunk_map)
            sizing_map  = _import_sizing_lessons(src, dst)
            case_map    = _import_decision_cases(src, dst, doc_map, chunk_map)

            _import_joins(src, dst, case_map, {
                'case_principles':        ('heuristic_id',       heur_map),
                'case_anti_patterns':     ('anti_pattern_id',    anti_map),
                'case_crowd_mistakes':    ('crowd_mistake_id',   crowd_map),
                'case_dispute_patterns':  ('dispute_pattern_id', disp_map),
                'case_execution_patterns':('execution_pattern_id', exec_map),
                'case_live_trading_tells':('live_trading_tell_id', tell_map),
                'case_pricing_signals':   ('pricing_signal_id',  signal_map),
                'case_speaker_profiles':  ('speaker_profile_id', speaker_map),
            })

            _rebuild_fts(dst)

        return {
            'status':           'ok',
            'source':           str(src_path),
            'documents':        _count_map(doc_map),
            'chunks':           _count_map(chunk_map),
            'heuristics':       _count_map(heur_map),
            'speaker_profiles': _count_map(speaker_map),
            'event_formats':    _count_map(format_map),
            'market_archetypes':_count_map(arch_map),
            'pricing_signals':  _count_map(signal_map),
            'phase_logic':      _count_map(phase_map),
            'crowd_mistakes':   _count_map(crowd_map),
            'anti_patterns':    _count_map(anti_map),
            'execution_patterns': _count_map(exec_map),
            'dispute_patterns': _count_map(disp_map),
            'live_trading_tells': _count_map(tell_map),
            'sizing_lessons':   _count_map(sizing_map),
            'decision_cases':   _count_map(case_map),
        }
    finally:
        src.close()


# ── Helpers ────────────────────────────────────────────────────────────────

_IdMap = dict[int | str, int]


def _count_map(m: _IdMap) -> dict:
    return {'total': len(m)}


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8', errors='replace')).hexdigest()


def _exists(dst: sqlite3.Connection, table: str, col: str, value) -> int | None:
    row = dst.execute(f'SELECT id FROM {table} WHERE {col} = ? LIMIT 1', (value,)).fetchone()
    return row[0] if row else None


# ── Documents & chunks ─────────────────────────────────────────────────────

def _import_documents(src: sqlite3.Connection, dst: sqlite3.Connection) -> _IdMap:
    """videos + transcripts → transcript_documents. Keys: video_id -> new doc.id."""
    doc_map: _IdMap = {}
    rows = src.execute('''
        SELECT v.video_id, v.title, v.source_channel, v.source_url, v.channel_url,
               v.local_txt_path, v.text_length, v.created_at,
               t.clean_text, t.language, t.source_type, t.ingested_at
        FROM videos v
        LEFT JOIN transcripts t ON t.video_id = v.video_id
    ''').fetchall()

    inserted = 0
    skipped  = 0
    ts = now_iso()
    for r in rows:
        existing = _exists(dst, 'transcript_documents', 'external_id', r['video_id'])
        if existing:
            doc_map[r['video_id']] = existing
            skipped += 1
            continue

        clean_text = r['clean_text'] or ''
        sha = _sha1(clean_text) if clean_text else None

        cur = dst.execute('''
            INSERT INTO transcript_documents
                (speaker, event, event_date, source_file, status, added_at,
                 external_id, source_type, language, sha256, char_count,
                 summary, title, source_url, channel)
            VALUES
                ('', '', '', ?, 'indexed', ?,
                 ?, ?, ?, ?, ?,
                 ?, ?, ?, ?)
        ''', (
            r['local_txt_path'] or f'pmt:{r["video_id"]}',
            r['ingested_at'] or r['created_at'] or ts,
            r['video_id'],
            r['source_type'] or 'youtube_auto',
            r['language'] or 'en',
            sha,
            r['text_length'],
            _summarize(clean_text),
            r['title'],
            r['source_url'],
            r['source_channel'],
        ))
        doc_map[r['video_id']] = cur.lastrowid
        inserted += 1

    log.info('Documents: inserted=%d skipped=%d', inserted, skipped)
    return doc_map


def _summarize(text: str, max_chars: int = 400) -> str:
    """Cheap non-LLM summary: first N chars of cleaned text."""
    if not text:
        return ''
    snippet = ' '.join(text.split())[:max_chars]
    return snippet


def _import_chunks(src: sqlite3.Connection, dst: sqlite3.Connection,
                   doc_map: _IdMap) -> _IdMap:
    """transcript_chunks → transcript_chunks. Keys: src.chunk.id -> new chunk.id."""
    chunk_map: _IdMap = {}
    rows = src.execute('''
        SELECT id, video_id, chunk_index, text, char_start, char_end,
               token_estimate, created_at
        FROM transcript_chunks
        ORDER BY id
    ''').fetchall()

    inserted = 0
    skipped  = 0
    for r in rows:
        doc_id = doc_map.get(r['video_id'])
        if doc_id is None:
            skipped += 1
            continue

        # Skip if the chunk already exists for this doc+index (idempotency).
        existing = dst.execute(
            'SELECT id FROM transcript_chunks WHERE document_id = ? AND chunk_index = ?',
            (doc_id, r['chunk_index']),
        ).fetchone()
        if existing:
            chunk_map[r['id']] = existing[0]
            skipped += 1
            continue

        cur = dst.execute('''
            INSERT INTO transcript_chunks
                (document_id, chunk_index, text, speaker, section,
                 char_start, char_end, token_count, text_sha1)
            VALUES (?, ?, ?, '', '', ?, ?, ?, ?)
        ''', (
            doc_id,
            r['chunk_index'],
            r['text'],
            r['char_start'],
            r['char_end'],
            r['token_estimate'],
            _sha1(r['text']),
        ))
        chunk_map[r['id']] = cur.lastrowid
        inserted += 1

    log.info('Chunks: inserted=%d skipped=%d', inserted, skipped)
    return chunk_map


# ── Structured knowledge tables ────────────────────────────────────────────

def _import_heuristics(src: sqlite3.Connection, dst: sqlite3.Connection) -> _IdMap:
    """Dedup by (heuristic_text[:200], heuristic_type)."""
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM heuristics').fetchall()
    inserted = 0
    for r in rows:
        key = (r['heuristic_text'][:200], r['heuristic_type'])
        existing = dst.execute(
            'SELECT id FROM heuristics WHERE substr(heuristic_text, 1, 200) = ? AND heuristic_type = ?',
            key,
        ).fetchone()
        if existing:
            id_map[r['id']] = existing[0]
            continue

        cur = dst.execute('''
            INSERT INTO heuristics
                (heuristic_text, heuristic_type, market_type, confidence,
                 recurring_count, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['heuristic_text'], r['heuristic_type'], r['market_type'],
            r['confidence'], r['recurring_count'], r['notes'],
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
        inserted += 1

    log.info('Heuristics: inserted=%d', inserted)
    return id_map


def _import_heuristic_evidence(src, dst, heur_map: _IdMap,
                               doc_map: _IdMap, chunk_map: _IdMap) -> None:
    rows = src.execute('SELECT * FROM heuristic_evidence').fetchall()
    inserted = 0
    for r in rows:
        h_id  = heur_map.get(r['heuristic_id'])
        d_id  = doc_map.get(r['video_id'])
        c_id  = chunk_map.get(r['chunk_id']) if r['chunk_id'] else None
        if h_id is None:
            continue

        # Dedup by (heuristic_id, quote_text[:200])
        existing = dst.execute(
            '''SELECT id FROM heuristic_evidence
               WHERE heuristic_id = ? AND substr(quote_text, 1, 200) = ?''',
            (h_id, (r['quote_text'] or '')[:200]),
        ).fetchone()
        if existing:
            continue

        dst.execute('''
            INSERT INTO heuristic_evidence
                (heuristic_id, document_id, chunk_id, quote_text,
                 evidence_strength, context_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (h_id, d_id, c_id, r['quote_text'], r['evidence_strength'],
              r['context_note'], r['created_at']))
        inserted += 1

    log.info('Heuristic evidence: inserted=%d', inserted)


def _import_speaker_profiles(src, dst) -> _IdMap:
    """PMT.speaker_profiles.speaker_name → new.canonical_name (UNIQUE)."""
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM speaker_profiles').fetchall()
    for r in rows:
        existing = _exists(dst, 'speaker_profiles', 'canonical_name', r['speaker_name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO speaker_profiles
                (canonical_name, speaker_type, aliases, description,
                 behavior_style, favored_topics, avoid_topics, qna_style,
                 adaptation_notes, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['speaker_name'], r['speaker_type'], r['description'],
            r['behavior_style'], r['favored_topics'], r['avoid_topics'],
            r['qna_style'], r['adaptation_notes'],
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Speaker profiles: total=%d', len(id_map))
    return id_map


def _import_event_formats(src, dst) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM event_formats').fetchall()
    for r in rows:
        existing = _exists(dst, 'event_formats', 'format_name', r['format_name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO event_formats
                (format_name, domain, description, has_prepared_remarks,
                 has_qna, qna_probability, usual_market_effects,
                 format_risk_notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['format_name'], r['domain'], r['description'],
            r['has_prepared_remarks'], r['has_qna'], r['qna_probability'],
            r['usual_market_effects'], r['format_risk_notes'],
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Event formats: total=%d', len(id_map))
    return id_map


def _import_market_archetypes(src, dst) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM market_archetypes').fetchall()
    for r in rows:
        existing = _exists(dst, 'market_archetypes', 'name', r['name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO market_archetypes
                (name, archetype_type, description, pricing_drivers,
                 common_edges, common_traps, liquidity_profile, repeatability,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['name'], r['archetype_type'], r['description'],
            r['pricing_drivers'], r['common_edges'], r['common_traps'],
            r['liquidity_profile'], r['repeatability'],
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Market archetypes: total=%d', len(id_map))
    return id_map


def _import_pricing_signals(src, dst) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM pricing_signals').fetchall()
    for r in rows:
        existing = _exists(dst, 'pricing_signals', 'signal_name', r['signal_name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO pricing_signals
                (signal_name, signal_type, description, interpretation,
                 typical_action, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['signal_name'], r['signal_type'], r['description'],
            r['interpretation'], r['typical_action'], r['confidence'],
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Pricing signals: total=%d', len(id_map))
    return id_map


def _import_phase_logic(src, dst, format_map: _IdMap) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM phase_logic').fetchall()
    for r in rows:
        ef_id = format_map.get(r['event_format_id']) if r['event_format_id'] else None
        existing = dst.execute(
            'SELECT id FROM phase_logic WHERE phase_name = ? AND IFNULL(event_format_id, -1) = IFNULL(?, -1)',
            (r['phase_name'], ef_id),
        ).fetchone()
        if existing:
            id_map[r['id']] = existing[0]
            continue
        cur = dst.execute('''
            INSERT INTO phase_logic
                (phase_name, event_format_id, description,
                 what_becomes_more_likely, what_becomes_less_likely,
                 common_pricing_errors, execution_notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['phase_name'], ef_id, r['description'],
            r['what_becomes_more_likely'], r['what_becomes_less_likely'],
            r['common_pricing_errors'], r['execution_notes'],
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Phase logic: total=%d', len(id_map))
    return id_map


def _import_crowd_mistakes(src, dst, doc_map: _IdMap, chunk_map: _IdMap) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM crowd_mistakes').fetchall()
    for r in rows:
        existing = _exists(dst, 'crowd_mistakes', 'mistake_name', r['mistake_name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO crowd_mistakes
                (mistake_name, mistake_type, description, why_it_happens,
                 how_to_exploit, example_document_id, example_chunk_id,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['mistake_name'], r['mistake_type'], r['description'],
            r['why_it_happens'], r['how_to_exploit'],
            doc_map.get(r['example_video_id']),
            chunk_map.get(r['example_chunk_id']) if r['example_chunk_id'] else None,
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Crowd mistakes: total=%d', len(id_map))
    return id_map


def _import_anti_patterns(src, dst, doc_map: _IdMap, chunk_map: _IdMap) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM anti_patterns').fetchall()
    for r in rows:
        existing = dst.execute(
            'SELECT id FROM anti_patterns WHERE substr(pattern_text, 1, 200) = ?',
            (r['pattern_text'][:200],),
        ).fetchone()
        if existing:
            id_map[r['id']] = existing[0]
            continue
        cur = dst.execute('''
            INSERT INTO anti_patterns
                (pattern_text, why_bad, example_document_id, example_chunk_id,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            r['pattern_text'], r['why_bad'],
            doc_map.get(r['example_video_id']),
            chunk_map.get(r['example_chunk_id']) if r['example_chunk_id'] else None,
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Anti patterns: total=%d', len(id_map))
    return id_map


def _import_execution_patterns(src, dst, doc_map: _IdMap, chunk_map: _IdMap) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM execution_patterns').fetchall()
    for r in rows:
        existing = _exists(dst, 'execution_patterns', 'pattern_name', r['pattern_name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO execution_patterns
                (pattern_name, execution_type, description, best_used_when,
                 avoid_when, risk_note, example_document_id, example_chunk_id,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['pattern_name'], r['execution_type'], r['description'],
            r['best_used_when'], r['avoid_when'], r['risk_note'],
            doc_map.get(r['example_video_id']),
            chunk_map.get(r['example_chunk_id']) if r['example_chunk_id'] else None,
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Execution patterns: total=%d', len(id_map))
    return id_map


def _import_dispute_patterns(src, dst, doc_map: _IdMap, chunk_map: _IdMap) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM dispute_patterns').fetchall()
    for r in rows:
        existing = _exists(dst, 'dispute_patterns', 'pattern_name', r['pattern_name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO dispute_patterns
                (pattern_name, dispute_type, description, common_confusion,
                 market_impact, mitigation, example_document_id,
                 example_chunk_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['pattern_name'], r['dispute_type'], r['description'],
            r['common_confusion'], r['market_impact'], r['mitigation'],
            doc_map.get(r['example_video_id']),
            chunk_map.get(r['example_chunk_id']) if r['example_chunk_id'] else None,
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Dispute patterns: total=%d', len(id_map))
    return id_map


def _import_live_trading_tells(src, dst, doc_map: _IdMap, chunk_map: _IdMap) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM live_trading_tells').fetchall()
    for r in rows:
        existing = _exists(dst, 'live_trading_tells', 'tell_name', r['tell_name'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO live_trading_tells
                (tell_name, tell_type, description, interpretation,
                 typical_response, risk_note, example_document_id,
                 example_chunk_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['tell_name'], r['tell_type'], r['description'],
            r['interpretation'], r['typical_response'], r['risk_note'],
            doc_map.get(r['example_video_id']),
            chunk_map.get(r['example_chunk_id']) if r['example_chunk_id'] else None,
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Live trading tells: total=%d', len(id_map))
    return id_map


def _import_sizing_lessons(src, dst) -> _IdMap:
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM sizing_lessons').fetchall()
    for r in rows:
        existing = _exists(dst, 'sizing_lessons', 'lesson_text', r['lesson_text'])
        if existing:
            id_map[r['id']] = existing
            continue
        cur = dst.execute('''
            INSERT INTO sizing_lessons
                (lesson_text, lesson_type, description, applies_to,
                 risk_note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['lesson_text'], r['lesson_type'], r['description'],
            r['applies_to'], r['risk_note'],
            r['created_at'], r['updated_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Sizing lessons: total=%d', len(id_map))
    return id_map


def _import_decision_cases(src, dst, doc_map: _IdMap, chunk_map: _IdMap) -> _IdMap:
    """PMT.decision_cases → new.decision_cases. Dedup by (document_id, setup[:200])."""
    id_map: _IdMap = {}
    rows = src.execute('SELECT * FROM decision_cases').fetchall()
    for r in rows:
        d_id = doc_map.get(r['video_id'])
        if d_id is None:
            continue
        existing = dst.execute(
            '''SELECT id FROM decision_cases
               WHERE document_id = ? AND substr(IFNULL(setup, ''), 1, 200) = ?''',
            (d_id, (r['setup'] or '')[:200]),
        ).fetchone()
        if existing:
            id_map[r['id']] = existing[0]
            continue
        cur = dst.execute('''
            INSERT INTO decision_cases
                (document_id, chunk_id, market_context, setup, decision,
                 reasoning, risk_note, outcome_note, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            d_id,
            chunk_map.get(r['chunk_id']) if r['chunk_id'] else None,
            r['market_context'], r['setup'], r['decision'],
            r['reasoning'], r['risk_note'], r['outcome_note'],
            r['tags'], r['created_at'],
        ))
        id_map[r['id']] = cur.lastrowid
    log.info('Decision cases: total=%d', len(id_map))
    return id_map


def _import_joins(src, dst, case_map: _IdMap, tables: dict) -> None:
    """Import all case_* join tables with INSERT OR IGNORE."""
    for table, (fk_col, target_map) in tables.items():
        rows = src.execute(f'SELECT * FROM {table}').fetchall()
        inserted = 0
        for r in rows:
            new_case = case_map.get(r['case_id'])
            new_fk   = target_map.get(r[fk_col])
            if new_case is None or new_fk is None:
                continue
            dst.execute(
                f'INSERT OR IGNORE INTO {table} (case_id, {fk_col}) VALUES (?, ?)',
                (new_case, new_fk),
            )
            inserted += 1
        log.info('%s: rows=%d', table, inserted)


def _rebuild_fts(dst: sqlite3.Connection) -> None:
    try:
        dst.execute('INSERT INTO transcript_chunks_fts(transcript_chunks_fts) VALUES("rebuild")')
        log.info('FTS rebuilt after PMT import')
    except Exception as exc:
        log.warning('FTS rebuild after import failed: %s', exc)
