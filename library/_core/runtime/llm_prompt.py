"""Compatibility shim for legacy ``library._core.runtime.llm_prompt`` imports."""

from agents.mentions.runtime.llm_prompt import build_fallback_prompt, build_prompt

__all__ = [
    'build_fallback_prompt',
    'build_prompt',
]
