"""Compatibility shim for legacy ``library._core.session.checkpoint`` imports."""

from mentions_core.base.session.checkpoint import log

__all__ = ['log']
