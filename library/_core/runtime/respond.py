"""Compatibility shim for legacy ``library._core.runtime.respond`` imports."""

from agents.mentions.runtime.respond import respond

__all__ = [
    'respond',
]
