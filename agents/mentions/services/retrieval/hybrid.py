"""Hybrid retrieval over the transcript corpus."""
from __future__ import annotations

import logging

from agents.mentions.db import connect, row_to_dict
from agents.mentions.utils import fts_query as build_fts, timed

from mentions_core.base.obs import get_collector, trace_event
from mentions_domain.retrieval import (
    EmbedBackend,
    NullEmbed,
    RetrievalHit,
    cosine,
    mmr_rerank,
    rrf_fuse,
)

log = logging.getLogger('mentions')


def _bm25_candidates(fts: str, *, pool: int, speaker: str = '') -> list[dict]:
    if not fts:
        return []
    rows: list[dict] = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            if speaker:
                cur.execute(
                    '''SELECT tc.id AS chunk_id, tc.document_id, tc.text,
                              COALESCE(tc.chunk_index, 0) AS chunk_index,
                              COALESCE(tc.speaker, '') AS speaker,
                              COALESCE(tc.speaker_canonical, '') AS speaker_canonical,
                              COALESCE(tc.section, '') AS section,
                              tc.char_start AS char_start,
                              tc.char_end AS char_end,
                              COALESCE(tc.token_count, 0) AS token_count,
                              COALESCE(td.event, '') AS event,
                              COALESCE(td.event_date, '') AS event_date,
                              COALESCE(td.source_file, '') AS source_file,
                              COALESCE(td.source_url, '') AS source_url,
                              fts.rank AS bm25_rank
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks tc ON tc.id = fts.rowid
                       JOIN transcript_documents td ON td.id = tc.document_id
                       WHERE transcript_chunks_fts MATCH ?
                         AND tc.speaker LIKE ?
                       ORDER BY fts.rank
                       LIMIT ?''',
                    (fts, f'%{speaker}%', pool),
                )
            else:
                cur.execute(
                    '''SELECT tc.id AS chunk_id, tc.document_id, tc.text,
                              COALESCE(tc.chunk_index, 0) AS chunk_index,
                              COALESCE(tc.speaker, '') AS speaker,
                              COALESCE(tc.speaker_canonical, '') AS speaker_canonical,
                              COALESCE(tc.section, '') AS section,
                              tc.char_start AS char_start,
                              tc.char_end AS char_end,
                              COALESCE(tc.token_count, 0) AS token_count,
                              COALESCE(td.event, '') AS event,
                              COALESCE(td.event_date, '') AS event_date,
                              COALESCE(td.source_file, '') AS source_file,
                              COALESCE(td.source_url, '') AS source_url,
                              fts.rank AS bm25_rank
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks tc ON tc.id = fts.rowid
                       JOIN transcript_documents td ON td.id = tc.document_id
                       WHERE transcript_chunks_fts MATCH ?
                       ORDER BY fts.rank
                       LIMIT ?''',
                    (fts, pool),
                )
            for row in cur.fetchall():
                rows.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('_bm25_candidates failed: %s', exc)
    return rows


