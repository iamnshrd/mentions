"""Query layer — search market data, transcript corpus, and structured KB.

Two levels of abstraction:

1. Low-level per-table queries (query_markets, query_transcripts,
   query_heuristics, query_decision_cases, ...). Use these when the caller
   knows what it wants.
2. High-level ``query()`` aggregator — returns a bundle with markets,
   transcripts, structured knowledge, and cached analysis. This is what the
   CLI and the retrieval layer should prefer.
"""
from __future__ import annotations

import logging

from agents.mentions.db import connect, row_to_dict
from agents.mentions.utils import fts_query as build_fts

log = logging.getLogger('mentions')


def query(search: str, limit: int = 8) -> dict:
    """Unified query: search markets + transcripts + structured knowledge.

    Returns combined results dict. The structured slice (heuristics, cases,
    speaker profiles, pricing signals) only fires when v2 schema is present;
    missing tables silently resolve to empty lists.
    """
    fts = build_fts(search)
    return {
        'query':           search,
        'markets':         query_markets(search, limit=limit),
        'transcripts':     query_transcripts(fts, limit=limit),
        'heuristics':      query_heuristics(search, limit=min(limit, 5)),
        'decision_cases':  query_decision_cases(search, limit=min(limit, 5)),
        'speaker_profile': query_speaker_profile(search),
        'pricing_signals': query_pricing_signals(search, limit=min(limit, 5)),
        'cached_analysis': query_analysis_cache(search, limit=3),
    }


def query_markets(search: str, limit: int = 10,
                  category: str = '') -> list[dict]:
    """Search the markets table by title or ticker."""
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            if category:
                cur.execute(
                    '''SELECT * FROM markets
                       WHERE (title LIKE ? OR ticker LIKE ?) AND category = ?
                       ORDER BY volume DESC LIMIT ?''',
                    (f'%{search}%', f'%{search}%', category, limit),
                )
            else:
                cur.execute(
                    '''SELECT * FROM markets
                       WHERE title LIKE ? OR ticker LIKE ?
                       ORDER BY volume DESC LIMIT ?''',
                    (f'%{search}%', f'%{search}%', limit),
                )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.warning('query_markets failed: %s', exc)
    return results


def query_transcripts(fts: str, limit: int = 5,
                      speaker: str = '') -> list[dict]:
    """FTS search over transcript corpus.

    *fts* should be a pre-built FTS5 query string.
    """
    if not fts:
        return []
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            if speaker:
                cur.execute(
                    '''SELECT tc.id, tc.text, tc.speaker, tc.section,
                              td.event, td.event_date
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks tc ON tc.id = fts.rowid
                       JOIN transcript_documents td ON td.id = tc.document_id
                       WHERE transcript_chunks_fts MATCH ?
                         AND tc.speaker LIKE ?
                       ORDER BY rank
                       LIMIT ?''',
                    (fts, f'%{speaker}%', limit),
                )
            else:
                cur.execute(
                    '''SELECT tc.id, tc.text, tc.speaker, tc.section,
                              td.event, td.event_date
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks tc ON tc.id = fts.rowid
                       JOIN transcript_documents td ON td.id = tc.document_id
                       WHERE transcript_chunks_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?''',
                    (fts, limit),
                )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_transcripts FTS failed: %s', exc)
    return results


