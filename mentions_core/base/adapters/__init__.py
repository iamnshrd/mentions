"""Canonical adapter exports for base-layer storage."""
from __future__ import annotations

from mentions_core.base.config import get_default_store
from mentions_core.base.adapters.fs_store import FileSystemStore


def get_store():
    """Return the shared default filesystem-backed store."""
    return get_default_store()


__all__ = ['FileSystemStore', 'get_store']
