"""Compatibility shim for legacy ``library._core.runtime.orchestrator`` imports."""

from agents.mentions.runtime.orchestrator import (
    detect_mode,
    orchestrate,
    orchestrate_for_llm,
    orchestrate_url,
    should_use_kb,
)

__all__ = [
    'detect_mode',
    'orchestrate',
    'orchestrate_for_llm',
    'orchestrate_url',
    'should_use_kb',
]
