"""Compatibility shim for legacy ``library._core.session.state`` imports."""

from mentions_core.base.session.state import build_user_profile, update_session

__all__ = ['build_user_profile', 'update_session']
