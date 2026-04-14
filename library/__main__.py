#!/usr/bin/env python3
"""Unified CLI entry point for the Mentions agent library.

Usage examples:
    python -m library run "what's moving on Kalshi today?"
    python -m library prompt "bitcoin price market"
    python -m library frame "fed rate decision market"
    python -m library fetch auto
    python -m library fetch market KXBTCD-25DEC
    python -m library analyze "is the bitcoin move signal or noise?"
    python -m library ingest auto
    python -m library ingest transcript path/to/transcript.txt
    python -m library kb build
    python -m library kb query --query "fed rate"
    python -m library schedule run
    python -m library schedule run --dry-run
    python -m library eval audit
"""
import argparse
import json
import sys

from library.logging_config import setup as setup_logging


def cmd_run(args):
    from library._core.runtime.orchestrator import orchestrate
    print(json.dumps(orchestrate(args.query, user_id=args.user_id),
                     ensure_ascii=False, indent=2))


def cmd_prompt(args):
    from library._core.runtime.orchestrator import orchestrate_for_llm
    result = orchestrate_for_llm(args.query, user_id=args.user_id)
    if args.system_only:
        print(result.get('system', ''))
    else:
        print(json.dumps({
            'system': result.get('system', ''),
            'user': result.get('user', ''),
            'action': result.get('action', ''),
            'mode': result.get('mode', ''),
        }, ensure_ascii=False, indent=2))


def cmd_frame(args):
    from library._core.runtime.frame import select_frame
    print(json.dumps(select_frame(args.query), ensure_ascii=False, indent=2))


def cmd_fetch(args):
    action = args.fetch_action
    if action == 'auto':
        from library._core.fetch.auto import fetch_all
        print(json.dumps(fetch_all(dry_run=args.dry_run),
                         ensure_ascii=False, indent=2))
    elif action == 'market':
        from library._core.fetch.kalshi import get_market
        print(json.dumps(get_market(args.ticker), ensure_ascii=False, indent=2))
    else:
        print(f'Unknown fetch action: {action}', file=sys.stderr)
        sys.exit(1)


def cmd_analyze(args):
    from library._core.runtime.orchestrator import orchestrate
    result = orchestrate(args.query, user_id=args.user_id)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get('response', json.dumps(result, ensure_ascii=False, indent=2)))


def cmd_ingest(args):
    action = args.ingest_action
    if action == 'auto':
        from library._core.ingest.auto import ingest
        print(json.dumps(ingest(dry_run=args.dry_run), ensure_ascii=False, indent=2))
    elif action == 'transcript':
        from library._core.ingest.transcript import register
        print(json.dumps(register(args.file, speaker=args.speaker,
                                  event=args.event, event_date=args.event_date),
                         ensure_ascii=False, indent=2))
    else:
        print(f'Unknown ingest action: {action}', file=sys.stderr)
        sys.exit(1)


def cmd_kb(args):
    action = args.kb_action
    if action == 'build':
        from library._core.kb.build import build
        print(json.dumps(build(), ensure_ascii=False, indent=2))
    elif action == 'query':
        from library._core.kb.query import query
        print(json.dumps(query(args.query, limit=args.limit),
                         ensure_ascii=False, indent=2))
    elif action == 'migrate':
        from library._core.kb.migrate import migrate_up
        from library.db import connect
        with connect(auto_migrate=False) as conn:
            migrate_up(conn)
        print('Migration complete')
    else:
        print(f'Unknown kb action: {action}', file=sys.stderr)
        sys.exit(1)


def cmd_schedule(args):
    action = args.schedule_action
    if action == 'run':
        from library._core.scheduler.runner import run_autonomous
        result = run_autonomous(dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f'Unknown schedule action: {action}', file=sys.stderr)
        sys.exit(1)


def cmd_eval(args):
    action = args.eval_action
    if action == 'audit':
        from library._core.eval.audit import audit
        print(json.dumps(audit(), ensure_ascii=False, indent=2))
    else:
        print(f'Unknown eval action: {action}', file=sys.stderr)
        sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog='python -m library',
        description='Mentions — Kalshi Prediction Market Analyst CLI',
    )
    parser.add_argument('--user-id', dest='user_id', default='default',
                        help='User ID for multi-tenant state isolation')
    sub = parser.add_subparsers(dest='command')

    p_run = sub.add_parser('run', help='Orchestrate a full analysis response')
    p_run.add_argument('query')
    p_run.set_defaults(func=cmd_run)

    p_prompt = sub.add_parser('prompt', help='Build LLM prompt bundle for OpenClaw')
    p_prompt.add_argument('query')
    p_prompt.add_argument('--system-only', dest='system_only', action='store_true',
                          help='Print only the system prompt text')
    p_prompt.set_defaults(func=cmd_prompt)

    p_frame = sub.add_parser('frame', help='Select market analysis frame')
    p_frame.add_argument('query')
    p_frame.set_defaults(func=cmd_frame)

    p_fetch = sub.add_parser('fetch', help='Fetch market data')
    p_fetch.add_argument('fetch_action', choices=['auto', 'market'])
    p_fetch.add_argument('ticker', nargs='?', default='',
                         help='Market ticker (for fetch market)')
    p_fetch.add_argument('--dry-run', dest='dry_run', action='store_true')
    p_fetch.set_defaults(func=cmd_fetch)

    p_analyze = sub.add_parser('analyze', help='Run analysis pipeline')
    p_analyze.add_argument('query')
    p_analyze.add_argument('--json', dest='json', action='store_true',
                           help='Output full JSON result')
    p_analyze.set_defaults(func=cmd_analyze)

    p_ingest = sub.add_parser('ingest', help='Ingest transcripts')
    p_ingest.add_argument('ingest_action', choices=['auto', 'transcript'])
    p_ingest.add_argument('file', nargs='?', default='',
                          help='Path to transcript file (for ingest transcript)')
    p_ingest.add_argument('--speaker', default='', help='Speaker name')
    p_ingest.add_argument('--event', default='', help='Event name')
    p_ingest.add_argument('--event-date', dest='event_date', default='',
                          help='Event date (YYYY-MM-DD)')
    p_ingest.add_argument('--dry-run', dest='dry_run', action='store_true')
    p_ingest.set_defaults(func=cmd_ingest)

    p_kb = sub.add_parser('kb', help='Knowledge base operations')
    p_kb.add_argument('kb_action', choices=['build', 'query', 'migrate'])
    p_kb.add_argument('--query', default='', help='Search query')
    p_kb.add_argument('--limit', type=int, default=8)
    p_kb.set_defaults(func=cmd_kb)

    p_schedule = sub.add_parser('schedule', help='Autonomous scheduled operations')
    p_schedule.add_argument('schedule_action', choices=['run'])
    p_schedule.add_argument('--dry-run', dest='dry_run', action='store_true',
                            help='Simulate run without writing output')
    p_schedule.set_defaults(func=cmd_schedule)

    p_eval = sub.add_parser('eval', help='Run evaluations')
    p_eval.add_argument('eval_action', choices=['audit'])
    p_eval.set_defaults(func=cmd_eval)

    return parser


def main():
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == '__main__':
    main()
