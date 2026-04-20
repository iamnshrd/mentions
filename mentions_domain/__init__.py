"""Canonical Mentions domain package.

This package owns reusable business-domain logic that should not live in
runtime/bootstrap code (`mentions_core`) or pack/orchestration adapters
(`agents/mentions`).
"""

__all__ = [
    'analysis',
    'contracts',
    'normalize',
    'market_resolution',
]
