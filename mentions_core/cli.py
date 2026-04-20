"""Generic CLI for the local Mentions runtime."""
from __future__ import annotations

import argparse
import json
import sys

from mentions_core.base.logging_config import setup as setup_logging
from mentions_core.base.registry import get_pack, list_packs
from mentions_core.base.scheduler.runner import run_pack_schedule
from mentions_core.base.utils import load_dotenv_files
from mentions_core.base.bootstrap_checks import run_bootstrap_checks


def _print_payload(payload):
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


def _cost_breakdown_from_counters(counter_rows):
    """Aggregate token + cost counters by model."""
    by_model: dict[str, dict[str, float | int]] = {}

    def _tag_model(tag_str):
        for part in (tag_str or '').split('|'):
            if part.startswith('model='):
                return part[len('model='):]
        return ''

    mapping = {
        'llm.input_tokens': 'input',
        'llm.output_tokens': 'output',
        'llm.cache_read_tokens': 'cache_read',
        'llm.cache_create_tokens': 'cache_write',
    }

    for row in counter_rows or []:
        name = row.get('name', '')
        model = _tag_model(row.get('tags', ''))
        if not model:
            continue
        bucket = by_model.setdefault(model, {
            'input': 0,
            'output': 0,
            'cache_read': 0,
            'cache_write': 0,
            'cost_usd': 0.0,
        })
        if name in mapping:
            bucket[mapping[name]] += int(row.get('value', 0) or 0)
        elif name == 'llm.cost_micro_usd':
            bucket['cost_usd'] += float(row.get('value', 0) or 0) / 1_000_000.0

    total_cost = round(sum(float(item['cost_usd']) for item in by_model.values()), 6)
    for item in by_model.values():
        item['cost_usd'] = round(float(item['cost_usd']), 6)
    return {'by_model': by_model, 'total_cost': total_cost}


def cmd_run(args):
    pack = get_pack(args.pack)
    _print_payload(pack.run(args.query, user_id=args.user_id))


def cmd_answer(args):
    pack = get_pack(args.pack)
    payload = pack.run(args.query, user_id=args.user_id)
    if isinstance(payload, dict):
        response = payload.get('response')
        if isinstance(response, str) and response.strip():
            print(response)
            return
        response_raw = payload.get('response_raw')
        if isinstance(response_raw, str) and response_raw.strip():
            print(response_raw)
            return
    _print_payload(payload)


def cmd_prompt(args):
    pack = get_pack(args.pack)
    payload = pack.prompt(args.query, user_id=args.user_id, system_only=args.system_only)
    _print_payload(payload)


def cmd_capability(args):
    pack = get_pack(args.pack)
    descriptor = pack.capability_descriptors().get(args.capability)
    if descriptor is None:
        raise SystemExit(f'Unknown capability for pack {args.pack}: {args.capability}')
    service = descriptor.service_factory(pack.build_context())
    _print_payload(service.run_action(args.action, args.args))


def cmd_schedule(args):
    _print_payload(run_pack_schedule(args.pack, args.action, dry_run=args.dry_run))


def cmd_packs(_args):
    _print_payload({'packs': list_packs()})


def cmd_health(_args):
    from agents.mentions.workflows.validation import runtime_validation_report
    _print_payload(runtime_validation_report())


def build_parser():
    parser = argparse.ArgumentParser(
        prog='python -m mentions_core',
        description='Local Mentions runtime with pack-style commands.',
    )
    sub = parser.add_subparsers(dest='command')

    p_run = sub.add_parser('run', help='Run a pack against a user query')
    p_run.add_argument('pack')
    p_run.add_argument('query')
    p_run.add_argument('--user-id', default='default')
    p_run.set_defaults(func=cmd_run)

    p_answer = sub.add_parser('answer', help='Run a pack and print the plain-text answer when available')
    p_answer.add_argument('pack')
    p_answer.add_argument('query')
    p_answer.add_argument('--user-id', default='default')
    p_answer.set_defaults(func=cmd_answer)

    p_prompt = sub.add_parser('prompt', help='Build an LLM prompt bundle for a pack')
    p_prompt.add_argument('pack')
    p_prompt.add_argument('query')
    p_prompt.add_argument('--user-id', default='default')
    p_prompt.add_argument('--system-only', action='store_true')
    p_prompt.set_defaults(func=cmd_prompt)

    p_capability = sub.add_parser('capability', help='Run a capability action')
    p_capability.add_argument('pack')
    p_capability.add_argument('capability')
    p_capability.add_argument('action')
    p_capability.add_argument('args', nargs=argparse.REMAINDER)
    p_capability.set_defaults(func=cmd_capability)

    p_schedule = sub.add_parser('schedule', help='Run a scheduler action for a pack')
    p_schedule.add_argument('pack')
    p_schedule.add_argument('action')
    p_schedule.add_argument('--dry-run', action='store_true')
    p_schedule.set_defaults(func=cmd_schedule)

    p_packs = sub.add_parser('packs', help='List registered packs')
    p_packs.set_defaults(func=cmd_packs)

    p_health = sub.add_parser('health', help='Show runtime infrastructure health')
    p_health.set_defaults(func=cmd_health)

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
        if args.command != 'health':
            run_bootstrap_checks(strict=False)
        args.func(args)
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
