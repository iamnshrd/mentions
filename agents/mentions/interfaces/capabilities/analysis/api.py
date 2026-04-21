"""Canonical analysis capability API entrypoint."""
from __future__ import annotations

from agents.mentions.interfaces.capabilities.wording.api import check_text as check_wording
from agents.mentions.workflows.scheduling import run_autonomous
from agents.mentions.workflows.orchestrator import (
    orchestrate,
    orchestrate_for_llm,
    orchestrate_url,
)


def run_query(query: str, user_id: str = 'default') -> dict:
    result = orchestrate(query, user_id=user_id)
    return _apply_wording(result)


def run_url(url: str, user_id: str = 'default') -> dict:
    result = orchestrate_url(url, user_id=user_id)
    return _apply_wording(result)


def build_prompt(query: str, user_id: str = 'default',
                 system_only: bool = False) -> dict | str:
    payload = orchestrate_for_llm(query, user_id=user_id)
    if system_only:
        response = payload.get('response', '')
        return response if isinstance(response, str) else ''
    return payload


def run_autonomous_scan(dry_run: bool = False) -> dict:
    return run_autonomous(dry_run=dry_run)


def build_workspace(query: str, user_id: str = 'default',
                    mode: str = 'query', news_limit: int = 5,
                    transcript_limit: int = 5) -> dict:
    from agents.mentions.presentation.workspace_payload import build_workspace_payload

    return build_workspace_payload(
        query,
        user_id=user_id,
        mode=mode,
        news_limit=news_limit,
        transcript_limit=transcript_limit,
    )


def _apply_wording(result: dict) -> dict:
    response = result.get('response')
    if not response:
        return result
    wording = check_wording(response, apply_fixes=True, mode='safe')
    updated = dict(result)
    updated['response_raw'] = response
    updated['response'] = wording['text']
    updated['wording'] = {
        'ok': wording['ok'],
        'warnings': wording['warnings'],
        'rewrite_count': wording['rewrite_count'],
    }
    return updated

__all__ = [
    'build_prompt',
    'build_workspace',
    'run_autonomous_scan',
    'run_query',
    'run_url',
]
