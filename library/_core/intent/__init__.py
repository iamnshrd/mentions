"""Intent classification for incoming queries.

Exposes :func:`classify_intent` which returns a structured intent +
entity dict. Uses an :class:`~library._core.llm.LLMClient` when
available, falls back to deterministic keyword rules otherwise.
"""
from __future__ import annotations

from library._core.intent.classifier import (
    INTENTS,
    IntentResult,
    classify_intent,
)

__all__ = ['INTENTS', 'IntentResult', 'classify_intent']
