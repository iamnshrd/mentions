"""Hybrid retrieval over the transcript corpus.

Pipeline:

1. **Lexical candidates** — FTS5 BM25 over ``transcript_chunks_fts``. We
   pull a larger pool (``candidate_pool`` default 40) than we ultimately
   emit so reranking has room to work.
2. **Semantic scoring** (optional) — when an :class:`EmbedBackend` is
   supplied *and* actually returns vectors, we embed the query plus
   every candidate chunk and score by cosine similarity.
3. **Fusion** — Reciprocal Rank Fusion (RRF). Score-free, so it is
   robust against BM25 vs cosine scale mismatch. When semantic scoring
   is unavailable, lexical rank alone drives the final order.
4. **MMR rerank** — Maximal Marginal Relevance for diversity. Uses
   embeddings when present; otherwise falls back to Jaccard overlap on
   word sets (still deterministic, zero deps).
5. **Token budget** — cumulatively sum ``token_count`` from chunks and
   stop at ``token_budget``. This replaces the v0.1 char-based cap and
   gives callers a predictable cost ceiling.

Returned :class:`RetrievalHit` objects carry every intermediate score
so downstream code (tests, telemetry, UI) can inspect what happened.

Structured knowledge attachment (:func:`retrieve_bundle`): after the
chunks are selected, we gather heuristics and decision_cases linked to
their source documents, so the caller gets a joined bundle.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field

from library.db import connect, row_to_dict
from library.utils import fts_query as build_fts, timed

from library._core.retrieve.embed import EmbedBackend, NullEmbed, cosine

log = logging.getLogger('mentions')


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class RetrievalHit:
    """One chunk with its provenance and all intermediate scores."""
    chunk_id:       int
    document_id:    int
    text:           str
    speaker:        str
    section:        str
    event:          str
    event_date:     str
    token_count:    int
    # v0.14.6 (T1): canonical profile name when the surface ``speaker``
    # resolved against ``speaker_profiles``. Empty string otherwise —
    # reliability weighting then falls back to the raw ``speaker`` field.
    speaker_canonical: str = ''
    # Ranks are 1-based; 0 means "not ranked in that stage".
    rank_bm25:      int = 0
    rank_semantic:  int = 0
    # Raw scores (lower-better for BM25, higher-better for cosine).
    score_bm25:     float = 0.0
    score_semantic: float | None = None
    score_final:    float = 0.0
    # Reliability multiplier applied in _rrf_fuse step (v0.14.1). 1.0
    # means the speaker either had no track record or wasn't found.
    score_reliability: float = 1.0
    # Recency multiplier from event_date (v0.14.7 — T4). 1.0 means
    # neutral (no date, future date, or decay disabled).
    score_recency:  float = 1.0
    final_rank:     int = 0

    def as_dict(self) -> dict:
        d = asdict(self)
        return d


# ── BM25 candidate pool ────────────────────────────────────────────────────

def _bm25_candidates(fts: str, *, pool: int, speaker: str = '') -> list[dict]:
    """Return up to *pool* FTS5 BM25-ranked chunk rows.

    FTS5's ``rank`` column is the negative BM25 score; smaller (more
    negative) is better. We carry it through as ``score_bm25`` without
    normalising — RRF handles ordering.
    """
    if not fts:
        return []
    rows: list[dict] = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            if speaker:
                cur.execute(
                    '''SELECT tc.id AS chunk_id, tc.document_id, tc.text,
                              COALESCE(tc.speaker, '')    AS speaker,
                              COALESCE(tc.speaker_canonical, '') AS speaker_canonical,
                              COALESCE(tc.section, '')    AS section,
                              COALESCE(tc.token_count, 0) AS token_count,
                              COALESCE(td.event, '')      AS event,
                              COALESCE(td.event_date, '') AS event_date,
                              fts.rank AS bm25_rank
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks     tc ON tc.id = fts.rowid
                       JOIN transcript_documents  td ON td.id = tc.document_id
                       WHERE transcript_chunks_fts MATCH ?
                         AND tc.speaker LIKE ?
                       ORDER BY fts.rank
                       LIMIT ?''',
                    (fts, f'%{speaker}%', pool),
                )
            else:
                cur.execute(
                    '''SELECT tc.id AS chunk_id, tc.document_id, tc.text,
                              COALESCE(tc.speaker, '')    AS speaker,
                              COALESCE(tc.speaker_canonical, '') AS speaker_canonical,
                              COALESCE(tc.section, '')    AS section,
                              COALESCE(tc.token_count, 0) AS token_count,
                              COALESCE(td.event, '')      AS event,
                              COALESCE(td.event_date, '') AS event_date,
                              fts.rank AS bm25_rank
                       FROM transcript_chunks_fts fts
                       JOIN transcript_chunks     tc ON tc.id = fts.rowid
                       JOIN transcript_documents  td ON td.id = tc.document_id
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


# ── Jaccard fallback for MMR ──────────────────────────────────────────────

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]{3,}")


def _word_set(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ── Fusion ─────────────────────────────────────────────────────────────────

def _rrf_fuse(lexical: list[int], semantic: list[int] | None,
              *, k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion over chunk_id lists.

    Returns ``{chunk_id: fused_score}`` — higher is better.
    Rank positions are 1-based. When ``semantic`` is ``None`` we only
    score the lexical list, preserving its order.
    """
    scores: dict[int, float] = {}
    for i, cid in enumerate(lexical):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
    if semantic:
        for i, cid in enumerate(semantic):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
    return scores


