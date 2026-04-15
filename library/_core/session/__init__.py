"""Legacy session facade for package-level compatibility imports."""

from library._core.session.checkpoint import log
from library._core.session.context import assemble
from library._core.session.continuity import (
    load,
    read,
    save,
    summarize,
    update,
)
from library._core.session.progress import estimate
from library._core.session.state import build_user_profile, update_session

__all__ = [
    'assemble',
    'build_user_profile',
    'estimate',
    'load',
    'log',
    'read',
    'save',
    'summarize',
    'update',
    'update_session',
]
