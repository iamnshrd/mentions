"""CLI-facing transcripts capability service."""
from __future__ import annotations

import argparse

from agents.mentions.capabilities.transcripts import api


class TranscriptsCapabilityService:
    def __init__(self, _context):
        self._context = _context

    def run_action(self, action: str, argv: list[str]):
        if action == 'ingest':
            return self._run_ingest(argv)
        if action == 'search':
            parser = argparse.ArgumentParser(prog='transcripts search')
            parser.add_argument('query')
            parser.add_argument('--limit', type=int, default=5)
            parser.add_argument('--speaker', default='')
            args = parser.parse_args(argv)
            return {
                'query': args.query,
                'results': api.search_transcripts(args.query, limit=args.limit, speaker=args.speaker),
            }
        if action == 'build':
            return api.build_kb()
        raise SystemExit(f'Unknown transcripts action: {action}')

    def _run_ingest(self, argv: list[str]):
        parser = argparse.ArgumentParser(prog='transcripts ingest')
        sub = parser.add_subparsers(dest='ingest_action', required=True)

        p_auto = sub.add_parser('auto')
        p_auto.add_argument('--dry-run', action='store_true')

        p_single = sub.add_parser('transcript')
        p_single.add_argument('file')
        p_single.add_argument('--speaker', default='')
        p_single.add_argument('--event', default='')
        p_single.add_argument('--event-date', dest='event_date', default='')

        args = parser.parse_args(argv)
        if args.ingest_action == 'auto':
            return api.ingest_auto(dry_run=args.dry_run)
        return api.ingest_transcript(
            args.file,
            speaker=args.speaker,
            event=args.event,
            event_date=args.event_date,
        )