# ── MMR rerank ─────────────────────────────────────────────────────────────

def _mmr_rerank(candidates: list[RetrievalHit],
                *, mmr_lambda: float,
                query_vec: list[float] | None,
                doc_vecs: dict[int, list[float]] | None,
                limit: int) -> list[RetrievalHit]:
    """Maximal Marginal Relevance rerank.

    *mmr_lambda* balances relevance vs novelty:
      - 1.0 → pure relevance (original order)
      - 0.0 → pure diversity (ignore relevance)
      - typical: 0.6–0.8

    Uses cosine similarity between chunk embeddings when available,
    else falls back to Jaccard on word sets. Either way we need a
    relevance score and a similarity function between chunks.
    """
    if not candidates:
        return []

    have_vectors = query_vec is not None and doc_vecs is not None

    # Relevance = score_final (from fusion) if set; else fall back to 1 for all.
    relevance = {
        h.chunk_id: h.score_final if h.score_final > 0 else 1.0 / (1 + h.rank_bm25)
        for h in candidates
    }

    # Pre-compute Jaccard sets for fallback similarity.
    word_sets = {h.chunk_id: _word_set(h.text) for h in candidates}

    def sim(a: RetrievalHit, b: RetrievalHit) -> float:
        if have_vectors:
            va = doc_vecs.get(a.chunk_id)
            vb = doc_vecs.get(b.chunk_id)
            if va and vb:
                return cosine(va, vb)
        return _jaccard(word_sets[a.chunk_id], word_sets[b.chunk_id])

    selected: list[RetrievalHit] = []
    pool = list(candidates)
    while pool and len(selected) < limit:
        best_idx = 0
        best_score = -1e9
        for i, cand in enumerate(pool):
            rel = relevance.get(cand.chunk_id, 0.0)
            max_sim = max((sim(cand, s) for s in selected), default=0.0)
            mmr = mmr_lambda * rel - (1 - mmr_lambda) * max_sim
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        selected.append(pool.pop(best_idx))
    return selected


