"""Pack registry and lazy loader support."""
from __future__ import annotations

from typing import Callable

from mentions_core.base.pack_types import AgentPack

_PACK_LOADERS: dict[str, Callable[[], AgentPack]] = {}
_PACK_CACHE: dict[str, AgentPack] = {}
_BUILTINS_REGISTERED = False


def register_pack_loader(pack_id: str, loader: Callable[[], AgentPack]) -> None:
    """Register a lazy loader for *pack_id*."""
    _PACK_LOADERS[pack_id] = loader


def ensure_builtin_packs_registered() -> None:
    """Register built-in packs once."""
    global _BUILTINS_REGISTERED
    if _BUILTINS_REGISTERED:
        return

    register_pack_loader('mentions', _load_mentions_pack)
    _BUILTINS_REGISTERED = True


def _load_mentions_pack():
    from agents.mentions.pack import MentionsPack

    return MentionsPack()


def get_pack(pack_id: str) -> AgentPack:
    """Load and cache the pack identified by *pack_id*."""
    ensure_builtin_packs_registered()
    if pack_id in _PACK_CACHE:
        return _PACK_CACHE[pack_id]
    loader = _PACK_LOADERS.get(pack_id)
    if loader is None:
        raise KeyError(f'Unknown pack: {pack_id}')
    pack = loader()
    _PACK_CACHE[pack_id] = pack
    return pack


def list_packs() -> list[str]:
    """Return all registered pack ids."""
    ensure_builtin_packs_registered()
    return sorted(_PACK_LOADERS.keys())
