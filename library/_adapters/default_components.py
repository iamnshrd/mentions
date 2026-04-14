"""Default component wiring for the Mentions agent.

Provides factory functions for the default store and any pluggable components.
"""
from __future__ import annotations

from library.config import get_default_store


def get_store():
    """Return the default FileSystemStore singleton."""
    return get_default_store()
