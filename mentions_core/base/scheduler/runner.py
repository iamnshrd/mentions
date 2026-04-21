"""Generic scheduler dispatch for runtime packs."""
from __future__ import annotations

from mentions_core.base.registry import get_pack


def run_pack_schedule(pack_id: str, action: str, **kwargs) -> dict:
    """Dispatch a scheduler action to a pack."""
    pack = get_pack(pack_id)
    return pack.schedule(action, **kwargs)
