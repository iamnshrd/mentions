"""Canonical retrieval-domain primitives and ranking helpers."""

from .embed import (
    EmbedBackend,
    NullEmbed,
    SentenceTransformerEmbed,
    cosine,
    default_backend,
)
from .models import RetrievalHit
from .ranking import rrf_fuse, mmr_rerank
from .recency import (
    DEFAULT_HALF_LIFE_DAYS,
    RECENCY_FLOOR,
    apply_recency,
    recency_weight,
)
from .reliability import apply_weights, speaker_weight

__all__ = [
    'DEFAULT_HALF_LIFE_DAYS',
    'RECENCY_FLOOR',
    'EmbedBackend',
    'NullEmbed',
    'RetrievalHit',
    'SentenceTransformerEmbed',
    'apply_recency',
    'apply_weights',
    'cosine',
    'default_backend',
    'mmr_rerank',
    'recency_weight',
    'rrf_fuse',
    'speaker_weight',
]
