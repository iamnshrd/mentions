from __future__ import annotations

"""Compatibility wrapper for legacy memo rendering imports.

Canonical user-facing rendering now lives in:
- agents.mentions.presentation.response_renderer.render_user_response
"""

from agents.mentions.presentation.response_renderer import render_user_response


render_memo_output = render_user_response
