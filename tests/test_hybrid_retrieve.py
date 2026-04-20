"""Tests for retrieval hybrid service.

Exercises the full hybrid-retrieval pipeline against a temp DB:

  * BM25 candidate fetch (FTS5 rank)
  * Fusion (Reciprocal Rank Fusion, with and without semantic)
  * MMR rerank (Jaccard fallback and pluggable vector backend)
  * Token budget enforcement
  * Structured knowledge attachment (heuristics + decision_cases)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ── Fixtures ───────────────────────────────────────────────────────────────

SAMPLE_TEXTS = [
    # (speaker, text, event, token_count)
    ('Alice', 'Entry pricing is everything. When Kalshi shows eighty cents we should wait for a pullback before scaling in.', 'Podcast A', 25),
    ('Bob',   'Liquidity is the main constraint on Kalshi markets. If the book is thin you cannot get size without moving the price.', 'Podcast A', 25),
    ('Alice', 'On election night the spread widened to fifteen cents which is enormous. We waited for announcer confirmation before entering.', 'Podcast A', 25),
    ('Bob',   'I always scale in rather than going full size. The rule is simple: never enter more than ten percent at once.', 'Podcast B', 25),
    ('Carol', 'The Fed decision moved the Kalshi market thirty cents in two minutes. That is signal not noise.', 'Podcast C', 20),
    ('Carol', 'Cocoa prices collapsed overnight. Nothing to do with politics, pure weather shock in West Africa.', 'Podcast C', 20),
]


def _seed_corpus(db_path: Path, texts=SAMPLE_TEXTS) -> dict[str, int]:
    """Seed the temp DB with a small transcript corpus and FTS index.

    Returns a dict with ``doc_id`` of the primary document and the list
    of inserted ``chunk_ids``.
    """
    from agents.mentions.storage.knowledge.fts_sync import sync_document
    ids = {'chunk_ids': []}
    with sqlite3.connect(db_path) as conn:
        # Group texts by event into a document per event.
        by_event: dict[str, list] = {}
        for sp, t, ev, tok in texts:
            by_event.setdefault(ev, []).append((sp, t, tok))

        for event, chunks in by_event.items():
            conn.execute(
                '''INSERT INTO transcript_documents
                   (speaker, event, source_file, status, source_type)
                   VALUES (?, ?, ?, 'indexed', 'file')''',
                ('', event, f'/tmp/{event}.txt'),
            )
            doc_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            ids.setdefault('doc_ids', []).append(doc_id)
            for i, (sp, t, tok) in enumerate(chunks):
                conn.execute(
                    '''INSERT INTO transcript_chunks
                       (document_id, chunk_index, text, speaker, section,
                        token_count)
                       VALUES (?, ?, ?, ?, '', ?)''',
                    (doc_id, i, t, sp, tok),
                )
                ids['chunk_ids'].append(conn.execute(
                    'SELECT last_insert_rowid()'
                ).fetchone()[0])
            sync_document(conn, doc_id)
        conn.commit()
    return ids


@pytest.fixture
def corpus(tmp_db):
    """Seed tmp_db with a small corpus and return the seed metadata."""
    return _seed_corpus(tmp_db)


# ── BM25 candidate pool ────────────────────────────────────────────────────

class TestBm25Candidates:
    def test_matches_kalshi_keyword(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import _bm25_candidates
        rows = _bm25_candidates('kalshi', pool=20)
        assert len(rows) >= 3
        # Every returned row should actually contain 'kalshi'.
        for r in rows:
            assert 'kalshi' in r['text'].lower()

    def test_speaker_filter(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import _bm25_candidates
        rows = _bm25_candidates('kalshi', pool=20, speaker='Alice')
        assert all(r['speaker'] == 'Alice' for r in rows)

    def test_returns_empty_on_no_match(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import _bm25_candidates
        rows = _bm25_candidates('zzzunmatched', pool=20)
        assert rows == []


# ── hybrid_retrieve end-to-end ─────────────────────────────────────────────

class TestHybridRetrieve:
    def test_empty_query_returns_empty(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        assert hybrid_retrieve('') == []
        assert hybrid_retrieve('   ') == []

    def test_returns_hits_with_expected_shape(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        from mentions_domain.retrieval import RetrievalHit
        hits = hybrid_retrieve('kalshi pricing', limit=5)
        assert len(hits) >= 1
        for h in hits:
            assert isinstance(h, RetrievalHit)
            assert h.chunk_id > 0
            assert h.document_id > 0
            assert h.text
            assert h.source_file
            assert h.chunk_index >= 0
            assert h.rank_bm25 >= 1
            assert h.final_rank >= 1

    def test_hits_include_traceability_fields(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        hits = hybrid_retrieve('kalshi pricing', limit=3)
        assert hits
        hit = hits[0]
        payload = hit.as_dict()
        assert payload['trace']['chunk_id'] == hit.chunk_id
        assert payload['trace']['document_id'] == hit.document_id
        assert payload['trace']['source_file'].endswith('.txt')
        assert payload['trace']['chunk_index'] == hit.chunk_index

    def test_bm25_rank_monotonic_in_candidate_pool(self, corpus, tmp_db):
        """Within the candidate pool, rank_bm25 ascends 1..N."""
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        hits = hybrid_retrieve('kalshi', limit=20, candidate_pool=10)
        ranks = [h.rank_bm25 for h in hits]
        # With no embeddings, final order follows fusion over lexical only.
        # rank_bm25 values should all be unique and within [1, candidate_pool].
        assert len(set(ranks)) == len(ranks)
        assert all(1 <= r <= 10 for r in ranks)

    def test_limit_is_respected(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        hits = hybrid_retrieve('kalshi', limit=2, candidate_pool=20)
        assert len(hits) <= 2

    def test_token_budget_enforced(self, corpus, tmp_db):
        """Token budget caps cumulative token_count across hits."""
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        # Each seeded chunk has token_count around 20–25. Budget of 40
        # should admit ~2 chunks, not more.
        hits = hybrid_retrieve('kalshi', limit=10, token_budget=40,
                               candidate_pool=20)
        total = sum(h.token_count for h in hits)
        # Allow budget to be exceeded only by the first admitted chunk.
        assert len(hits) <= 3
        if len(hits) > 1:
            # Second chunk would push us over 40 if we had much bigger
            # chunks; guard that we don't keep adding past budget.
            assert total <= 60

    def test_speaker_filter_propagates(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        hits = hybrid_retrieve('kalshi', limit=10, speaker='Bob',
                               candidate_pool=20)
        assert hits, 'should find Bob-attributed chunks'
        assert all(h.speaker == 'Bob' for h in hits)

    def test_no_embed_backend_leaves_semantic_none(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        hits = hybrid_retrieve('kalshi', limit=5)
        # Default NullEmbed → semantic scoring disabled.
        assert all(h.score_semantic is None for h in hits)
        assert all(h.rank_semantic == 0 for h in hits)

    def test_fake_embed_backend_activates_semantic(self, corpus, tmp_db):
        """Plugging in an embedding backend populates semantic scores."""
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve

        class FakeEmbed:
            """Trivial hashing-based encoder for deterministic tests."""

            def encode(self, texts):
                # 8-dim vector of lowercase char-class frequencies.
                vecs = []
                for t in texts:
                    t = t.lower()
                    v = [0.0] * 8
                    for ch in t:
                        if ch.isalpha():
                            v[ord(ch) % 8] += 1
                        elif ch.isdigit():
                            v[0] += 1
                    vecs.append(v)
                return vecs

        hits = hybrid_retrieve('kalshi pricing', limit=5, embed_backend=FakeEmbed())
        assert hits
        # All hits should now carry a semantic score and non-zero rank.
        assert all(h.score_semantic is not None for h in hits)
        assert all(h.rank_semantic >= 1 for h in hits)


# ── MMR rerank behavior ───────────────────────────────────────────────────

class TestMMR:
    def test_mmr_prefers_diverse_hits(self, corpus, tmp_db):
        """Low lambda (=more diversity) should pull in more unique docs."""
        from agents.mentions.services.retrieval.hybrid import hybrid_retrieve
        # Biased query that will match multiple chunks from Podcast A first.
        relevant = hybrid_retrieve('kalshi', limit=3, mmr_lambda=1.0,
                                   candidate_pool=20, token_budget=1000)
        diverse  = hybrid_retrieve('kalshi', limit=3, mmr_lambda=0.1,
                                   candidate_pool=20, token_budget=1000)
        assert len(relevant) == 3
        assert len(diverse)  == 3
        # Unique document count should be >= under the diversity setting.
        assert len({h.document_id for h in diverse}) >= \
               len({h.document_id for h in relevant})


# ── retrieve_bundle: chunks + structured knowledge ────────────────────────

class TestRetrieveBundle:
    def test_bundle_returns_chunks_and_doc_ids(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import retrieve_bundle
        bundle = retrieve_bundle('kalshi', limit=4)
        assert bundle['query'] == 'kalshi'
        assert len(bundle['chunks']) >= 1
        assert bundle['doc_ids']
        assert bundle['token_total'] == sum(
            c['token_count'] for c in bundle['chunks']
        )
        assert bundle['chunks'][0]['trace']['document_id'] == bundle['chunks'][0]['document_id']
        assert bundle['chunks'][0]['trace']['chunk_id'] == bundle['chunks'][0]['chunk_id']

    def test_bundle_includes_heuristics_linked_to_matched_docs(
        self, corpus, tmp_db,
    ):
        from agents.mentions.services.retrieval.hybrid import retrieve_bundle

        # Seed a heuristic + evidence pointing at a specific matched doc.
        matched_doc = corpus['doc_ids'][0]
        with sqlite3.connect(tmp_db) as conn:
            conn.execute(
                '''INSERT INTO heuristics
                   (heuristic_text, heuristic_type, confidence, recurring_count)
                   VALUES (?, ?, ?, ?)''',
                ('Scale in, do not go full size at entry.', 'entry_pricing',
                 0.8, 3),
            )
            hid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            # Attach evidence pointing at the matched document.
            conn.execute(
                '''INSERT INTO heuristic_evidence
                   (heuristic_id, document_id, quote_text, evidence_strength)
                   VALUES (?, ?, ?, ?)''',
                (hid, matched_doc, 'Scale in rather than going full size.', 0.9),
            )
            conn.commit()

        bundle = retrieve_bundle('kalshi', limit=4)
        assert matched_doc in bundle['doc_ids']
        # Heuristic should hit the bundle because its evidence points at a
        # document we retrieved.
        ids = [h['id'] for h in bundle['heuristics']]
        assert hid in ids

    def test_bundle_without_structured_slice(self, corpus, tmp_db):
        from agents.mentions.services.retrieval.hybrid import retrieve_bundle
        bundle = retrieve_bundle('kalshi', include_structured=False)
        assert bundle['heuristics'] == []
        assert bundle['decision_cases'] == []


# ── Embedding backend defaults ────────────────────────────────────────────

class TestEmbedBackends:
    def test_null_embed_returns_none(self):
        from mentions_domain.retrieval.embed import NullEmbed
        assert NullEmbed().encode(['a', 'b']) is None

    def test_cosine_basic_properties(self):
        from mentions_domain.retrieval.embed import cosine
        assert cosine([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
        assert cosine([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
        assert cosine([], [1, 0, 0]) == 0.0
        assert cosine([1, 0], [1, 0, 0]) == 0.0  # mismatched dim → 0

    def test_default_backend_is_nonraising(self):
        from mentions_domain.retrieval.embed import default_backend
        # Whatever is installed, this should not raise — either a real
        # backend or NullEmbed.
        b = default_backend()
        # encode() must at least accept the call.
        out = b.encode(['hello world'])
        # Either None (Null) or a list of vectors (real backend). Never error.
        assert out is None or isinstance(out, list)
