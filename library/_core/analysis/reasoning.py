"""Compatibility shim for legacy ``library._core.analysis.reasoning`` imports."""

from agents.mentions.analysis.reasoning import build_reasoning_chain

__all__ = [
    'build_reasoning_chain',
]
