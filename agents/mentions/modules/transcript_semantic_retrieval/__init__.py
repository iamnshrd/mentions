"""Transcript semantic retrieval package.

Current main-path integration is centered on:
- `strategy.retrieve_family_segments`
- `client.*` remote worker calls
- `family_taxonomy`

Other modules in this package are primarily experimental/research tooling.
"""

from .prototype import semantic_segment_search
from .strategy import retrieve_family_segments

__all__ = [
    'retrieve_family_segments',
    'semantic_segment_search',
]
