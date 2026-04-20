#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

from agents.mentions.workflows.orchestrator import orchestrate_url


def main() -> int:
    parser = argparse.ArgumentParser(description='Fast smoke test for speaker-event URL orchestration.')
    parser.add_argument(
        'url',
        nargs='?',
        default='https://kalshi.com/markets/kxtrumpmention/what-will-trump-say/kxtrumpmention-26apr16',
        help='Kalshi market URL to test',
    )
    parser.add_argument('--user-id', default='default')
    parser.add_argument('--fast', action='store_true', help='Enable MENTIONS_DEBUG_FAST=1 for faster ML path smoke')
    args = parser.parse_args()

    if args.fast:
        os.environ['MENTIONS_DEBUG_FAST'] = '1'

    result = orchestrate_url(args.url, user_id=args.user_id)
    synthesis = result.get('synthesis', {}) or {}

    payload = {
        'url': args.url,
        'action': result.get('action', ''),
        'confidence': result.get('confidence', ''),
        'has_data': result.get('has_data', False),
        'report_present': bool(synthesis.get('analysis_report')),
        'reasoning_present': bool(synthesis.get('reasoning_chain')),
        'ticker': result.get('ticker', ''),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    ok = (
        payload['action'] == 'respond-with-data'
        and payload['has_data']
        and payload['report_present']
        and payload['reasoning_present']
    )
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
