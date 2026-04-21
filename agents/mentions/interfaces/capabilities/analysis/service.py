"""Canonical analysis capability service entrypoint."""
from __future__ import annotations

import argparse

from agents.mentions.interfaces.capabilities.analysis import api


class AnalysisCapabilityService:
    def __init__(self, _context):
        self._context = _context

    def run_action(self, action: str, argv: list[str]):
        if action == 'query':
            parser = argparse.ArgumentParser(prog='analysis query')
            parser.add_argument('query')
            parser.add_argument('--user-id', default='default')
            args = parser.parse_args(argv)
            return api.run_query(args.query, user_id=args.user_id)

        if action == 'url':
            parser = argparse.ArgumentParser(prog='analysis url')
            parser.add_argument('url')
            parser.add_argument('--user-id', default='default')
            args = parser.parse_args(argv)
            return api.run_url(args.url, user_id=args.user_id)

        if action == 'prompt':
            parser = argparse.ArgumentParser(prog='analysis prompt')
            parser.add_argument('query')
            parser.add_argument('--user-id', default='default')
            parser.add_argument('--system-only', action='store_true')
            args = parser.parse_args(argv)
            return api.build_prompt(
                args.query,
                user_id=args.user_id,
                system_only=args.system_only,
            )

        if action == 'autonomous':
            parser = argparse.ArgumentParser(prog='analysis autonomous')
            parser.add_argument('--dry-run', action='store_true')
            args = parser.parse_args(argv)
            return api.run_autonomous_scan(dry_run=args.dry_run)

        if action == 'workspace':
            parser = argparse.ArgumentParser(prog='analysis workspace')
            parser.add_argument('query')
            parser.add_argument('--user-id', default='default')
            parser.add_argument('--mode', choices=['query', 'url'], default='query')
            parser.add_argument('--news-limit', type=int, default=5)
            parser.add_argument('--transcript-limit', type=int, default=5)
            args = parser.parse_args(argv)
            return api.build_workspace(
                args.query,
                user_id=args.user_id,
                mode=args.mode,
                news_limit=args.news_limit,
                transcript_limit=args.transcript_limit,
            )

        raise SystemExit(f'Unknown analysis action: {action}')


__all__ = ['AnalysisCapabilityService']
