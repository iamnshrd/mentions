"""Extraction pipeline — chunk → LLM → KB upserts with provenance."""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3

from mentions_domain.llm import LLMClient, NullClient, default_client
from mentions_core.base.obs import get_collector, trace_event
from agents.mentions.services.extraction.prompts import EXTRACT_SYSTEM
from agents.mentions.db import connect

log = logging.getLogger('mentions')

_WS = re.compile(r'\s+')
_PUNCT = re.compile(r'[^\w\s]')


def _norm_heuristic_text(text: str) -> str:
    s = text.lower().strip()
    s = _PUNCT.sub(' ', s)
    s = _WS.sub(' ', s).strip()
    return s


def _norm_signal_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8', errors='replace')).hexdigest()


def _clip(s: str, n: int = 240) -> str:
    s = (s or '').strip()
    return s if len(s) <= n else s[:n - 1] + '…'


def _f(v, default: float = 0.5) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


def _s(v) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s.lower() in {'null', 'none'} else s


def extract_from_chunk(
    chunk: dict,
    client: LLMClient | None = None,
) -> dict:
    empty = {'heuristics': [], 'decision_cases': [], 'pricing_signals': []}
    text = (chunk.get('text') or '').strip()
    if not text:
        return empty

    client = client or default_client()
    if isinstance(client, NullClient):
        get_collector().incr('extract.skipped_no_llm')
        return empty

    metrics = get_collector()
    metrics.incr('extract.calls')
    chunk_id = chunk.get('id')
    doc_id = chunk.get('document_id')

    header_bits = []
    for k in ('speaker', 'event', 'event_date'):
        v = _s(chunk.get(k))
        if v:
            header_bits.append(f'{k}: {v}')
    header = '\n'.join(header_bits)
    user = (f'{header}\n\n---\n{text}' if header else text)

    try:
        raw = client.complete_json(
            system=EXTRACT_SYSTEM,
            user=user,
            max_tokens=1500,
            temperature=0.0,
            cache_system=True,
        )
    except Exception as exc:
        log.debug('extract_from_chunk LLM failure: %s', exc)
        return empty

    if not raw or not isinstance(raw, dict):
        return empty
    out = dict(empty)
    for k in empty:
        v = raw.get(k)
        if isinstance(v, list):
            out[k] = v
    trace_event(
        'extract.chunk',
        chunk_id=chunk_id,
        document_id=doc_id,
        heuristics=len(out['heuristics']),
        decision_cases=len(out['decision_cases']),
        pricing_signals=len(out['pricing_signals']),
    )
    return out


def _upsert_heuristic(conn: sqlite3.Connection, item: dict,
                      document_id: int, chunk_id: int) -> tuple[int, bool]:
    text = _s(item.get('text'))
    if not text:
        return (0, False)
    norm = _norm_heuristic_text(text)
    htype = _s(item.get('type')) or 'meta'
    market_type = _s(item.get('market_type')) or None
    conf = _f(item.get('confidence'), 0.5)

    for hid, htext in conn.execute(
        'SELECT id, heuristic_text FROM heuristics',
    ).fetchall():
        if _norm_heuristic_text(htext or '') == norm:
            conn.execute(
                'UPDATE heuristics SET recurring_count = recurring_count + 1, '
                'updated_at = CURRENT_TIMESTAMP WHERE id=?', (hid,),
            )
            return (hid, False)

    cur = conn.execute(
        'INSERT INTO heuristics '
        '(heuristic_text, heuristic_type, market_type, confidence, '
        ' recurring_count, notes) '
        'VALUES (?, ?, ?, ?, 1, ?)',
        (text, htype, market_type, conf,
         f'auto-extracted from document {document_id} chunk {chunk_id}'),
    )
    return (cur.lastrowid, True)


def _insert_evidence(conn: sqlite3.Connection, *, heuristic_id: int,
                     document_id: int, chunk_id: int,
                     quote: str, strength: float,
                     context_note: str = '') -> bool:
    quote = _clip(quote)
    if not quote:
        return False
    existing = conn.execute(
        'SELECT id FROM heuristic_evidence '
        'WHERE heuristic_id=? AND document_id=? AND chunk_id=? '
        '  AND substr(quote_text, 1, 240) = ?',
        (heuristic_id, document_id, chunk_id, quote),
    ).fetchone()
    if existing:
        return False
    conn.execute(
        'INSERT INTO heuristic_evidence '
        '(heuristic_id, document_id, chunk_id, quote_text, '
        ' evidence_strength, context_note) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        (heuristic_id, document_id, chunk_id, quote, _f(strength, 0.5),
         context_note),
    )
    return True


def _upsert_decision_case(conn: sqlite3.Connection, item: dict,
                          document_id: int, chunk_id: int) -> bool:
    setup = _s(item.get('setup'))
    if not setup:
        return False
    setup_sha = _sha1(_norm_heuristic_text(setup))
    existing = conn.execute(
        'SELECT id FROM decision_cases '
        'WHERE document_id=? AND chunk_id=? '
        "  AND substr(tags, 1, 42) = ?",
        (document_id, chunk_id, f'sha:{setup_sha[:38]}'),
    ).fetchone()
    if existing:
        return False
    tags_in = _s(item.get('tags'))
    tags = f'sha:{setup_sha[:38]}' + (f' | {tags_in}' if tags_in else '')
    conn.execute(
        'INSERT INTO decision_cases '
        '(document_id, chunk_id, market_context, setup, decision, '
        ' reasoning, risk_note, outcome_note, tags) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (document_id, chunk_id,
         _s(item.get('market_context')),
         setup,
         _s(item.get('decision')),
         _s(item.get('reasoning')),
         _s(item.get('risk_note')) or None,
         _s(item.get('outcome_note')) or None,
         tags),
    )
    return True


