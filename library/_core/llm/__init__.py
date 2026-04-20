"""Pluggable LLM client layer.

Default is :class:`library._core.llm.client.NullClient` — no LLM calls,
all callers receive ``None``/fallback responses. Opt-in Anthropic
adapter is :class:`library._core.llm.client.AnthropicClient`; it
enables prompt caching on the static system prompt so repeated
classification or extraction calls are cheap.

The library never imports ``anthropic`` at module load — it's a lazy
import inside the adapter so the dep stays optional.
"""
from __future__ import annotations

from library._core.llm.client import (
    AnthropicClient,
    LLMClient,
    LLMResponse,
    NullClient,
    default_client,
)

__all__ = [
    'AnthropicClient',
    'LLMClient',
    'LLMResponse',
    'NullClient',
    'default_client',
]
