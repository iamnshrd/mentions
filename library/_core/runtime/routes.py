"""Compatibility shim for legacy ``library._core.runtime.routes`` imports."""

from agents.mentions.runtime.routes import (
    ALL_KB_KEYWORDS,
    ROUTES,
    infer_route,
    route_voice_bias,
)

__all__ = [
    'ALL_KB_KEYWORDS',
    'ROUTES',
    'infer_route',
    'route_voice_bias',
]
