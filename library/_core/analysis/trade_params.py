"""Compatibility shim for legacy ``library._core.analysis.trade_params`` imports."""

from agents.mentions.analysis.trade_params import compute_trade_params

__all__ = [
    'compute_trade_params',
]
