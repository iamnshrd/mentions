"""Shared base-layer paths and default configuration."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
WORKSPACE = PROJECT / 'workspace'
CONTINUITY = WORKSPACE / 'continuity.json'
SESSION_STATE = WORKSPACE / 'session_state.json'
USER_STATE = WORKSPACE / 'user_state.json'
EFFECTIVENESS = WORKSPACE / 'effectiveness_memory.json'
CHECKPOINTS = WORKSPACE / 'session_checkpoints.jsonl'
CONTEXT_GRAPH = WORKSPACE / 'context_graph.json'
CONTINUITY_SUMMARY = WORKSPACE / 'continuity_summary.json'
METRICS_LOG = WORKSPACE / 'metrics.jsonl'
TRACE_LOG = WORKSPACE / 'traces.jsonl'

_default_store = None


def get_default_store():
    """Return the default workspace-backed state store."""
    global _default_store
    if _default_store is None:
        from mentions_core.base.adapters.fs_store import FileSystemStore
        _default_store = FileSystemStore(WORKSPACE)
    return _default_store
