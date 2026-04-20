"""Compatibility shim for legacy ``library._core.scheduler.runner`` imports."""

from agents.mentions.scheduler.runner import run_autonomous

__all__ = ['run_autonomous']
