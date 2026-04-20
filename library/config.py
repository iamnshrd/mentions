#!/usr/bin/env python3
"""Centralised paths and settings for the Mentions agent.

Every module imports paths from here instead of hardcoding them.
All paths are derived relative to this file so the project works
regardless of where it is deployed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent            # library/
PROJECT = ROOT.parent                             # mentions/
WORKSPACE = PROJECT / 'workspace'

# --- SQLite knowledge base ---
DB_PATH = ROOT / 'mentions_data.db'

# --- Manifest & source material ---
MANIFEST = ROOT / 'manifest.json'
INCOMING = ROOT / 'incoming'
TRANSCRIPTS = ROOT / 'transcripts'

# --- Library JSON assets ---
MARKET_CATEGORIES = ROOT / 'market_categories.json'
ANALYSIS_MODES = ROOT / 'analysis_modes.json'
SOURCE_PROFILES = ROOT / 'source_profiles.json'

# --- Runtime thresholds (tunable) ---
THRESHOLDS = ROOT / 'thresholds.json'

# --- Intermediate build artefacts ---
INGEST_REPORT = ROOT / 'ingest_report.json'

# --- Dashboard output ---
DASHBOARD = PROJECT / 'dashboard'
DASHBOARD_LATEST = DASHBOARD / 'latest_analysis.json'

# --- Workspace JSON state files (legacy, kept for backward-compat) ---
CONTINUITY = WORKSPACE / 'continuity.json'
SESSION_STATE = WORKSPACE / 'session_state.json'
USER_STATE = WORKSPACE / 'user_state.json'
EFFECTIVENESS = WORKSPACE / 'effectiveness_memory.json'
CHECKPOINTS = WORKSPACE / 'session_checkpoints.jsonl'
CONTEXT_GRAPH = WORKSPACE / 'context_graph.json'
CONTINUITY_SUMMARY = WORKSPACE / 'continuity_summary.json'

# --- Eval / regression artefacts ---
EVAL_REPORT = ROOT / 'eval_report.json'
RUNTIME_AUDIT_REPORT = ROOT / 'runtime_audit_report.json'

# --- Observability (Phase 7+) ---
METRICS_LOG = WORKSPACE / 'metrics.jsonl'
TRACE_LOG   = WORKSPACE / 'traces.jsonl'

# --- Multi-tenant store factory ---

_default_store = None


def get_default_store():
    """Return a singleton FileSystemStore rooted at WORKSPACE."""
    global _default_store
    if _default_store is None:
        from library._adapters.fs_store import FileSystemStore
        _default_store = FileSystemStore(WORKSPACE)
    return _default_store
