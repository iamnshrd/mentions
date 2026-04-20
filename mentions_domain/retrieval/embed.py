"""Embedding backends for retrieval-domain semantic ranking."""
from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger('mentions')


class EmbedBackend(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]] | None: ...


class NullEmbed:
    def encode(self, texts: list[str]) -> None:
        return None


class SentenceTransformerEmbed:
    _model = None
    _model_name = ''

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model_name = model_name

    def _get_model(self):
        if (
            SentenceTransformerEmbed._model is None
            or SentenceTransformerEmbed._model_name != self.model_name
        ):
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                log.warning(
                    'sentence-transformers not installed; install it to enable semantic retrieval',
                )
                return None
            SentenceTransformerEmbed._model = SentenceTransformer(self.model_name)
            SentenceTransformerEmbed._model_name = self.model_name
        return SentenceTransformerEmbed._model

    def encode(self, texts: list[str]) -> list[list[float]] | None:
        if not texts:
            return []
        model = self._get_model()
        if model is None:
            return None
        try:
            arr = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return [list(map(float, v)) for v in arr]
        except Exception as exc:
            log.warning('SentenceTransformer encode failed: %s', exc)
            return None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def default_backend() -> EmbedBackend:
    try:
        import sentence_transformers  # noqa: F401
        return SentenceTransformerEmbed()
    except ImportError:
        return NullEmbed()
