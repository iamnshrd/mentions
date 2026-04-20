#!/usr/bin/env python3
"""Unified CLI entry point for the Mentions agent library.

Usage examples:
    python -m library run "what's moving on Kalshi today?"
    python -m library run "https://www.kalshi.com/markets/kxinfantinomention/kxinfantinomention-26apr15"
    python -m library prompt "bitcoin price market"
    python -m library frame "fed rate decision market"
    python -m library fetch auto
    python -m library fetch market KXBTCD-25DEC
    python -m library analyze "is the bitcoin move signal or noise?"
    python -m library ingest auto
    python -m library ingest transcript path/to/transcript.txt
    python -m library ingest rechunk 42
    python -m library ingest rechunk --all
    python -m library kb build
    python -m library kb query --query "fed rate"
    python -m library schedule run
    python -m library schedule run --dry-run
    python -m library eval audit
    python -m library eval run
    python -m library eval run --retrieve --limit 5 --verbose
    python -m library extract run 42
    python -m library extract run --all --chunk-limit 20
    python -m library metrics summary
    python -m library metrics flush
    python -m library metrics reset
    python -m library trace list
    python -m library trace show <trace_id>
    python -m library cost summary
    python -m library cost summary --history
"""
import argparse
import json
import sys

from library.logging_config import setup as setup_logging


