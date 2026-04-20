#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

from agents.mentions.workflows.orchestrator import orchestrate


def main() -> int:
    parser = argparse.ArgumentParser(description='Fast smoke test for text-query orchestration.')
    parser.add_argument(
        'query',
        nargs='?',
        default='Will Trump mention Iran in a speech?',
        help='Text query to test',
    )
    parser.add_argument('--user-id', default='default')
    parser.add_argument('--fast', action='store_true', help='Enable MENTIONS_DEBUG_FAST=1 for faster ML path smoke')
    args = parser.parse_args()

    if args.fast:
        os.environ['MENTIONS_DEBUG_FAST'] = '1'

    result = orchestrate(args.query, user_id=args.user_id)
    synthesis = result.get('synthesis', {}) or {}

    payload = {
        'query': args.query,
        'action': result.get('action', ''),
        'confidence': result.get('confidence', ''),
        'has_response': bool(result.get('response')),
        'has_synthesis': bool(synthesis),
        'has_reasoning': bool(synthesis.get('reasoning_chain')),
        'has_sources': bool(result.get('sources')),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    ok = (
        payload['action'] in {'respond-with-data', 'answer-directly'}
        and payload['has_response']
    )
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
