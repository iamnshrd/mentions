from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mentions_core.cli import main as runtime_main


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Export a Mentions research workspace payload for the static UI.'
    )
    parser.add_argument('query')
    parser.add_argument('--output', default='docs/ui/workspace-data.json')
    parser.add_argument('--user-id', default='default')
    parser.add_argument('--mode', choices=['query', 'url'], default='query')
    parser.add_argument('--news-limit', type=int, default=5)
    parser.add_argument('--transcript-limit', type=int, default=5)
    args = parser.parse_args()

    return runtime_main([
        'workspace',
        args.query,
        '--user-id', args.user_id,
        '--mode', args.mode,
        '--news-limit', str(args.news_limit),
        '--transcript-limit', str(args.transcript_limit),
        '--output', str(Path(args.output)),
    ])


if __name__ == '__main__':
    raise SystemExit(main())
