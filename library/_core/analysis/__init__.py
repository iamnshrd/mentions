"""Legacy compatibility barrel for historical ``library._core.analysis`` imports.

Current code should prefer `agents.mentions.analysis.*` or higher-level
runtime/module entrypoints on the active path.

Note: some exports here survive only for compatibility and are not used by the
repo-local current path. Keep this file as a thin re-export surface only.
"""

from agents.mentions.analysis.event_context import analyze_event_context
from agents.mentions.analysis.market import analyze_market
from agents.mentions.analysis.reasoning import build_reasoning_chain
from agents.mentions.analysis.signal import assess_signal
from agents.mentions.analysis.speaker import extract_speaker_context
from agents.mentions.analysis.speaker_extract import (
    analyse_speaker_tendency,
    extract_speaker,
    extract_speaker_from_ticker,
)
from agents.mentions.analysis.trade_params import compute_trade_params

__all__ = [
    'analyse_speaker_tendency',
    'analyze_event_context',
    'analyze_market',
    'assess_signal',
    'build_reasoning_chain',
    'compute_trade_params',
    'extract_speaker',
    'extract_speaker_context',
    'extract_speaker_from_ticker',
]
