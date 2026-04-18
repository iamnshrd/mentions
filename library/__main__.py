#!/usr/bin/env python3
"""Legacy CLI compatibility shim for the Mentions pack.

The canonical public interface is now ``python -m mentions_core ...``.
This module preserves the old ``python -m library ...`` commands by
translating them into pack-aware calls or thin wrappers around the new code.
"""
from __future__ import annotations

import argparse
import json
import sys

from library.logging_config import setup as setup_logging
from mentions_core.cli import main as openclaw_main
from mentions_core.base.utils import load_dotenv_files


def _print_payload(payload):
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


def _cmd_run(args) -> int:
    argv = ['run', 'mentions', args.query, '--user-id', args.user_id]
    return openclaw_main(argv)


def _cmd_prompt(args) -> int:
    argv = ['prompt', 'mentions', args.query, '--user-id', args.user_id]
    if args.system_only:
        argv.append('--system-only')
    return openclaw_main(argv)


def _cmd_frame(args) -> int:
    from library._core.runtime.frame import select_frame

    _print_payload(select_frame(args.query, user_id=args.user_id))
    return 0


def _cmd_fetch(args) -> int:
    if args.fetch_action == 'auto':
        from library._core.fetch.auto import fetch_all

        _print_payload(fetch_all(dry_run=args.dry_run))
        return 0

    from agents.mentions.modules.kalshi_provider import get_market_bundle

    _print_payload(get_market_bundle(args.ticker).get('market', {}))
    return 0


def _cmd_analyze(args) -> int:
    if args.json:
        argv = [
            'capability', 'mentions', 'analysis', 'query',
            args.query, '--user-id', args.user_id,
        ]
        return openclaw_main(argv)

    from library._core.runtime.orchestrator import orchestrate

    result = orchestrate(args.query, user_id=args.user_id)
    print(result.get('response', json.dumps(result, ensure_ascii=False, indent=2)))
    return 0


def _cmd_ingest(args) -> int:
    argv = ['capability', 'mentions', 'transcripts', 'ingest', args.ingest_action]
    if args.ingest_action == 'auto':
        if args.dry_run:
            argv.append('--dry-run')
    else:
        argv.append(args.file)
        if args.speaker:
            argv.extend(['--speaker', args.speaker])
        if args.event:
            argv.extend(['--event', args.event])
        if args.event_date:
            argv.extend(['--event-date', args.event_date])
    return openclaw_main(argv)


def _cmd_kb(args) -> int:
    if args.kb_action == 'migrate':
        from library._core.kb.migrate import migrate_up
        from library.db import connect

        with connect(auto_migrate=False) as conn:
            migrate_up(conn)
        print('Migration complete')
        return 0

    if args.kb_action == 'build':
        argv = ['capability', 'mentions', 'transcripts', 'build']
        return openclaw_main(argv)

    from library._core.kb.query import query

    _print_payload(query(args.query, limit=args.limit))
    return 0


def _cmd_schedule(args) -> int:
    argv = ['schedule', 'mentions', args.schedule_action]
    if args.dry_run:
        argv.append('--dry-run')
    return openclaw_main(argv)


def _cmd_eval(_args) -> int:
    from library._core.eval.audit import audit

    _print_payload(audit())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m library',
        description='Legacy Mentions CLI shim backed by OpenClaw.',
    )
    parser.add_argument(
        '--user-id',
        dest='user_id',
        default='default',
        help='User ID for multi-tenant state isolation',
    )
    sub = parser.add_subparsers(dest='command')

    p_run = sub.add_parser('run', help='Run the Mentions pack against a query')
    p_run.add_argument('query')
    p_run.set_defaults(func=_cmd_run)

    p_prompt = sub.add_parser('prompt', help='Build an LLM prompt bundle')
    p_prompt.add_argument('query')
    p_prompt.add_argument(
        '--system-only',
        dest='system_only',
        action='store_true',
        help='Print only the system prompt text',
    )
    p_prompt.set_defaults(func=_cmd_prompt)

    p_frame = sub.add_parser('frame', help='Select a market analysis frame')
    p_frame.add_argument('query')
    p_frame.set_defaults(func=_cmd_frame)

    p_fetch = sub.add_parser('fetch', help='Fetch market data')
    p_fetch.add_argument('fetch_action', choices=['auto', 'market'])
    p_fetch.add_argument('ticker', nargs='?', default='')
    p_fetch.add_argument('--dry-run', dest='dry_run', action='store_true')
    p_fetch.set_defaults(func=_cmd_fetch)

    p_analyze = sub.add_parser('analyze', help='Run the analysis pipeline')
    p_analyze.add_argument('query')
    p_analyze.add_argument('--json', dest='json', action='store_true')
    p_analyze.set_defaults(func=_cmd_analyze)

    p_ingest = sub.add_parser('ingest', help='Ingest transcripts')
    p_ingest.add_argument('ingest_action', choices=['auto', 'transcript'])
    p_ingest.add_argument('file', nargs='?', default='')
    p_ingest.add_argument('--speaker', default='')
    p_ingest.add_argument('--event', default='')
    p_ingest.add_argument('--event-date', dest='event_date', default='')
    p_ingest.add_argument('--dry-run', dest='dry_run', action='store_true')
    p_ingest.set_defaults(func=_cmd_ingest)

    p_kb = sub.add_parser('kb', help='Knowledge base operations')
    p_kb.add_argument('kb_action', choices=['build', 'query', 'migrate'])
    p_kb.add_argument('--query', default='')
    p_kb.add_argument('--limit', type=int, default=8)
    p_kb.set_defaults(func=_cmd_kb)

    p_schedule = sub.add_parser('schedule', help='Autonomous scheduled operations')
    p_schedule.add_argument('schedule_action', choices=['run'])
    p_schedule.add_argument('--dry-run', dest='dry_run', action='store_true')
    p_schedule.set_defaults(func=_cmd_schedule)

    p_eval = sub.add_parser('eval', help='Run evaluations')
    p_eval.add_argument('eval_action', choices=['audit'])
    p_eval.set_defaults(func=_cmd_eval)

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv_files()
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, 'command', None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
