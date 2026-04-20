#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

from agents.mentions.workflows.retrieve import retrieve_by_ticker, retrieve_market_data


def main() -> int:
    parser = argparse.ArgumentParser(description='Smoke test for retrieval paths.')
    parser.add_argument('--query', default='Will Trump mention Iran in a speech?')
    parser.add_argument('--ticker', default='KXTRUMPMENTION-26APR16')
    parser.add_argument('--fast', action='store_true', help='Enable MENTIONS_DEBUG_FAST=1 for faster ML path smoke')
    args = parser.parse_args()

    if args.fast:
        os.environ['MENTIONS_DEBUG_FAST'] = '1'

    query_result = retrieve_market_data(args.query)
    ticker_result = retrieve_by_ticker(args.ticker)

    payload = {
        'query': args.query,
        'query_has_data': query_result.get('has_data', False),
        'query_sources': query_result.get('sources_used', []),
        'ticker': args.ticker,
        'ticker_has_data': ticker_result.get('has_data', False),
        'ticker_sources': ticker_result.get('sources_used', []),
        'ticker_market_title': ((ticker_result.get('market') or {}).get('market_data') or {}).get('title', ''),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    ok = (
        isinstance(payload['query_sources'], list)
        and isinstance(payload['ticker_sources'], list)
        and 'market' in payload['ticker_sources']
    )
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
