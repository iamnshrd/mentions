"""Programmatic API for wording validation and rewrites."""
from __future__ import annotations

from agents.mentions.wording.enforcer import check_text as check_text_impl


def check_text(text: str, apply_fixes: bool = False, mode: str = 'safe') -> dict:
    return check_text_impl(text, apply_fixes=apply_fixes, mode=mode)


def enforce_text(text: str, mode: str = 'safe') -> str:
    return check_text_impl(text, apply_fixes=True, mode=mode)['text']
