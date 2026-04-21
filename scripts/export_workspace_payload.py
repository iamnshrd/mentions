from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mentions.presentation.workspace_payload import build_workspace_payload
from mentions_core.base.logging_config import setup as setup_logging
from mentions_core.base.utils import load_dotenv_files


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

    load_dotenv_files()
    setup_logging()

    payload = build_workspace_payload(
        args.query,
        user_id=args.user_id,
        mode=args.mode,
        news_limit=args.news_limit,
        transcript_limit=args.transcript_limit,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(output_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
