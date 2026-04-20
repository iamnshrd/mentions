from __future__ import annotations

import re

from mentions_domain.retrieval.embed import cosine
from mentions_domain.retrieval.models import RetrievalHit

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]{3,}")


def _word_set(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def rrf_fuse(lexical: list[int], semantic: list[int] | None, *, k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for i, cid in enumerate(lexical):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
    if semantic:
        for i, cid in enumerate(semantic):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
    return scores


def mmr_rerank(
    candidates: list[RetrievalHit],
    *,
    mmr_lambda: float,
    query_vec: list[float] | None,
    doc_vecs: dict[int, list[float]] | None,
    limit: int,
) -> list[RetrievalHit]:
    if not candidates:
        return []

    have_vectors = query_vec is not None and doc_vecs is not None
    relevance = {
        h.chunk_id: h.score_final if h.score_final > 0 else 1.0 / (1 + h.rank_bm25)
        for h in candidates
    }
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
