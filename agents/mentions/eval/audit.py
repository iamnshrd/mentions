"""Quality audit for the Mentions agent runtime.

Checks that the core pipeline is wired correctly and reports any issues.
"""
from __future__ import annotations

import logging

from agents.mentions.utils import now_iso

log = logging.getLogger('mentions')


def audit() -> dict:
    """Run a suite of lightweight checks against the runtime pipeline.

    Returns a report dict with pass/fail for each check.
    """
    checks = []

    # Check 1: DB schema
    checks.append(_check_db())

    # Check 2: Config files present
    checks.append(_check_config_files())

    # Check 3: Orchestrator imports
    checks.append(_check_orchestrator())

    # Check 4: CLI frame selection
    checks.append(_check_frame())

    passed = sum(1 for c in checks if c['status'] == 'pass')
    failed = len(checks) - passed

    return {
        'timestamp': now_iso(),
        'checks': checks,
        'passed': passed,
        'failed': failed,
        'status': 'ok' if failed == 0 else 'degraded',
    }


def _check_db() -> dict:
    try:
        from agents.mentions.db import connect
        from agents.mentions.kb.migrate import get_schema_version, LATEST_VERSION
        with connect() as conn:
            version = get_schema_version(conn)
        return {
            'check': 'db_schema',
            'status': 'pass' if version >= LATEST_VERSION else 'fail',
            'detail': f'version={version}, latest={LATEST_VERSION}',
        }
    except Exception as exc:
        return {'check': 'db_schema', 'status': 'fail', 'detail': str(exc)}


def _check_config_files() -> dict:
    from agents.mentions.config import THRESHOLDS, MARKET_CATEGORIES, ANALYSIS_MODES
    missing = []
    for path in (THRESHOLDS, MARKET_CATEGORIES, ANALYSIS_MODES):
        if not path.exists():
            missing.append(path.name)
    return {
        'check': 'config_files',
        'status': 'pass' if not missing else 'fail',
        'detail': f'missing: {missing}' if missing else 'all present',
    }


def _check_orchestrator() -> dict:
    try:
        from agents.mentions.runtime.orchestrator import detect_mode, should_use_kb
        m = detect_mode('what is happening with bitcoin')
        k = should_use_kb('bitcoin price market')
        return {
            'check': 'orchestrator',
            'status': 'pass',
            'detail': f'detect_mode={m}, should_use_kb={k}',
        }
    except Exception as exc:
        return {'check': 'orchestrator', 'status': 'fail', 'detail': str(exc)}


def _check_frame() -> dict:
    try:
        from agents.mentions.runtime.frame import select_frame
        frame = select_frame('why is the fed market moving?')
        return {
            'check': 'frame_selection',
            'status': 'pass',
            'detail': f'route={frame.get("route")}, mode={frame.get("mode")}',
        }
    except Exception as exc:
        return {'check': 'frame_selection', 'status': 'fail', 'detail': str(exc)}
