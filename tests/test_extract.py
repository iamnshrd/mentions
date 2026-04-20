"""Tests for library._core.extract.pipeline.

Covers:
  * extract_from_chunk: empty input, NullClient short-circuit, exception
    path, shape coercion.
  * run_extraction:
      - NullClient → skipped_no_llm
      - End-to-end seeded document: heuristics, cases, signals, evidence
        inserted with correct provenance.
      - Idempotency: re-run bumps recurring_count, never duplicates rows.
      - Pricing signal UNIQUE-name dedup keeps single row, raises conf.
      - all=True iterates every document.
      - Normalizers behave.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from library._core.extract import extract_from_chunk, run_extraction
from library._core.extract.pipeline import (
    _clip,
    _norm_heuristic_text,
    _norm_signal_name,
)
from library._core.llm import LLMResponse, NullClient
from library.db import connect


# ── FakeClient ─────────────────────────────────────────────────────────────

class FakeClient:
    """Returns either a fixed payload for every call, or a sequence of
    payloads consumed in order. ``BaseException`` payloads raise."""

    def __init__(self, payload=None, *, sequence=None):
        self.payload = payload
        self.sequence = list(sequence) if sequence else None
        self.calls: list[dict] = []

    def _next(self):
        if self.sequence is not None:
            return self.sequence.pop(0) if self.sequence else None
        return self.payload

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        p = self._next()
        if isinstance(p, BaseException):
            raise p
        return LLMResponse(text=json.dumps(p) if p else '')

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        p = self._next()
        if isinstance(p, BaseException):
            raise p
        return p


# ── Seed helpers ───────────────────────────────────────────────────────────

_seed_counter = {'n': 0}


def _seed_doc(conn: sqlite3.Connection, *, speaker='Bob',
              event='Podcast 2024', event_date='2024-05-01',
              chunk_texts=None) -> tuple[int, list[int]]:
    chunk_texts = chunk_texts or [
        'When liquidity is thin on Kalshi, scale in rather than taking full '
        'size. The spread tells you the crowd is uncertain.',
    ]
    _seed_counter['n'] += 1
    src = f'mem://seed-{_seed_counter["n"]}.txt'
    cur = conn.execute(
        'INSERT INTO transcript_documents '
        '(speaker, event, event_date, source_file, status, language) '
        "VALUES (?, ?, ?, ?, 'indexed', 'en')",
        (speaker, event, event_date, src),
    )
    doc_id = cur.lastrowid
    chunk_ids = []
    for i, text in enumerate(chunk_texts):
        c = conn.execute(
            'INSERT INTO transcript_chunks '
            '(document_id, chunk_index, text, speaker, token_count, '
            ' text_sha1) VALUES (?, ?, ?, ?, ?, ?)',
            (doc_id, i, text, speaker, len(text.split()),
             f'sha{doc_id}_{i}'),
        )
        chunk_ids.append(c.lastrowid)
    conn.commit()
    return doc_id, chunk_ids


_RICH_PAYLOAD = {
    'heuristics': [
        {
            'text': 'When liquidity is thin, scale in rather than taking full size.',
            'type': 'sizing',
            'market_type': 'binary',
            'confidence': 0.82,
            'quote': 'scale in rather than taking full size',
            'evidence_strength': 0.9,
        },
    ],
    'decision_cases': [
        {
            'market_context': 'Binary Kalshi market at 80¢',
            'setup': 'Thin book, wide spread',
            'decision': 'Scale in over 3 clips',
            'reasoning': 'Liquidity constraint',
            'risk_note': None,
            'outcome_note': None,
            'tags': 'sizing,liquidity',
        },
    ],
    'pricing_signals': [
        {
            'name': 'wide_spread_thin_book',
            'type': 'structural',
            'description': 'Large spread combined with shallow depth',
            'interpretation': 'Crowd uncertainty; avoid market orders',
            'typical_action': 'Scale in with limits',
            'confidence': 0.75,
        },
    ],
}


# ── extract_from_chunk ─────────────────────────────────────────────────────

class TestExtractFromChunk:
    def test_empty_text_returns_empty(self):
        out = extract_from_chunk({'id': 1, 'document_id': 1, 'text': ''})
        assert out == {'heuristics': [], 'decision_cases': [],
                       'pricing_signals': []}

    def test_null_client_short_circuits(self):
        out = extract_from_chunk(
            {'id': 1, 'document_id': 1, 'text': 'hello world'},
            client=NullClient(),
        )
        assert out == {'heuristics': [], 'decision_cases': [],
                       'pricing_signals': []}

    def test_shape_coerced(self):
        # Non-list values should be replaced with empty lists, not raise.
        fake = FakeClient({
            'heuristics': 'not-a-list',
            'decision_cases': None,
            'pricing_signals': [{'name': 'x', 'description': 'y',
                                 'interpretation': 'z', 'confidence': 0.5,
                                 'type': 'flow'}],
        })
        out = extract_from_chunk(
            {'id': 1, 'document_id': 1, 'text': 'x'}, client=fake,
        )
        assert out['heuristics'] == []
        assert out['decision_cases'] == []
        assert len(out['pricing_signals']) == 1

    def test_exception_returns_empty(self):
        fake = FakeClient(RuntimeError('boom'))
        out = extract_from_chunk(
            {'id': 1, 'document_id': 1, 'text': 'x'}, client=fake,
        )
        assert out == {'heuristics': [], 'decision_cases': [],
                       'pricing_signals': []}

    def test_cache_system_flag_propagates(self):
        fake = FakeClient(_RICH_PAYLOAD)
        extract_from_chunk(
            {'id': 1, 'document_id': 1, 'text': 'x', 'speaker': 'Bob'},
            client=fake,
        )
        assert fake.calls[0]['cache_system'] is True
        assert fake.calls[0]['temperature'] == 0.0
        # Metadata header should appear in the user prompt.
        assert 'speaker: Bob' in fake.calls[0]['user']


# ── Normalizers ────────────────────────────────────────────────────────────

class TestNormalizers:
    def test_norm_heuristic_text(self):
        a = _norm_heuristic_text('When LIQUIDITY is thin, SCALE in!')
        b = _norm_heuristic_text('when liquidity  is thin scale in')
        assert a == b

    def test_norm_signal_name(self):
        assert _norm_signal_name('Wide Spread Thin Book!') == 'wide_spread_thin_book'
        assert _norm_signal_name('__post_event__drift__') == 'post_event_drift'

    def test_clip(self):
        assert _clip('hi') == 'hi'
        assert len(_clip('x' * 500, 240)) == 240
        assert _clip('x' * 500, 240).endswith('…')


# ── run_extraction end-to-end ──────────────────────────────────────────────

class TestRunExtraction:
    def test_null_client_skipped(self, tmp_db):
        r = run_extraction(document_id=1, client=NullClient())
        assert r['status'] == 'skipped_no_llm'
        assert r['documents'] == []

    def test_happy_path_creates_rows(self, tmp_db):
        fake = FakeClient(_RICH_PAYLOAD)
        with connect() as conn:
            doc_id, chunk_ids = _seed_doc(conn)
            r = run_extraction(document_id=doc_id, client=fake, conn=conn)
            conn.commit()

            assert r['status'] == 'ok'
            totals = r['totals']
            assert totals['chunks_processed'] == 1
            assert totals['heuristics_added'] == 1
            assert totals['cases_added'] == 1
            assert totals['signals_added'] == 1
            assert totals['evidence_added'] == 1

            # Heuristic row exists with correct metadata.
            h = conn.execute(
                'SELECT heuristic_text, heuristic_type, market_type, '
                '       recurring_count FROM heuristics',
            ).fetchone()
            assert h is not None
            assert 'scale in' in h[0].lower()
            assert h[1] == 'sizing'
            assert h[2] == 'binary'
            assert h[3] == 1

            # Evidence row linked back to doc + chunk.
            ev = conn.execute(
                'SELECT document_id, chunk_id, quote_text FROM heuristic_evidence',
            ).fetchone()
            assert ev[0] == doc_id
            assert ev[1] == chunk_ids[0]
            assert 'scale in' in ev[2]

            # Pricing signal.
            sig = conn.execute(
                'SELECT signal_name, signal_type, confidence '
                'FROM pricing_signals WHERE signal_name=?',
                ('wide_spread_thin_book',),
            ).fetchone()
            assert sig is not None
            assert sig[1] == 'structural'
            assert sig[2] == pytest.approx(0.75)

            # Decision case.
            dc = conn.execute(
                'SELECT document_id, chunk_id, setup, tags FROM decision_cases',
            ).fetchone()
            assert dc[0] == doc_id
            assert dc[1] == chunk_ids[0]
            assert 'thin book' in dc[2].lower()
            assert dc[3].startswith('sha:')

    def test_idempotent_rerun(self, tmp_db):
        """Running twice: heuristic recurring_count → 2, no new dup rows."""
        fake = FakeClient(_RICH_PAYLOAD)
        with connect() as conn:
            doc_id, _ = _seed_doc(conn)
            run_extraction(document_id=doc_id, client=fake, conn=conn)
            # Second run — FakeClient continues returning the same payload.
            r2 = run_extraction(document_id=doc_id, client=fake, conn=conn)
            conn.commit()

            # Second run bumped, did not insert a new heuristic.
            assert r2['totals']['heuristics_added'] == 0
            assert r2['totals']['heuristics_bumped'] == 1
            assert r2['totals']['cases_added'] == 0
            assert r2['totals']['signals_added'] == 0
            assert r2['totals']['evidence_added'] == 0

            # Exactly one heuristic row, recurring_count == 2.
            rows = conn.execute(
                'SELECT COUNT(*), MAX(recurring_count) FROM heuristics',
            ).fetchone()
            assert rows == (1, 2)

            # Evidence did NOT duplicate (same quote + doc + chunk).
            ec = conn.execute(
                'SELECT COUNT(*) FROM heuristic_evidence',
            ).fetchone()[0]
            assert ec == 1

            # Decision case did NOT duplicate.
            dc_count = conn.execute(
                'SELECT COUNT(*) FROM decision_cases',
            ).fetchone()[0]
            assert dc_count == 1

            # Pricing signal stays unique by name.
            sig_count = conn.execute(
                'SELECT COUNT(*) FROM pricing_signals',
            ).fetchone()[0]
            assert sig_count == 1

    def test_pricing_signal_confidence_raised_on_rerun(self, tmp_db):
        """Re-run with higher confidence should bump, not overwrite down."""
        low = {
            'heuristics': [], 'decision_cases': [],
            'pricing_signals': [{
                'name': 'post_event_drift', 'type': 'behavioral',
                'description': 'x', 'interpretation': 'y',
                'typical_action': None, 'confidence': 0.4,
            }],
        }
        high = {
            'heuristics': [], 'decision_cases': [],
            'pricing_signals': [{
                'name': 'post_event_drift', 'type': 'behavioral',
                'description': 'x', 'interpretation': 'y',
                'typical_action': None, 'confidence': 0.9,
            }],
        }
        with connect() as conn:
            doc_id, _ = _seed_doc(conn)
            run_extraction(document_id=doc_id, client=FakeClient(low), conn=conn)
            run_extraction(document_id=doc_id, client=FakeClient(high), conn=conn)
            conn.commit()
            conf = conn.execute(
                'SELECT confidence FROM pricing_signals WHERE signal_name=?',
                ('post_event_drift',),
            ).fetchone()[0]
            assert conf == pytest.approx(0.9)

    def test_all_iterates_every_document(self, tmp_db):
        fake = FakeClient(_RICH_PAYLOAD)
        with connect() as conn:
            d1, _ = _seed_doc(conn, speaker='Alice')
            d2, _ = _seed_doc(conn, speaker='Bob', event='Podcast 2025')
            r = run_extraction(all=True, client=fake, conn=conn)
            conn.commit()
            assert r['totals']['documents'] == 2
            assert {d['document_id'] for d in r['documents']} == {d1, d2}
            # Same heuristic text → single row across both docs.
            assert conn.execute(
                'SELECT COUNT(*) FROM heuristics',
            ).fetchone()[0] == 1
            # But evidence links both chunks.
            assert conn.execute(
                'SELECT COUNT(*) FROM heuristic_evidence',
            ).fetchone()[0] == 2

    def test_chunk_limit_respected(self, tmp_db):
        fake = FakeClient(_RICH_PAYLOAD)
        with connect() as conn:
            doc_id, _ = _seed_doc(conn, chunk_texts=[
                'chunk one text about liquidity',
                'chunk two text about pricing',
                'chunk three text about sizing',
            ])
            r = run_extraction(document_id=doc_id, client=fake, conn=conn,
                               chunk_limit=2)
            assert r['totals']['chunks_processed'] == 2

    def test_requires_target(self, tmp_db):
        with pytest.raises(ValueError):
            run_extraction(client=FakeClient(_RICH_PAYLOAD))
