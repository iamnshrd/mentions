"""Retrieval engine — hybrid search over the transcript corpus.

Submodules:

* :mod:`library._core.retrieve.hybrid` — BM25 (FTS5) + optional semantic
  embeddings + MMR diversity rerank + explicit token budget.
* :mod:`library._core.retrieve.embed` — pluggable embedding backends
  (``NullEmbed`` default, ``SentenceTransformerEmbed`` optional).

High-level: call :func:`library._core.retrieve.hybrid.hybrid_retrieve` for
transcript search with ranking, diversity, and budget in one place.
"""
from __future__ import annotations

from library._core.retrieve.hybrid import (
    RetrievalHit,
    hybrid_retrieve,
    retrieve_bundle,
)

__all__ = [
    'RetrievalHit',
    'hybrid_retrieve',
    'retrieve_bundle',
]
