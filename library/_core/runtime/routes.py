"""Compatibility shim for legacy ``library._core.runtime.routes`` imports."""

from agents.mentions.runtime.routes import infer_route, route_voice_bias

__all__ = [
    'infer_route',
    'route_voice_bias',
]
