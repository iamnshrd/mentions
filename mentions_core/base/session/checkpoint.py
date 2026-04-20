"""Session checkpoint logging — append analysis events to JSONL log."""
from __future__ import annotations

from mentions_core.base.config import get_default_store
from mentions_core.base.state_store import StateStore, KEY_CHECKPOINTS
from mentions_core.base.utils import now_iso


def log(payload: dict, user_id: str = 'default',
        store: StateStore | None = None) -> dict:
    """Append a checkpoint entry to the JSONL log.

    Returns a copy of the payload dict with an injected timestamp.
    """
    store = store or get_default_store()
    entry = {**payload, 'timestamp': now_iso()}
    store.append_jsonl(user_id, KEY_CHECKPOINTS, entry)
    return entry
