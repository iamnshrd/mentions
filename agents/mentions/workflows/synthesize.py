"""Canonical workflow entrypoint for synthesis."""
from __future__ import annotations

import logging

from agents.mentions.services.analysis import synthesize_analysis_bundle
from agents.mentions.utils import timed

log = logging.getLogger('mentions')


@timed('synthesize')
def synthesize(query: str, frame: dict, bundle: dict) -> dict:
    return synthesize_analysis_bundle(query=query, frame=frame, bundle=bundle)


__all__ = ['synthesize']
