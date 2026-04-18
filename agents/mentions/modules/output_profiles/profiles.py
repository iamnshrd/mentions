from __future__ import annotations

"""Compatibility wrapper for legacy output-profile imports.

Canonical output-profile rendering now lives in:
- agents.mentions.presentation.profile_renderers.build_output_profiles
"""


def build_output_profiles(query: str, analysis_profiles: dict) -> dict:
    from agents.mentions.presentation.profile_renderers import build_output_profiles as build_presentation_output_profiles
    return build_presentation_output_profiles(query, analysis_profiles)