@timed('hybrid_retrieve')
def hybrid_retrieve(
    query: str,
    *,
    limit: int = 10,
    token_budget: int = 2000,
    mmr_lambda: float = 0.7,
    candidate_pool: int = 40,
    speaker: str = '',
    embed_backend: EmbedBackend | None = None,
    reliability_weight: bool = True,
    recency_half_life_days: float | None = 365.0,
) -> list[RetrievalHit]:
    metrics = get_collector()

    if not query or not query.strip():
        return []

    fts = build_fts(query)
    if not fts:
        return []

    metrics.incr('retrieve.calls')
    with metrics.timed('retrieve.bm25_ms'):
        rows = _bm25_candidates(fts, pool=candidate_pool, speaker=speaker)
    metrics.observe('retrieve.candidates', len(rows))
    if not rows:
        metrics.incr('retrieve.empty')
        trace_event('retrieve.hybrid', candidates=0, returned=0, speaker=speaker or '')
        return []

    hits: list[RetrievalHit] = []
    for i, r in enumerate(rows):
        hits.append(RetrievalHit(
            chunk_id=r['chunk_id'],
            document_id=r['document_id'],
            text=r['text'] or '',
            speaker=r.get('speaker') or '',
            speaker_canonical=r.get('speaker_canonical') or '',
            section=r.get('section') or '',
            event=r.get('event') or '',
            event_date=r.get('event_date') or '',
            token_count=r.get('token_count') or 0,
            chunk_index=r.get('chunk_index') or 0,
            source_file=r.get('source_file') or '',
            source_url=r.get('source_url') or '',
            char_start=r.get('char_start'),
            char_end=r.get('char_end'),
            rank_bm25=i + 1,
            score_bm25=float(r.get('bm25_rank') or 0.0),
        ))

    query_vec: list[float] | None = None
    doc_vecs: dict[int, list[float]] | None = None
    semantic_order: list[int] | None = None

    backend = embed_backend if embed_backend is not None else NullEmbed()
    model_name = getattr(backend, 'model_name', '') or backend.__class__.__name__

    cached: dict[int, list[float]] = {}
    if not isinstance(backend, NullEmbed):
        from agents.mentions.storage.retrieval import embed_cache
        try:
            with connect() as _c:
                cached = embed_cache.get_many(
                    _c, [h.chunk_id for h in hits], model_name)
        except Exception as exc:
            log.debug('embed_cache.get_many skipped: %s', exc)
            cached = {}
        metrics.incr('retrieve.embed_cache_hit', n=len(cached))
        metrics.incr('retrieve.embed_cache_miss', n=len(hits) - len(cached))

    missing_hits = [h for h in hits if h.chunk_id not in cached]
    to_encode = [query] + [h.text for h in missing_hits]
    try:
        vecs = backend.encode(to_encode)
    except Exception as exc:
        log.debug('embed_backend.encode failed: %s', exc)
        vecs = None

    if vecs is not None and len(vecs) == len(missing_hits) + 1:
        query_vec = vecs[0]
        fresh = {h.chunk_id: vecs[i + 1] for i, h in enumerate(missing_hits)}
        doc_vecs = {**cached, **fresh}
        if fresh:
            try:
                with connect() as _c:
                    from agents.mentions.storage.retrieval import embed_cache
                    embed_cache.put_many(
                        _c, model_name,
                        [(cid, v) for cid, v in fresh.items()])
            except Exception as exc:
                log.debug('embed_cache.put_many skipped: %s', exc)
        scored: list[tuple[int, float]] = [
            (h.chunk_id, cosine(query_vec, doc_vecs[h.chunk_id]))
            for h in hits if h.chunk_id in doc_vecs
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        semantic_order = [cid for cid, _ in scored]
        rank_map = {cid: rank for rank, (cid, _) in enumerate(scored, start=1)}
        score_map = dict(scored)
        for h in hits:
            h.rank_semantic = rank_map.get(h.chunk_id, 0)
            h.score_semantic = score_map.get(h.chunk_id, 0.0)

    lexical_order = [h.chunk_id for h in hits]
    fused = rrf_fuse(lexical_order, semantic_order)
    for h in hits:
        h.score_final = fused.get(h.chunk_id, 0.0)

    if reliability_weight:
        try:
            from agents.mentions.services.retrieval import reliability as _rel
            lookup_names = [h.speaker_canonical or h.speaker for h in hits]
            with connect() as _c:
                weights = _rel.speaker_weights(_c, lookup_names)
            if weights:
                _rel.apply_weights(hits, weights)
                metrics.incr('retrieve.reliability_applied', n=sum(
                    1 for h in hits
                    if getattr(h, 'score_reliability', 1.0) != 1.0
                ))
        except Exception as exc:
            log.debug('reliability weighting skipped: %s', exc)

    if recency_half_life_days:
        try:
            from mentions_domain.retrieval import recency as _rec
            _rec.apply_recency(hits, half_life_days=recency_half_life_days)
            metrics.incr('retrieve.recency_applied', n=sum(
                1 for h in hits
                if getattr(h, 'score_recency', 1.0) != 1.0
            ))
        except Exception as exc:
            log.debug('recency weighting skipped: %s', exc)

    hits.sort(key=lambda h: h.score_final, reverse=True)
    reranked = mmr_rerank(
        hits,
        mmr_lambda=mmr_lambda,
        query_vec=query_vec,
        doc_vecs=doc_vecs,
        limit=min(len(hits), max(limit * 2, candidate_pool // 2)),
    )

    final: list[RetrievalHit] = []
    used_tokens = 0
    for h in reranked:
        if len(final) >= limit:
            break
        tok = h.token_count or max(1, len(h.text) // 4)
        if used_tokens + tok > token_budget and final:
            break
        h.final_rank = len(final) + 1
        final.append(h)
        used_tokens += tok
    metrics.observe('retrieve.returned', len(final))
    metrics.observe('retrieve.tokens_used', used_tokens)
    trace_event('retrieve.hybrid',
                candidates=len(rows), returned=len(final),
                tokens_used=used_tokens, semantic=semantic_order is not None,
                speaker=speaker or '')
    return final


@timed('retrieve_bundle')
def retrieve_bundle(
    query: str,
    *,
    limit: int = 8,
    token_budget: int = 2000,
    speaker: str = '',
    embed_backend: EmbedBackend | None = None,
    include_structured: bool = True,
) -> dict:
    hits = hybrid_retrieve(
        query,
        limit=limit,
        token_budget=token_budget,
        speaker=speaker,
        embed_backend=embed_backend,
    )

    doc_ids = sorted({h.document_id for h in hits if h.document_id})
    heuristics: list[dict] = []
    decision_cases: list[dict] = []

    if include_structured and doc_ids:
        heuristics = _heuristics_for_documents(doc_ids, limit=limit)
        decision_cases = _cases_for_documents(doc_ids, limit=limit)

    return {
        'query': query,
        'chunks': [h.as_dict() for h in hits],
        'heuristics': heuristics,
        'decision_cases': decision_cases,
        'token_total': sum(h.token_count or 0 for h in hits),
        'doc_ids': doc_ids,
    }


def _heuristics_for_documents(doc_ids: list[int], *, limit: int) -> list[dict]:
    return _fetch_for_documents(
        table='heuristics',
        join_table='heuristic_evidence',
        fk='heuristic_id',
        doc_ids=doc_ids,
        limit=limit,
    )


def _cases_for_documents(doc_ids: list[int], *, limit: int) -> list[dict]:
    return _fetch_for_documents(
        table='decision_cases',
        join_table='case_principles',
        fk='case_id',
        doc_ids=doc_ids,
        limit=limit,
    )


def _fetch_for_documents(
    *,
    table: str,
    join_table: str,
    fk: str,
    doc_ids: list[int],
    limit: int,
) -> list[dict]:
    if not doc_ids:
        return []
    placeholders = ','.join('?' * len(doc_ids))
    results: list[dict] = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f'''SELECT DISTINCT t.*
                      FROM {table} t
                      JOIN {join_table} j ON j.{fk} = t.id
                     WHERE j.document_id IN ({placeholders})
                     ORDER BY t.id DESC
                     LIMIT ?''',
                (*doc_ids, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('_fetch_for_documents(%s) unexpected: %s', table, exc)
    return results
