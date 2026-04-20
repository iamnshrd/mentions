"""StateStore protocol and canonical key constants for the OpenClaw base layer.

Modules should import keys from here rather than using raw strings.
``library/state_store.py`` is kept as a legacy compatibility shim that
re-exports everything from this module.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

KEY_SESSION_STATE      = 'session_state'
KEY_USER_STATE         = 'user_state'
KEY_CONTINUITY         = 'continuity'
KEY_CONTINUITY_SUMMARY = 'continuity_summary'
KEY_EFFECTIVENESS      = 'effectiveness_memory'
KEY_CHECKPOINTS        = 'session_checkpoints'
KEY_CONTEXT_GRAPH      = 'context_graph'
KEY_PROGRESS_STATE     = 'progress_state'


@runtime_checkable
class StateStore(Protocol):
    """Abstract persistence backend for per-user session state."""

    def get_json(self, user_id: str, key: str,
                 default: dict | None = None) -> dict:
        """Return the stored dict for *user_id* / *key*, or *default*."""
        ...

    def put_json(self, user_id: str, key: str, value: dict) -> None:
        """Atomically persist *value* for *user_id* / *key*."""
        ...

    def append_jsonl(self, user_id: str, key: str, event: dict) -> None:
        """Append *event* to the JSONL log for *user_id* / *key*."""
        ...

    def read_jsonl(self, user_id: str, key: str) -> list[dict]:
        """Return all events from the JSONL log for *user_id* / *key*."""
        ...
