"""CLI-facing news/context capability service."""
from __future__ import annotations

import argparse

from agents.mentions.capabilities.news_context import api


class NewsContextCapabilityService:
    def __init__(self, _context):
        self._context = _context

    def run_action(self, action: str, argv: list[str]):
        if action != 'build':
            raise SystemExit(f'Unknown news_context action: {action}')
        parser = argparse.ArgumentParser(prog='news_context build')
        parser.add_argument('query')
        parser.add_argument('--category', default='general')
        parser.add_argument('--require-live', action='store_true')
        args = parser.parse_args(argv)
        return api.build_context(
            args.query,
            category=args.category,
            require_live=args.require_live,
        )
