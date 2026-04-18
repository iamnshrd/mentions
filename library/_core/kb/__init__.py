"""Legacy knowledge-base facade for package-level compatibility imports.

Keep this as a thin re-export surface only. Do not add new KB logic here.
"""

from agents.mentions.kb.build import build
from agents.mentions.kb.migrate import LATEST_VERSION, get_schema_version, migrate_up
from agents.mentions.kb.query import (
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