# ── Public entry point ────────────────────────────────────────────────────

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
    """Hybrid BM25 + (optional) semantic + MMR retrieval with token budget.

    Arguments:
      * ``query``: natural-language search string.
      * ``limit``: max hits returned AFTER MMR and budget enforcement.
      * ``token_budget``: cumulative token cap across returned chunks.
      * ``mmr_lambda``: 0..1, relevance vs diversity tradeoff.
      * ``candidate_pool``: size of the BM25 pool fed into reranking.
      * ``speaker``: optional speaker-name substring filter.
      * ``embed_backend``: if provided and produces vectors, enables
        semantic fusion and embedding-based MMR similarity.
      * ``reliability_weight``: if True (default), multiply fused
        scores by the per-speaker Beta-posterior multiplier from
        :mod:`library._core.retrieve.reliability`. Disable for
        regression tests that need identity-preserving ranking.
      * ``recency_half_life_days``: exponential decay half-life for
        the event-date recency boost (v0.14.7 — T4). Default 365
        days. Pass ``None`` or ``0`` to disable (chunks with old
        event_dates then rank the same as fresh ones).
    """
    from library._core.obs import get_collector, trace_event
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
        trace_event('retrieve.hybrid', candidates=0, returned=0,
                    speaker=speaker or '')
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
            rank_bm25=i + 1,
            score_bm25=float(r.get('bm25_rank') or 0.0),
        ))

    # ── Semantic scoring ───────────────────────────────────────────────────
    # Strategy: look up cached chunk vectors first, only embed the misses
    # plus the query itself. Cache hits are tracked in metrics so operators
    # can spot cold corpora / misconfigured model names.
    query_vec: list[float] | None = None
    doc_vecs:  dict[int, list[float]] | None = None
    semantic_order: list[int] | None = None

    backend = embed_backend if embed_backend is not None else NullEmbed()
    model_name = getattr(backend, 'model_name', '') or backend.__class__.__name__

    cached: dict[int, list[float]] = {}
    if not isinstance(backend, NullEmbed):
        from library._core.retrieve import embed_cache
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
        # Persist the newly computed vectors for the next query.
        if fresh:
            try:
                with connect() as _c:
                    from library._core.retrieve import embed_cache
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
        # Attach semantic rank and raw score back to the hits.
        rank_map = {cid: rank for rank, (cid, _) in enumerate(scored, start=1)}
        score_map = dict(scored)
        for h in hits:
            h.rank_semantic = rank_map.get(h.chunk_id, 0)
            h.score_semantic = score_map.get(h.chunk_id, 0.0)
    elif cached and vecs is None:
        # Backend failed but we have cached vectors — still score against them.
        # Skip: no query_vec means no fusion signal. Fall through to lexical-only.
        pass

    # ── Fusion ─────────────────────────────────────────────────────────────
    lexical_order = [h.chunk_id for h in hits]  # already BM25-sorted
    fused = _rrf_fuse(lexical_order, semantic_order)
    for h in hits:
        h.score_final = fused.get(h.chunk_id, 0.0)

    # ── Reliability reweighting (v0.14.1) ─────────────────────────────────
    # Multiply each fused score by the speaker's Beta-posterior
    # multiplier. Speakers with <min_applications history get 1.0
    # (neutral) so this can only nudge, never dominate ranking on a
    # clean cold-start corpus.
    if reliability_weight:
        try:
            from library._core.retrieve import reliability as _rel
            # v0.14.6 (T1): prefer speaker_canonical over raw speaker
            # when the ingest path resolved a canonical profile. This
            # avoids missing reliability hits for "Chair Powell" vs
            # "Jerome Powell" surface drift.
            lookup_names = [
                h.speaker_canonical or h.speaker for h in hits
            ]
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

    # ── Recency boost (v0.14.7 — T4) ──────────────────────────────────────
    # Exponential decay on ``event_date`` — a one-year-old transcript
    # gets half the weight of today's (default half-life 365 d). Neutral
    # for missing / unparseable / future dates; floored at 0.1 so BM25
    # can still surface a truly seminal old source.
    if recency_half_life_days:
        try:
            from library._core.retrieve import recency as _rec
            _rec.apply_recency(hits,
                               half_life_days=recency_half_life_days)
            metrics.incr('retrieve.recency_applied', n=sum(
                1 for h in hits
                if getattr(h, 'score_recency', 1.0) != 1.0
            ))
        except Exception as exc:
            log.debug('recency weighting skipped: %s', exc)

    hits.sort(key=lambda h: h.score_final, reverse=True)

    # ── MMR rerank ─────────────────────────────────────────────────────────
    reranked = _mmr_rerank(
        hits,
        mmr_lambda=mmr_lambda,
        query_vec=query_vec,
        doc_vecs=doc_vecs,
        limit=min(len(hits), max(limit * 2, candidate_pool // 2)),
    )

    # ── Token budget ───────────────────────────────────────────────────────
    final: list[RetrievalHit] = []
    used_tokens = 0
    for h in reranked:
        if len(final) >= limit:
            break
        # If token_count is missing (legacy rows), approximate from text length.
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


# ── Bundle: chunks + linked structured knowledge ──────────────────────────

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
    """Return chunks + structured knowledge (heuristics, decision cases).

    The structured slice hangs off the SAME document ids that the
    hybrid retrieval returned, so callers get a coherent bundle rather
    than two disconnected result sets.

    Always safe: missing v2 tables silently resolve to empty lists.
    """
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
        'query':          query,
        'chunks':         [h.as_dict() for h in hits],
        'heuristics':     heuristics,
        'decision_cases': decision_cases,
        'token_total':    sum(h.token_count or 0 for h in hits),
        'doc_ids':        doc_ids,
    }


def _heuristics_for_documents(doc_ids: list[int], limit: int) -> list[dict]:
    """Return distinct heuristics whose evidence points at these documents."""
    if not doc_ids:
        return []
    placeholders = ','.join('?' * len(doc_ids))
    results: list[dict] = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f'''SELECT DISTINCT h.id, h.heuristic_text, h.heuristic_type,
                                    h.market_type, h.confidence, h.recurring_count,
                                    h.notes
                    FROM heuristics h
                    JOIN heuristic_evidence he ON he.heuristic_id = h.id
                    WHERE he.document_id IN ({placeholders})
                    ORDER BY h.recurring_count DESC, h.confidence DESC
                    LIMIT ?''',
                (*doc_ids, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('_heuristics_for_documents failed: %s', exc)
    return results


def _cases_for_documents(doc_ids: list[int], limit: int) -> list[dict]:
    """Return decision cases anchored to any of these document ids."""
    if not doc_ids:
        return []
    placeholders = ','.join('?' * len(doc_ids))
    results: list[dict] = []
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f'''SELECT dc.id, dc.document_id, dc.market_context, dc.setup,
                           dc.decision, dc.reasoning, dc.risk_note,
                           dc.outcome_note, dc.tags
                    FROM decision_cases dc
                    WHERE dc.document_id IN ({placeholders})
                    ORDER BY dc.created_at DESC
                    LIMIT ?''',
                (*doc_ids, limit),
            )
            for row in cur.fetchall():
                results.append(row_to_dict(cur, row))
    except Exception as exc:
        log.debug('_cases_for_documents failed: %s', exc)
    return results
