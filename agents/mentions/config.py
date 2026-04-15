"""Centralised paths and settings for the Mentions pack."""
from __future__ import annotations

from pathlib import Path

from mentions_core.base.config import WORKSPACE, get_default_store as get_base_store

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
ASSETS = ROOT / 'assets'
DATA = WORKSPACE / 'mentions'
MANIFEST = ROOT / 'manifest.json'
SKILLS = ROOT / 'skills'
WORDING_DB = ROOT / 'wording' / 'markets_wording_db.json'

DB_PATH = DATA / 'mentions_data.db'
INCOMING = DATA / 'incoming'
TRANSCRIPTS = DATA / 'transcripts'
PROCESSING = DATA / 'processing'
PROCESSED = DATA / 'processed'
FAILED = DATA / 'failed'
INGEST_JOBS = DATA / 'ingest_jobs.jsonl'

MARKET_CATEGORIES = ASSETS / 'market_categories.json'
ANALYSIS_MODES = ASSETS / 'analysis_modes.json'
SOURCE_PROFILES = ASSETS / 'source_profiles.json'
THRESHOLDS = ASSETS / 'thresholds.json'

INGEST_REPORT = DATA / 'ingest_report.json'
EVAL_REPORT = DATA / 'eval_report.json'
RUNTIME_AUDIT_REPORT = DATA / 'runtime_audit_report.json'

DASHBOARD = PROJECT / 'dashboard' / 'mentions'
DASHBOARD_LATEST = DASHBOARD / 'latest_analysis.json'

NEWS_API_URL = 'https://newsapi.org/v2/everything'


def get_default_store():
    """Return the shared OpenClaw state store for this pack."""
    return get_base_store()