def cmd_run(args):
    from library._core.runtime.orchestrator import orchestrate
    # orchestrate() auto-detects Kalshi URLs and routes accordingly
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
        print(json.dumps(register(args.target, speaker=args.speaker,
                                  event=args.event, event_date=args.event_date),
                         ensure_ascii=False, indent=2))
    elif action == 'rechunk':
        from library._core.ingest.transcript import rechunk
        from library.db import connect
        if args.all:
            with connect() as conn:
                doc_ids = [r[0] for r in conn.execute(
                    'SELECT id FROM transcript_documents ORDER BY id'
                ).fetchall()]
            results = [rechunk(doc_id) for doc_id in doc_ids]
            summary = {
                'status':       'rechunked_all',
                'total_docs':   len(results),
                'ok':           sum(1 for r in results if r['status'] == 'rechunked'),
                'errors':       sum(1 for r in results if r['status'] == 'error'),
                'total_chunks': sum(r.get('chunks', 0) for r in results),
                'total_tokens': sum(r.get('tokens', 0) for r in results),
                'results':      results,
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            if not args.target:
                print('rechunk requires --all or a document id',
                      file=sys.stderr)
                sys.exit(2)
            try:
                doc_id = int(args.target)
            except ValueError:
                print(f'document id must be an integer, got {args.target!r}',
                      file=sys.stderr)
                sys.exit(2)
            print(json.dumps(rechunk(doc_id), ensure_ascii=False, indent=2))
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
    elif action == 'import-pmt':
        from library._core.kb.import_pmt import import_pmt
        print(json.dumps(import_pmt(args.src), ensure_ascii=False, indent=2))
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


def cmd_extract(args):
    from library._core.extract import run_extraction
    if args.extract_action != 'run':
        print(f'Unknown extract action: {args.extract_action}', file=sys.stderr)
        sys.exit(1)
    if args.all:
        result = run_extraction(all=True, chunk_limit=args.chunk_limit)
    else:
        if not args.target:
            print('extract run requires --all or a document id',
                  file=sys.stderr)
            sys.exit(2)
        try:
            doc_id = int(args.target)
        except ValueError:
            print(f'document id must be an integer, got {args.target!r}',
                  file=sys.stderr)
            sys.exit(2)
        result = run_extraction(document_id=doc_id,
                                chunk_limit=args.chunk_limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_eval(args):
    action = args.eval_action
    if action == 'audit':
        from library._core.eval.audit import audit
        print(json.dumps(audit(), ensure_ascii=False, indent=2))
    elif action == 'run':
        from library._core.eval.harness import run_and_persist
        report = run_and_persist(
            retrieve=bool(getattr(args, 'retrieve', False)),
            limit=getattr(args, 'limit', None),
            compare_paths=bool(getattr(args, 'compare_paths', False)),
        )
        # Keep the per-query detail out of stdout by default to avoid
        # flooding; --verbose restores it.
        if not getattr(args, 'verbose', False):
            report = {k: v for k, v in report.items() if k != 'queries'}
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f'Unknown eval action: {action}', file=sys.stderr)
        sys.exit(1)


def cmd_metrics(args):
    from library._core.obs import (
        get_collector, reset_collector, persist_event,
        load_events, summarize_events,
    )
    action = args.metrics_action
    if action == 'summary':
        snapshot = get_collector().snapshot()
        if getattr(args, 'history', False):
            events = load_events(limit=args.limit)
            print(json.dumps({
                'current':   snapshot,
                'aggregate': summarize_events(events),
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    elif action == 'flush':
        import time
        snapshot = get_collector().snapshot()
        snapshot['timestamp'] = time.time()
        persist_event(snapshot)
        print(json.dumps({'status': 'flushed', 'snapshot': snapshot},
                         ensure_ascii=False, indent=2))
    elif action == 'reset':
        reset_collector()
        print(json.dumps({'status': 'reset'}, ensure_ascii=False, indent=2))
    else:
        print(f'Unknown metrics action: {action}', file=sys.stderr)
        sys.exit(1)


def _cost_breakdown_from_counters(counter_rows):
    """Aggregate token + cost counters by model.

    Returns ``{model: {input, output, cache_read, cache_write, cost_usd}}``
    plus a ``_total`` entry.
    """
    by_model: dict = {}

    def _tag_model(tag_str):
        for part in (tag_str or '').split('|'):
            if part.startswith('model='):
                return part[len('model='):]
        return ''

    mapping = {
        'llm.input_tokens':        'input',
        'llm.output_tokens':       'output',
        'llm.cache_read_tokens':   'cache_read',
        'llm.cache_create_tokens': 'cache_write',
    }
    for row in counter_rows:
        name = row.get('name', '')
        model = _tag_model(row.get('tags', ''))
        value = int(row.get('value', 0))
        if name in mapping and model:
            bucket = by_model.setdefault(model, {})
            bucket[mapping[name]] = bucket.get(mapping[name], 0) + value
        elif name == 'llm.cost_micro_usd' and model:
            bucket = by_model.setdefault(model, {})
            bucket['cost_usd'] = bucket.get('cost_usd', 0.0) + value / 1_000_000.0

    total_cost = sum(b.get('cost_usd', 0.0) for b in by_model.values())
    return {
        'by_model':     by_model,
        'total_cost':   round(total_cost, 6),
    }


def cmd_cost(args):
    from library._core.obs import get_collector, load_events
    action = args.cost_action
    if action == 'summary':
        snap = get_collector().snapshot()
        current = _cost_breakdown_from_counters(snap.get('counters', []))
        payload = {'current': current}
        if getattr(args, 'history', False):
            events = load_events(limit=args.limit)
            all_rows = []
            for ev in events:
                all_rows.extend(ev.get('counters') or [])
            payload['aggregate'] = _cost_breakdown_from_counters(all_rows)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f'Unknown cost action: {action}', file=sys.stderr)
        sys.exit(1)


def cmd_trace(args):
    from library._core.obs import events_for_trace, list_traces
    action = args.trace_action
    if action == 'list':
        rows = list_traces(limit=args.limit or 20)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif action == 'show':
        if not args.trace_id:
            print('trace show requires a trace_id', file=sys.stderr)
            sys.exit(2)
        rows = events_for_trace(args.trace_id)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(f'Unknown trace action: {action}', file=sys.stderr)
        sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog='python -m library',
        description='Mentions — Kalshi Prediction Market Analyst CLI',
    )
    parser.add_argument('--user-id', dest='user_id', default='default',
                        help='User ID for multi-tenant state isolation')
    sub = parser.add_subparsers(dest='command')

    p_run = sub.add_parser(
        'run',
        help='Orchestrate a full analysis response (auto-detects Kalshi URLs)',
    )
    p_run.add_argument(
        'query',
        help='Market query or Kalshi URL (https://www.kalshi.com/markets/...)',
    )
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
    p_ingest.add_argument('ingest_action', choices=['auto', 'transcript', 'rechunk'])
    # Positional target: file path for `transcript`, doc id for `rechunk`,
    # ignored for `auto`. Parsed per-action in cmd_ingest.
    p_ingest.add_argument('target', nargs='?', default='',
                          help='Transcript file path, or document id (for rechunk)')
    p_ingest.add_argument('--speaker', default='', help='Speaker name')
    p_ingest.add_argument('--event', default='', help='Event name')
    p_ingest.add_argument('--event-date', dest='event_date', default='',
                          help='Event date (YYYY-MM-DD)')
    p_ingest.add_argument('--dry-run', dest='dry_run', action='store_true')
    p_ingest.add_argument('--all', dest='all', action='store_true',
                          help='Rechunk every document (for ingest rechunk)')
    p_ingest.set_defaults(func=cmd_ingest)

    p_kb = sub.add_parser('kb', help='Knowledge base operations')
    p_kb.add_argument('kb_action', choices=['build', 'query', 'migrate', 'import-pmt'])
    p_kb.add_argument('--query', default='', help='Search query')
    p_kb.add_argument('--limit', type=int, default=8)
    p_kb.add_argument('--src', default='pmt-architecture-dump/pmt_trader_knowledge.db',
                      help='Path to source PMT knowledge DB (for import-pmt)')
    p_kb.set_defaults(func=cmd_kb)

    p_schedule = sub.add_parser('schedule', help='Autonomous scheduled operations')
    p_schedule.add_argument('schedule_action', choices=['run'])
    p_schedule.add_argument('--dry-run', dest='dry_run', action='store_true',
                            help='Simulate run without writing output')
    p_schedule.set_defaults(func=cmd_schedule)

    p_eval = sub.add_parser('eval', help='Run evaluations')
    p_eval.add_argument('eval_action', choices=['audit', 'run'])
    p_eval.add_argument('--retrieve', dest='retrieve', action='store_true',
                        help='Include hybrid-retrieval metrics (eval run)')
    p_eval.add_argument('--limit', type=int, default=None,
                        help='Only run the first N gold queries (eval run)')
    p_eval.add_argument('--verbose', dest='verbose', action='store_true',
                        help='Include per-query details in stdout (eval run)')
    p_eval.add_argument('--compare-paths', dest='compare_paths',
                        action='store_true',
                        help='Emit LLM vs rules-baseline calibration diff '
                             '(eval run)')
    p_eval.set_defaults(func=cmd_eval)

    p_extract = sub.add_parser(
        'extract',
        help='LLM-driven knowledge extraction from ingested transcripts',
    )
    p_extract.add_argument('extract_action', choices=['run'],
                           help='Subcommand (run)')
    p_extract.add_argument('target', nargs='?', default='',
                           help='Document id to extract from (ignored with --all)')
    p_extract.add_argument('--all', dest='all', action='store_true',
                           help='Extract from every ingested document')
    p_extract.add_argument('--chunk-limit', dest='chunk_limit', type=int,
                           default=None,
                           help='Cap chunks per document (cost control / debug)')
    p_extract.set_defaults(func=cmd_extract)

    p_metrics = sub.add_parser(
        'metrics',
        help='Observability — show, flush, or reset in-process metrics',
    )
    p_metrics.add_argument('metrics_action',
                           choices=['summary', 'flush', 'reset'])
    p_metrics.add_argument('--history', dest='history', action='store_true',
                           help='Include aggregated historical snapshots')
    p_metrics.add_argument('--limit', type=int, default=None,
                           help='Max historical events to read (metrics summary --history)')
    p_metrics.set_defaults(func=cmd_metrics)

    p_trace = sub.add_parser('trace',
                             help='Inspect per-request trace events')
    p_trace.add_argument('trace_action', choices=['list', 'show'])
    p_trace.add_argument('trace_id', nargs='?', default='',
                         help='Trace id (for trace show)')
    p_trace.add_argument('--limit', type=int, default=None,
                         help='Max rows (trace list)')
    p_trace.set_defaults(func=cmd_trace)

    p_cost = sub.add_parser('cost',
                            help='Show LLM cost breakdown by model')
    p_cost.add_argument('cost_action', choices=['summary'])
    p_cost.add_argument('--history', dest='history', action='store_true',
                        help='Aggregate historical snapshots too')
    p_cost.add_argument('--limit', type=int, default=None,
                        help='Max historical events to read (with --history)')
    p_cost.set_defaults(func=cmd_cost)

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
