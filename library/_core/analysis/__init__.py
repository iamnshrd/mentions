"""Legacy analysis facade for package-level compatibility imports."""

from library._core.analysis.event_context import analyze_event_context
from library._core.analysis.history import compute_base_rate, find_historical_patterns
from library._core.analysis.market import analyze_market
from library._core.analysis.reasoning import build_reasoning_chain
from library._core.analysis.signal import assess_signal
from library._core.analysis.speaker import extract_speaker_context, find_speaker_pattern
from library._core.analysis.speaker_extract import analyse_speaker_tendency, extract_speaker
from library._core.analysis.trade_params import compute_trade_params

__all__ = [
    'analyse_speaker_tendency',
    'analyze_event_context',
    'analyze_market',
    'assess_signal',
    'build_reasoning_chain',
    'compute_base_rate',
    'compute_trade_params',
    'extract_speaker',
    'extract_speaker_context',
    'find_historical_patterns',
    'find_speaker_pattern',
]
