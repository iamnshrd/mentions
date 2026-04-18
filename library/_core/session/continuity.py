"""Compatibility shim for legacy ``library._core.session.continuity`` imports."""

from mentions_core.base.session.continuity import load, read, save, summarize, update

__all__ = ['load', 'read', 'save', 'summarize', 'update']
