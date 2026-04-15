"""Legacy ingest facade for package-level compatibility imports."""

from library._core.ingest.auto import ingest
from library._core.ingest.transcript import register

__all__ = ['ingest', 'register']
