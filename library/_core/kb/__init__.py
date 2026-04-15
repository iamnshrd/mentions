"""Legacy knowledge-base facade for package-level compatibility imports."""

from library._core.kb.build import build
from library._core.kb.migrate import LATEST_VERSION, get_schema_version, migrate_up
from library._core.kb.query import (
    query,
    query_analysis_cache,
    query_markets,
    query_transcripts,
    save_analysis,
)

__all__ = [
    'LATEST_VERSION',
    'build',
    'get_schema_version',
    'migrate_up',
    'query',
    'query_analysis_cache',
    'query_markets',
    'query_transcripts',
    'save_analysis',
]
