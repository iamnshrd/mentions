"""Runtime synthesis entrypoint."""
from __future__ import annotations

import logging

from agents.mentions.modules.analysis_engine import synthesize_analysis_bundle
from agents.mentions.utils import timed

log = logging.getLogger('mentions')


@timed('synthesize')
def synthesize(query: str, frame: dict, bundle: dict) -> dict:
    return synthesize_analysis_bundle(query=query, frame=frame, bundle=bundle)