def query_analysis_cache(query_text: str, limit: int = 3) -> list[dict]:
    """Return recent cached analyses matching *query_text*."""
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT * FROM analysis_cache
                   WHERE query LIKE ? OR ticker LIKE ?
                   ORDER BY created_at DESC LIMIT ?''',
                (f'%{query_text[:40]}%', f'%{query_text[:20]}%', limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_analysis_cache failed: %s', exc)
    return results


# ── Structured knowledge queries (v2 schema) ───────────────────────────────

def query_heuristics(search: str, limit: int = 5,
                     heuristic_type: str = '',
                     market_type: str = '') -> list[dict]:
    """Return heuristics matching *search* in text/notes/market_type.

    Optional filters: ``heuristic_type`` (e.g. 'entry_pricing', 'execution'),
    ``market_type`` (e.g. 'binary', 'speaker_event').
    """
    if not search and not heuristic_type and not market_type:
        return []
    results = []
    clauses = []
    params: list = []
    if search:
        # Match on natural text AND on snake_case types (e.g. "entry pricing"
        # → "entry_pricing"). Tokenise on whitespace so multi-word queries
        # still hit when at least one token is present.
        norm = search.strip().lower().replace('-', ' ').replace('_', ' ')
        tokens = [t for t in norm.split() if len(t) >= 3] or [norm]
        snake = search.strip().lower().replace(' ', '_').replace('-', '_')

        text_clauses = []
        for tok in tokens:
            like = f'%{tok}%'
            text_clauses.append(
                '(heuristic_text LIKE ? OR notes LIKE ? OR market_type LIKE ?)')
            params.extend([like, like, like])
        text_clauses.append('(heuristic_type LIKE ? OR heuristic_type LIKE ?)')
        params.extend([f'%{snake}%', f'%{search.strip().lower()}%'])
        clauses.append('(' + ' OR '.join(text_clauses) + ')')
    if heuristic_type:
        clauses.append('heuristic_type = ?')
        params.append(heuristic_type)
    if market_type:
        clauses.append('market_type = ?')
        params.append(market_type)
    where = ' AND '.join(clauses) or '1=1'
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f'''SELECT id, heuristic_text, heuristic_type, market_type,
                           confidence, recurring_count, notes
                    FROM heuristics
                    WHERE {where}
                    ORDER BY recurring_count DESC, confidence DESC
                    LIMIT ?''',
                (*params, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_heuristics failed: %s', exc)
    return results


def query_decision_cases(search: str, limit: int = 5) -> list[dict]:
    """Return decision_cases matching *search* in setup/decision/context/tags."""
    if not search:
        return []
    results = []
    s = f'%{search}%'
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT dc.id, dc.document_id, dc.market_context, dc.setup,
                          dc.decision, dc.reasoning, dc.risk_note, dc.outcome_note,
                          dc.tags, td.title AS document_title, td.external_id
                   FROM decision_cases dc
                   LEFT JOIN transcript_documents td ON td.id = dc.document_id
                   WHERE dc.market_context LIKE ? OR dc.setup LIKE ?
                      OR dc.decision LIKE ? OR dc.reasoning LIKE ?
                      OR dc.tags LIKE ?
                   ORDER BY dc.created_at DESC
                   LIMIT ?''',
                (s, s, s, s, s, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_decision_cases failed: %s', exc)
    return results


def query_speaker_profile(search: str) -> dict | None:
    """Return the speaker profile whose canonical_name or alias matches *search*.

    Alias matching is a substring check against the JSON aliases column. Returns
    ``None`` when nothing matches.
    """
    if not search:
        return None
    s_full = f'%{search}%'
    try:
        with connect() as conn:
            cur = conn.cursor()
            # Prefer exact canonical_name match; fall back to substring, then aliases.
            for sql, args in (
                ('SELECT * FROM speaker_profiles WHERE canonical_name = ? LIMIT 1',
                 (search,)),
                ('SELECT * FROM speaker_profiles WHERE canonical_name LIKE ? LIMIT 1',
                 (s_full,)),
                ('SELECT * FROM speaker_profiles WHERE aliases LIKE ? LIMIT 1',
                 (s_full,)),
            ):
                row = cur.execute(sql, args).fetchone()
                if row:
                    return row_to_dict(cur, row)
    except Exception as exc:
        log.debug('query_speaker_profile failed: %s', exc)
    return None


def query_pricing_signals(search: str, limit: int = 5) -> list[dict]:
    """Return pricing_signals matching *search* in name/description/interpretation."""
    if not search:
        return []
    s = f'%{search}%'
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT id, signal_name, signal_type, description,
                          interpretation, typical_action, confidence
                   FROM pricing_signals
                   WHERE signal_name LIKE ? OR description LIKE ?
                      OR interpretation LIKE ? OR signal_type LIKE ?
                   ORDER BY confidence DESC NULLS LAST
                   LIMIT ?''',
                (s, s, s, s, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_pricing_signals failed: %s', exc)
    return results


def query_phase_logic(phase_name: str = '', event_format: str = '',
                      limit: int = 5) -> list[dict]:
    """Return phase_logic rows optionally filtered by phase/event format."""
    results = []
    clauses = []
    params: list = []
    if phase_name:
        clauses.append('p.phase_name LIKE ?')
        params.append(f'%{phase_name}%')
    if event_format:
        clauses.append('ef.format_name LIKE ?')
        params.append(f'%{event_format}%')
    where = ' AND '.join(clauses) or '1=1'
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f'''SELECT p.*, ef.format_name
                    FROM phase_logic p
                    LEFT JOIN event_formats ef ON ef.id = p.event_format_id
                    WHERE {where}
                    LIMIT ?''',
                (*params, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_phase_logic failed: %s', exc)
    return results


def query_case_context(case_id: int) -> dict:
    """Hydrate a decision_case with all linked principles/signals/patterns.

    Returns the case row plus lists of related heuristics, pricing_signals,
    anti_patterns, execution_patterns, crowd_mistakes, live_trading_tells,
    dispute_patterns, speaker_profiles.
    """
    out: dict = {'id': case_id}
    try:
        with connect() as conn:
            cur = conn.cursor()

            row = cur.execute('SELECT * FROM decision_cases WHERE id = ?',
                              (case_id,)).fetchone()
            if not row:
                return out
            out.update(row_to_dict(cur, row))

            def _fetch(sql: str) -> list[dict]:
                cur.execute(sql, (case_id,))
                return [row_to_dict(cur, r) for r in cur.fetchall()]

            out['heuristics'] = _fetch(
                '''SELECT h.* FROM case_principles cp
                   JOIN heuristics h ON h.id = cp.heuristic_id
                   WHERE cp.case_id = ?''')
            out['anti_patterns'] = _fetch(
                '''SELECT a.* FROM case_anti_patterns ca
                   JOIN anti_patterns a ON a.id = ca.anti_pattern_id
                   WHERE ca.case_id = ?''')
            out['crowd_mistakes'] = _fetch(
                '''SELECT m.* FROM case_crowd_mistakes cm
                   JOIN crowd_mistakes m ON m.id = cm.crowd_mistake_id
                   WHERE cm.case_id = ?''')
            out['dispute_patterns'] = _fetch(
                '''SELECT d.* FROM case_dispute_patterns cd
                   JOIN dispute_patterns d ON d.id = cd.dispute_pattern_id
                   WHERE cd.case_id = ?''')
            out['execution_patterns'] = _fetch(
                '''SELECT e.* FROM case_execution_patterns ce
                   JOIN execution_patterns e ON e.id = ce.execution_pattern_id
                   WHERE ce.case_id = ?''')
            out['live_trading_tells'] = _fetch(
                '''SELECT t.* FROM case_live_trading_tells ct
                   JOIN live_trading_tells t ON t.id = ct.live_trading_tell_id
                   WHERE ct.case_id = ?''')
            out['pricing_signals'] = _fetch(
                '''SELECT ps.* FROM case_pricing_signals cp
                   JOIN pricing_signals ps ON ps.id = cp.pricing_signal_id
                   WHERE cp.case_id = ?''')
            out['speaker_profiles'] = _fetch(
                '''SELECT sp.* FROM case_speaker_profiles csp
                   JOIN speaker_profiles sp ON sp.id = csp.speaker_profile_id
                   WHERE csp.case_id = ?''')
    except Exception as exc:
        log.debug('query_case_context failed: %s', exc)
    return out


def query_heuristic_evidence(heuristic_id: int, limit: int = 5) -> list[dict]:
    """Return quote evidence for a heuristic, joined with source document title."""
    results = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''SELECT he.id, he.quote_text, he.evidence_strength,
                          he.context_note, he.chunk_id,
                          td.title AS document_title, td.external_id
                   FROM heuristic_evidence he
                   LEFT JOIN transcript_documents td ON td.id = he.document_id
                   WHERE he.heuristic_id = ?
                   ORDER BY he.evidence_strength DESC NULLS LAST
                   LIMIT ?''',
                (heuristic_id, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('query_heuristic_evidence failed: %s', exc)
    return results


def save_analysis(query_text: str, ticker: str, frame: dict,
                  synthesis: dict) -> None:
    """Persist an analysis result to the cache."""
    import json
    from agents.mentions.utils import now_iso
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                '''INSERT INTO analysis_cache
                   (query, ticker, frame, reasoning, conclusion, confidence,
                    sources, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    query_text[:500],
                    ticker,
                    json.dumps(frame, ensure_ascii=False),
                    json.dumps(synthesis.get('reasoning_chain', []),
                               ensure_ascii=False),
                    synthesis.get('conclusion', ''),
                    synthesis.get('confidence', ''),
                    json.dumps([], ensure_ascii=False),
                    now_iso(),
                ),
            )
    except Exception as exc:
        log.debug('save_analysis failed: %s', exc)
