"""Legacy runtime facade for package-level compatibility imports."""

from library._core.runtime.frame import select_frame
from library._core.runtime.llm_prompt import build_fallback_prompt, build_prompt
from library._core.runtime.orchestrator import (
    detect_mode,
    orchestrate,
    orchestrate_for_llm,
    orchestrate_url,
    should_use_kb,
)
from library._core.runtime.respond import respond
from library._core.runtime.retrieve import build_retrieval_bundle, retrieve_by_ticker
from library._core.runtime.routes import infer_route, route_voice_bias
from library._core.runtime.synthesize import synthesize
from library._core.runtime.synthesize_speaker import synthesize_speaker_market

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
    'retrieve_by_ticker',
    'route_voice_bias',
    'select_frame',
    'should_use_kb',
    'synthesize',
    'synthesize_speaker_market',
]