def _upsert_pricing_signal(conn: sqlite3.Connection, item: dict) -> bool:
    name = _norm_signal_name(_s(item.get('name')))
    if not name:
        return False
    existing = conn.execute(
        'SELECT id, confidence FROM pricing_signals WHERE signal_name=?',
        (name,),
    ).fetchone()
    if existing:
        new_conf = max(_f(existing[1] or 0.0), _f(item.get('confidence'), 0.5))
        conn.execute(
            'UPDATE pricing_signals SET confidence=?, '
            'updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (new_conf, existing[0]),
        )
        return False
    conn.execute(
        'INSERT INTO pricing_signals '
        '(signal_name, signal_type, description, interpretation, '
        ' typical_action, confidence) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        (name,
         _s(item.get('type')) or None,
         _s(item.get('description')),
         _s(item.get('interpretation')),
         _s(item.get('typical_action')) or None,
         _f(item.get('confidence'), 0.5)),
    )
    return True


def _fetch_chunks(conn: sqlite3.Connection, document_id: int,
                  limit: int | None) -> list[dict]:
    sql = (
        'SELECT c.id, c.document_id, c.text, d.speaker, d.event, d.event_date '
        'FROM transcript_chunks c '
        'JOIN transcript_documents d ON d.id = c.document_id '
        'WHERE c.document_id = ? ORDER BY c.chunk_index'
    )
    rows = conn.execute(sql, (document_id,)).fetchall()
    chunks = [
        {
            'id': r[0], 'document_id': r[1], 'text': r[2] or '',
            'speaker': r[3] or '', 'event': r[4] or '',
            'event_date': r[5] or '',
        } for r in rows
    ]
    if limit is not None:
        chunks = chunks[:max(0, int(limit))]
    return chunks


def _iter_doc_ids(conn: sqlite3.Connection) -> list[int]:
    return [r[0] for r in conn.execute(
        'SELECT id FROM transcript_documents ORDER BY id',
    ).fetchall()]


def run_extraction(
    *,
    document_id: int | None = None,
    all: bool = False,
    client: LLMClient | None = None,
    conn: sqlite3.Connection | None = None,
    chunk_limit: int | None = None,
) -> dict:
    client = client or default_client()

    if isinstance(client, NullClient):
        return {'status': 'skipped_no_llm', 'documents': [], 'totals': {'documents': 0}}

    if not all and document_id is None:
        raise ValueError('document_id or all=True required')

    if conn is not None:
        return _run_on_conn(conn, client, document_id, all, chunk_limit)
    with connect() as owned:
        return _run_on_conn(owned, client, document_id, all, chunk_limit)


def _run_on_conn(conn: sqlite3.Connection, client: LLMClient,
                 document_id: int | None, all: bool,
                 chunk_limit: int | None) -> dict:
    if all:
        doc_ids = _iter_doc_ids(conn)
    elif document_id is not None:
        doc_ids = [int(document_id)]
    else:
        return {'status': 'error', 'error': 'document_id or all=True required'}

    documents = []
    totals = {
        'documents': 0,
        'chunks_processed': 0,
        'heuristics_added': 0,
        'heuristics_bumped': 0,
        'cases_added': 0,
        'signals_added': 0,
        'evidence_added': 0,
    }

    for doc_id in doc_ids:
        chunks = _fetch_chunks(conn, doc_id, chunk_limit)
        summary = {
            'document_id': doc_id,
            'chunks_processed': 0,
            'heuristics_added': 0,
            'heuristics_bumped': 0,
            'cases_added': 0,
            'signals_added': 0,
            'evidence_added': 0,
        }
        for chunk in chunks:
            payload = extract_from_chunk(chunk, client=client)
            summary['chunks_processed'] += 1

            for item in payload.get('heuristics') or []:
                hid, created = _upsert_heuristic(conn, item, doc_id, chunk['id'])
                if hid:
                    if created:
                        summary['heuristics_added'] += 1
                    else:
                        summary['heuristics_bumped'] += 1
                    if _insert_evidence(
                        conn,
                        heuristic_id=hid,
                        document_id=doc_id,
                        chunk_id=chunk['id'],
                        quote=_s(item.get('quote')),
                        strength=_f(item.get('evidence_strength'), 0.5),
                        context_note='auto-extracted',
                    ):
                        summary['evidence_added'] += 1

            for item in payload.get('decision_cases') or []:
                if _upsert_decision_case(conn, item, doc_id, chunk['id']):
                    summary['cases_added'] += 1

            for item in payload.get('pricing_signals') or []:
                if _upsert_pricing_signal(conn, item):
                    summary['signals_added'] += 1

        documents.append(summary)
        totals['documents'] += 1
        for k in summary:
            if k != 'document_id':
                totals[k] += summary[k]

    return {'status': 'ok', 'documents': documents, 'totals': totals}
