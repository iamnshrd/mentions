"""Legacy compatibility barrel for historical ``library._core.runtime`` imports.

Current code should prefer `agents.mentions.runtime.*` or higher-level pack/runtime
entrypoints on the active path.

This barrel should stay as a thin re-export surface only. Do not add new runtime
logic here.
"""

from agents.mentions.runtime.frame import select_frame
from agents.mentions.runtime.llm_prompt import build_fallback_prompt, build_prompt
from agents.mentions.runtime.orchestrator import (
    detect_mode,
    orchestrate,
    orchestrate_for_llm,
    orchestrate_url,
    should_use_kb,
)
from agents.mentions.runtime.respond import respond
from agents.mentions.runtime.retrieve import (
    build_retrieval_bundle,
    retrieve_bundle_for_frame,
    retrieve_by_ticker,
    retrieve_market_data,
)
from agents.mentions.runtime.routes import infer_route, route_voice_bias
from agents.mentions.runtime.synthesize import synthesize
from agents.mentions.runtime.synthesize_speaker import synthesize_speaker_market

__all__ = [
    'build_fallback_prompt',
    'build_prompt',
    'build_retrieval_bundle',
    'detect_mode',
    'infer_route',
    'orchestrate',
    'orchestrate_for_llm',
    'orchestrate_url',
    'respond',
    'retrieve_bundle_for_frame',
    'retrieve_by_ticker',
    'retrieve_market_data',
    'route_voice_bias',
    'select_frame',
    'should_use_kb',
    'synthesize',
    'synthesize_speaker_market',
]
