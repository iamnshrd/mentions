"""Legacy session facade for package-level compatibility imports.

Keep this as a thin re-export surface only. Do not add new session logic here.
"""

from mentions_core.base.session.checkpoint import log
from mentions_core.base.session.context import assemble
from mentions_core.base.session.continuity import (
    load,
    read,
    save,
    summarize,
    update,
)
from mentions_core.base.session.progress import estimate
from mentions_core.base.session.state import build_user_profile, update_session

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
