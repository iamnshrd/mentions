"""Compatibility shim for legacy ``library._core.ingest.transcript`` imports."""

from agents.mentions.ingest.transcript import register

__all__ = ['register']
