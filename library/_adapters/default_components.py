"""Compatibility shim for legacy ``library._adapters.default_components`` imports."""

from mentions_core.base.config import get_default_store


def get_store():
    """Return the default shared store."""
    return get_default_store()
