"""Canonical transcripts capability service entrypoint."""
from __future__ import annotations

import argparse

from agents.mentions.interfaces.capabilities.transcripts import api


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in (value or '').split(',') if item.strip()]


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

        p_manual = sub.add_parser('manual')
        p_manual.add_argument('file')
        p_manual.add_argument('--speaker', required=True)
        p_manual.add_argument('--event', required=True)
        p_manual.add_argument('--event-date', dest='event_date', default='')
        p_manual.add_argument('--format-tags', default='')
        p_manual.add_argument('--topic-tags', default='')
        p_manual.add_argument('--event-tags', default='')
        p_manual.add_argument('--mention-tags', default='')
        p_manual.add_argument('--quality-tags', default='')
        p_manual.add_argument('--notes', default='')

        args = parser.parse_args(argv)
        if args.ingest_action == 'auto':
            return api.ingest_auto(dry_run=args.dry_run)
        if args.ingest_action == 'manual':
            return api.ingest_manual_transcript(
                args.file,
                speaker=args.speaker,
                event=args.event,
                event_date=args.event_date,
                format_tags=_csv_list(args.format_tags),
                topic_tags=_csv_list(args.topic_tags),
                event_tags=_csv_list(args.event_tags),
                mention_tags=_csv_list(args.mention_tags),
                quality_tags=_csv_list(args.quality_tags),
                notes=args.notes,
            )
        return api.ingest_transcript(
            args.file,
            speaker=args.speaker,
            event=args.event,
            event_date=args.event_date,
        )


__all__ = ['TranscriptsCapabilityService']
