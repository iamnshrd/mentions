"""Shared base-layer paths and default configuration."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
WORKSPACE = PROJECT / 'workspace'

_default_store = None


def get_default_store():
    """Return the default workspace-backed state store."""
    global _default_store
    if _default_store is None:
        from mentions_core.base.adapters.fs_store import FileSystemStore
        _default_store = FileSystemStore(WORKSPACE)
    return _default_store
