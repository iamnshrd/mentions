from __future__ import annotations

import json
import logging

from agents.mentions.config import WORDING_DB

log = logging.getLogger('mentions')


def load_preferred_replacements() -> dict[str, str]:
    try:
        payload = json.loads(WORDING_DB.read_text(encoding='utf-8'))
    except Exception as exc:
        log.debug('Failed to load wording DB from %s: %s', WORDING_DB, exc)
        return {}
    replacements = {}
    for row in payload.get('preferred_replacements', []):
        source = (row.get('source') or '').strip()
        target = (row.get('target') or '').strip()
        if source and target:
            replacements[source] = target
    return replacements


def apply_wording(text: str) -> str:
    value = (text or '').strip()
    replacements = load_preferred_replacements()
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value
