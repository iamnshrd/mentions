#!/usr/bin/env python3
import argparse, json, os, sys

if __package__ is None or __package__ == '':
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from market_pipeline.analyze import analyze_event
from market_pipeline.report_builder import build_report_json
from market_pipeline.render import render_report


def cmd_analyze(args):
    out = analyze_event(args.ticker, args.preset, args.speaker, args.format, args.archetype, args.event_class, args.freeform)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_report(args):
    payload = build_report_json(args.ticker, args.preset)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(render_report(payload))


def main():
    ap = argparse.ArgumentParser(prog='market-pipeline')
    sp = ap.add_subparsers(dest='subcmd', required=True)

    a = sp.add_parser('analyze')
    a.add_argument('ticker')
    a.add_argument('--preset', default='')
    a.add_argument('--freeform', default='')
    a.add_argument('--speaker', default='')
    a.add_argument('--format', default='')
    a.add_argument('--archetype', default='')
    a.add_argument('--event-class', action='append')
    a.set_defaults(func=cmd_analyze)

    r = sp.add_parser('report')
    r.add_argument('ticker')
    r.add_argument('--preset', default='iran-press')
    r.add_argument('--json', action='store_true')
    r.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
