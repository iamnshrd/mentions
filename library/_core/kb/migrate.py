"""Compatibility shim for legacy ``library._core.kb.migrate`` imports."""

from agents.mentions.kb.migrate import LATEST_VERSION, get_schema_version, migrate_up

__all__ = ['LATEST_VERSION', 'get_schema_version', 'migrate_up']
