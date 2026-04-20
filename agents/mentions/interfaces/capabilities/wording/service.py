"""Canonical wording capability service entrypoint."""
from __future__ import annotations

import argparse

from agents.mentions.interfaces.capabilities.wording import api


class WordingCapabilityService:
    def __init__(self, _context):
        self._context = _context

    def run_action(self, action: str, argv: list[str]):
        parser = argparse.ArgumentParser(prog=f'wording {action}')
        parser.add_argument('text')
        parser.add_argument('--mode', choices=['safe', 'full'], default='safe')
        args = parser.parse_args(argv)

        if action == 'check':
            return api.check_text(args.text, apply_fixes=False, mode=args.mode)
        if action == 'rewrite':
            return api.check_text(args.text, apply_fixes=True, mode=args.mode)
        raise SystemExit(f'Unknown wording action: {action}')


__all__ = ['WordingCapabilityService']
