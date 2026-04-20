"""Embedding backends for semantic retrieval.

Two implementations:

* :class:`NullEmbed` — returns ``None`` from :meth:`encode`, signaling
  "no embeddings available". The hybrid retriever falls back to
  lexical-only scoring in that case. This is the zero-dependency default.
* :class:`SentenceTransformerEmbed` — wraps a local
  `sentence-transformers` model when the package is installed. Opt-in
  because the dependency is heavy (~400 MB with models).

A third backend (OpenAI embeddings) can be added the same way when an
API key is wired; keep it out of this phase to avoid network dependency
in the retrieval path.

All backends implement the :class:`EmbedBackend` protocol: one
:meth:`encode` method that takes a list of strings and returns either
``None`` (signals "unavailable") or a 2-D array of shape
``(n, dim)``.
"""
from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger('mentions')


class EmbedBackend(Protocol):
    """Minimal embedding interface used by hybrid retrieval."""

    def encode(self, texts: list[str]) -> list[list[float]] | None:
        """Return per-text dense vectors, or ``None`` if unavailable."""
        ...


# ── Null backend (default) ─────────────────────────────────────────────────

class NullEmbed:
    """No-op backend. Always returns ``None`` — semantic scoring disabled."""

    def encode(self, texts: list[str]) -> None:
        return None


# ── Sentence-Transformers (optional) ───────────────────────────────────────

class SentenceTransformerEmbed:
    """Wrap a `sentence-transformers` model. Lazy-loaded on first call.

    Install separately::

        pip install sentence-transformers

    The default model (`all-MiniLM-L6-v2`) is 22 MB, multilingual enough
    for mixed EN/RU corpora, and fast on CPU.
    """

    _model = None  # class-level singleton per model name
    _model_name = ''

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model_name = model_name

    def _get_model(self):
        if (SentenceTransformerEmbed._model is None
                or SentenceTransformerEmbed._model_name != self.model_name):
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                log.warning(
                    'sentence-transformers not installed; '
                    'install it to enable semantic retrieval',
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
            arr = model.encode(texts, normalize_embeddings=True,
                               show_progress_bar=False)
            return [list(map(float, v)) for v in arr]
        except Exception as exc:
            log.warning('SentenceTransformer encode failed: %s', exc)
            return None


# ── Helpers ────────────────────────────────────────────────────────────────

def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Both vectors assumed non-empty of equal length."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def default_backend() -> EmbedBackend:
    """Pick the best backend available without raising.

    Tries :class:`SentenceTransformerEmbed` lazily; falls back to
    :class:`NullEmbed` if the optional dependency is missing.
    """
    # Probe once, cheaply — don't load the model here.
    try:
        import sentence_transformers  # noqa: F401
        return SentenceTransformerEmbed()
    except ImportError:
        return NullEmbed()
