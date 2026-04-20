"""Legacy compatibility package.

The canonical runtime now lives under ``mentions_core/`` and ``agents/mentions/``.
``library/`` is retained as a shim layer for older imports and CLI usage.

Do not add new runtime logic here. Prefer importing from the canonical active
modules directly.
"""

__all__: list[str] = []
