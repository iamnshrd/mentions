"""Shared shape helpers for canonical Mentions domain modules."""
from __future__ import annotations

from typing import Any


CONFIDENCE_LEVELS = {'low', 'medium', 'high'}
STATUS_LEVELS = {'ok', 'empty', 'unavailable', 'error', 'skipped'}


def normalize_status(value: str, default: str = 'unavailable') -> str:
    candidate = (value or '').strip().lower()
    return candidate if candidate in STATUS_LEVELS else default


def normalize_confidence(value: str, default: str = 'low') -> str:
    candidate = (value or '').strip().lower()
    return candidate if candidate in CONFIDENCE_LEVELS else default


def ensure_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def bundle_meta(**kwargs) -> dict:
    return {key: val for key, val in kwargs.items() if val not in (None, '', [], {})}
