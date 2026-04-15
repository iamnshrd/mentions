"""Compatibility shim — re-exports everything from ``library._core.state_store``.

The canonical location of the StateStore protocol and key constants is now
``library/_core/state_store.py`` (matching the Jordan base-layer pattern).
This file is kept so that any external callers using ``library.state_store``
continue to work without changes.
"""
from library._core.state_store import *  # noqa: F401, F403
from library._core.state_store import StateStore  # noqa: F401  (re-export for type checkers)
