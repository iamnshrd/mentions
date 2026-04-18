"""Module wiring and binding registry for Mentions."""
from __future__ import annotations

from agents.mentions.config import MODULE_BINDINGS
from agents.mentions.presentation.response_renderer import render_user_response
from agents.mentions.runtime.frame import select_frame
from agents.mentions.runtime.retrieve import retrieve_bundle_for_frame, build_retrieval_bundle, retrieve_by_ticker
from agents.mentions.runtime.synthesize import synthesize
from agents.mentions.utils import load_json


DEFAULT_BINDINGS = {
    'frame_selector': 'default',
    'retrieval_bundle_builder': 'default',
    'ticker_retriever': 'default',
    'analysis_engine': 'default',
    'response_renderer': 'default',
}

IMPLEMENTATIONS = {
    'frame_selector': {'default': select_frame},
    'retrieval_bundle_builder': {'default': retrieve_bundle_for_frame},
    'ticker_retriever': {'default': retrieve_by_ticker},
    'analysis_engine': {'default': synthesize},
    'response_renderer': {'default': render_user_response},
}


def load_module_bindings() -> dict:
    data = load_json(MODULE_BINDINGS, default={}) or {}
    merged = dict(DEFAULT_BINDINGS)
    for key, value in data.items():
        if key in merged and isinstance(value, str) and value.strip():
            merged[key] = value.strip()
    return merged


def resolve_module(name: str):
    bindings = load_module_bindings()
    binding = bindings.get(name, 'default')
    implementations = IMPLEMENTATIONS.get(name, {})
    if binding not in implementations:
        raise KeyError(f'Unknown binding for {name}: {binding}')
    return implementations[binding]


def module_health_report() -> dict:
    bindings = load_module_bindings()
    report = {}
    for name, binding in bindings.items():
        implementations = IMPLEMENTATIONS.get(name, {})
        impl = implementations.get(binding)
        report[name] = {
            'binding': binding,
            'ok': impl is not None,
            'available': sorted(implementations.keys()),
            'callable': getattr(impl, '__name__', '') if impl else '',
        }
    return report


def get_frame_selector():
    return resolve_module('frame_selector')


def get_retrieval_bundle_builder():
    return resolve_module('retrieval_bundle_builder')


def get_ticker_retriever():
    return resolve_module('ticker_retriever')


def get_analysis_engine():
    return resolve_module('analysis_engine')


def get_response_renderer():
    return resolve_module('response_renderer')
