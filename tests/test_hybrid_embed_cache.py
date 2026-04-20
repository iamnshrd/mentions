"""Tests that hybrid_retrieve reuses the persistent embedding cache.

The v0.11 behaviour was to call ``backend.encode`` on the full
``[query, *candidate_texts]`` every time, paying linear model cost
per query. v0.12 caches chunk vectors in ``chunk_embeddings`` so a
second query pays only for the query text (plus any never-before-seen
chunks).
"""
from __future__ import annotations

import sqlite3

import pytest

from tests.test_hybrid_retrieve import _seed_corpus


# ── Counting backend ───────────────────────────────────────────────────────

class _CountingEmbed:
    """Deterministic 8-dim encoder that records every input it sees."""

    model_name = 'counting-v1'

    def __init__(self):
        self.calls: list[list[str]] = []

    def encode(self, texts):
        self.calls.append(list(texts))
        out = []
        for t in texts:
            v = [0.0] * 8
            for ch in t.lower():
                if ch.isalpha():
                    v[ord(ch) % 8] += 1
            out.append(v)
        return out


@pytest.fixture
def corpus(tmp_db):
    return _seed_corpus(tmp_db)


# ── Tests ──────────────────────────────────────────────────────────────────

class TestEmbedCacheReuse:
    def test_second_call_encodes_only_query(self, corpus, tmp_db):
        """Cold run encodes query + all candidates; warm run encodes query only."""
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve

        backend = _CountingEmbed()
        hits1 = hybrid_retrieve('kalshi pricing', limit=5,
                                candidate_pool=20, embed_backend=backend)
        assert hits1
        first_input_len = len(backend.calls[0])
        assert first_input_len >= 2  # query + >=1 candidates

        # Second call: all candidate chunks are now cached under this model.
        backend2 = _CountingEmbed()
        hits2 = hybrid_retrieve('kalshi pricing', limit=5,
                                candidate_pool=20, embed_backend=backend2)
        assert hits2
        second_input_len = len(backend2.calls[0])
        # Warm: only the query text needs encoding.
        assert second_input_len == 1

    def test_new_chunks_are_encoded_incrementally(self, corpus, tmp_db):
        """Adding a chunk after the warmup forces only that chunk to re-encode."""
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        from agents.mentions.storage.knowledge.fts_sync import sync_document

        backend = _CountingEmbed()
        hybrid_retrieve('kalshi', limit=10, candidate_pool=20,
                        embed_backend=backend)
        warmup_inputs = len(backend.calls[-1])

        # Insert a fresh chunk that will match 'kalshi' queries.
        with sqlite3.connect(tmp_db) as conn:
            doc_id = corpus['doc_ids'][0]
            conn.execute(
                '''INSERT INTO transcript_chunks
                   (document_id, chunk_index, text, speaker, section,
                    token_count)
                   VALUES (?, ?, ?, ?, '', ?)''',
                (doc_id, 999, 'Kalshi orderbook depth matters a lot here.',
                 'Dan', 15),
            )
            sync_document(conn, doc_id)
            conn.commit()

        backend2 = _CountingEmbed()
        hybrid_retrieve('kalshi', limit=10, candidate_pool=20,
                        embed_backend=backend2)
        # Expect: query + exactly one new chunk (the rest cached).
        incr_inputs = len(backend2.calls[-1])
        assert incr_inputs == 2, \
            f'expected query + 1 new chunk; got {incr_inputs} inputs'
        assert incr_inputs < warmup_inputs

    def test_different_models_do_not_share_cache(self, corpus, tmp_db):
        """Switching model_name forces a fresh encode pass."""
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve

        b1 = _CountingEmbed()
        b1.model_name = 'model-A'
        hybrid_retrieve('kalshi', limit=5, candidate_pool=20,
                        embed_backend=b1)

        b2 = _CountingEmbed()
        b2.model_name = 'model-B'
        hybrid_retrieve('kalshi', limit=5, candidate_pool=20,
                        embed_backend=b2)
        # model-B has empty cache → must re-encode all candidates.
        assert len(b2.calls[0]) > 1
