"""Legacy ingest facade for package-level compatibility imports.

Keep this as a thin re-export surface only. Do not add new ingest logic here.
"""

from agents.mentions.ingest.auto import ingest
from agents.mentions.ingest.transcript import register

__all__ = ['ingest', 'register']
