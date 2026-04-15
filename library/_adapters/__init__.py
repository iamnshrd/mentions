"""Legacy adapter facade for compatibility imports."""

from library._adapters.default_components import get_store
from library._adapters.fs_store import FileSystemStore

__all__ = ['FileSystemStore', 'get_store']
